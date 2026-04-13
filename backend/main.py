"""
FastAPI backend — RAG search server for Tech-Prep Copilot

Endpoints:
  POST /api/rag/search   - Query ChromaDB for company-specific tech blog context
  GET  /api/health       - Health check

Run:
    uvicorn backend.main:app --reload --port 8000

Requires:
    pip install fastapi uvicorn langchain-chroma langchain-huggingface sentence-transformers python-dotenv
"""

import os
import re
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel, Field
from tavily import TavilyClient

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
CHROMA_DIR = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "finance_tech"
EMBED_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Company ID → domain keyword mapping for metadata-filtered retrieval
COMPANY_DOMAINS: dict[str, list[str]] = {
    "toss": ["toss.tech", "toss.im", "toss"],
    "kakao": ["tech.kakao.com", "kakao"],
    "naver": ["d2.naver.com", "naver"],
    # build_vectorstore stores hostname in metadata.domain (e.g. medium.com).
    "coupang": ["medium.com", "coupang"],
}

# ── App Lifespan (load vectorstore once on startup) ───────────────────────────
vectorstore: Optional[Chroma] = None
tavily_client: Optional[TavilyClient] = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vectorstore
    if not os.path.exists(CHROMA_DIR):
        print(
            f"[WARN] ChromaDB not found at '{CHROMA_DIR}'. "
            "Run the Python pipeline first: python utils/build_vectorstore.py"
        )
    else:
        print(f"Loading embeddings model: {EMBED_MODEL}")
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            encode_kwargs={"normalize_embeddings": True},
        )
        vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=CHROMA_DIR,
        )
        count = vectorstore._collection.count()
        print(f"ChromaDB ready — {count} chunks in collection '{COLLECTION_NAME}'")
    yield
    # Cleanup (nothing to do for Chroma)


app = FastAPI(title="Tech-Prep Copilot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ─────────────────────────────────────────────────
class RagSearchRequest(BaseModel):
    company_id: str = Field(default="", max_length=50)  # "toss" | "kakao" | "naver" | "coupang"
    query: str = Field(min_length=1, max_length=2000)  # Natural language query
    top_k: int = 3  # Number of chunks to return


class RagResult(BaseModel):
    content: str
    title: str
    source: str
    score: float


class RagSearchResponse(BaseModel):
    results: list[RagResult]
    company_id: str
    rag_available: bool


class RealtimeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    company_id: str = Field(default="", max_length=50)
    max_results: int = 5


class RealtimeSearchResult(BaseModel):
    title: str
    source: str
    content: str
    score: float


class RealtimeSearchResponse(BaseModel):
    query: str
    results: list[RealtimeSearchResult]
    search_used: bool
    fallback_reason: str = ""


class AgentBriefRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    company_id: str = Field(default="", max_length=50)
    top_k: int = 3
    max_results: int = 5


class AgentBriefResponse(BaseModel):
    query: str
    summary: str
    rag_results: list[RagResult]
    realtime_results: list[RealtimeSearchResult]
    used_realtime_search: bool
    rag_available: bool


def _normalize_company_id(company_id: str) -> str:
    return company_id.strip().lower()


def _search_rag(company_id: str, query: str, top_k: int) -> tuple[list[RagResult], bool]:
    if vectorstore is None:
        return [], False

    normalized_company_id = _normalize_company_id(company_id)
    domains = COMPANY_DOMAINS.get(normalized_company_id)

    if domains:
        where_filter = {"domain": {"$in": domains}}
        docs_and_scores = vectorstore.similarity_search_with_relevance_scores(
            query,
            k=top_k,
            filter=where_filter,
        )
        if not docs_and_scores:
            docs_and_scores = vectorstore.similarity_search_with_relevance_scores(
                query, k=top_k
            )
    else:
        docs_and_scores = vectorstore.similarity_search_with_relevance_scores(query, k=top_k)

    filtered_results = [
        RagResult(
            content=doc.page_content,
            title=doc.metadata.get("title", ""),
            source=doc.metadata.get("source", ""),
            score=round(float(score), 4),
        )
        for doc, score in docs_and_scores
        if score > 0.3
    ]
    return filtered_results, True


def _needs_realtime_search(query: str) -> bool:
    realtime_keywords = [
        "latest",
        "recent",
        "today",
        "news",
        "update",
        "version",
        "release",
        "breaking",
        "trend",
        "올해",
        "최신",
        "최근",
        "업데이트",
        "릴리즈",
        "트렌드",
        "뉴스",
    ]
    lowered = query.lower()
    return any(keyword in lowered for keyword in realtime_keywords)


def _search_realtime(query: str, max_results: int) -> tuple[list[RealtimeSearchResult], bool, str]:
    if tavily_client is None:
        return [], False, "Tavily API key is not configured"

    last_error = ""
    response = None
    for _ in range(2):
        try:
            response = tavily_client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                include_answer=False,
                include_raw_content=False,
            )
            break
        except Exception as exc:
            last_error = str(exc)
    if response is None:
        return [], False, f"Tavily request failed: {last_error}"

    results = [
        RealtimeSearchResult(
            title=item.get("title", ""),
            source=item.get("url", ""),
            content=item.get("content", ""),
            score=round(float(item.get("score", 0.0)), 4),
        )
        for item in response.get("results", [])
    ]
    return results, True, ""


def _build_summary(rag_results: list[RagResult], realtime_results: list[RealtimeSearchResult]) -> str:
    context_lines: list[str] = []
    if rag_results:
        context_lines.append("RAG Context:")
        context_lines.extend(
            [f"- {result.title}: {result.content[:180]}" for result in rag_results[:3]]
        )
    if realtime_results:
        context_lines.append("Realtime Context:")
        context_lines.extend(
            [f"- {result.title}: {result.content[:180]}" for result in realtime_results[:3]]
        )
    if not context_lines:
        return "No additional context was found. Use base interview flow."
    return "\n".join(context_lines)


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    chunk_count = 0
    if vectorstore is not None:
        try:
            chunk_count = int(vectorstore._collection.count())
        except Exception:
            chunk_count = 0

    return {
        "status": "ok",
        "rag_ready": vectorstore is not None,
        "chroma_dir": CHROMA_DIR,
        "collection_name": COLLECTION_NAME,
        "chunk_count": chunk_count,
        "tavily_ready": tavily_client is not None,
    }


@app.post("/api/rag/search", response_model=RagSearchResponse)
async def rag_search(req: RagSearchRequest):
    if req.top_k < 1 or req.top_k > 10:
        raise HTTPException(status_code=422, detail="top_k must be between 1 and 10")
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be empty")

    try:
        normalized_company_id = _normalize_company_id(req.company_id)
        results, rag_available = _search_rag(normalized_company_id, query, req.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vector search failed: {exc}")

    return RagSearchResponse(results=results, company_id=normalized_company_id, rag_available=rag_available)


@app.post("/api/realtime/search", response_model=RealtimeSearchResponse)
async def realtime_search(req: RealtimeSearchRequest):
    if req.max_results < 1 or req.max_results > 10:
        raise HTTPException(status_code=422, detail="max_results must be between 1 and 10")

    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be empty")

    company_id = _normalize_company_id(req.company_id)
    if company_id:
        company_hint = re.sub(r"[^a-zA-Z0-9_-]", " ", company_id).strip()
        if company_hint:
            query = f"{query} {company_hint} engineering"

    results, search_used, fallback_reason = _search_realtime(query, req.max_results)
    return RealtimeSearchResponse(
        query=req.query,
        results=results,
        search_used=search_used,
        fallback_reason=fallback_reason,
    )


@app.post("/api/agent/brief", response_model=AgentBriefResponse)
async def agent_brief(req: AgentBriefRequest):
    if req.top_k < 1 or req.top_k > 10:
        raise HTTPException(status_code=422, detail="top_k must be between 1 and 10")
    if req.max_results < 1 or req.max_results > 10:
        raise HTTPException(status_code=422, detail="max_results must be between 1 and 10")

    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be empty")

    company_id = _normalize_company_id(req.company_id)
    rag_results, rag_available = _search_rag(company_id, query, req.top_k)

    used_realtime_search = _needs_realtime_search(query)
    realtime_results: list[RealtimeSearchResult] = []
    if used_realtime_search:
        realtime_results, _, _ = _search_realtime(query, req.max_results)

    summary = _build_summary(rag_results, realtime_results)
    return AgentBriefResponse(
        query=req.query,
        summary=summary,
        rag_results=rag_results,
        realtime_results=realtime_results,
        used_realtime_search=used_realtime_search,
        rag_available=rag_available,
    )
