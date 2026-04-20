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

import asyncio
import json
import os
import re
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from starlette.middleware.base import BaseHTTPMiddleware
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel, Field
from tavily import TavilyClient

from backend.llm.failover import AllProvidersFailed, generate_chat_json

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
CHROMA_DIR = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "finance_tech"
EMBED_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ── 면접관 페르소나 정의 ──────────────────────────────────────────────────────
INTERVIEWER_PERSONAS: dict[str, dict] = {
    "dual-strict": {
        "id": "dual-strict",
        "emoji": "🧊",
        "name": "나엄격 / 나친절",
        "summary": "압박 기술 면접 + 따뜻한 성장 피드백 | 실력 지상주의 테크 리드가 꼬리 질문으로 깊이를 파고들고, 친절한 시니어가 맞춤 성장 방향을 안내합니다.",
        "interview_character": "나엄격 (42세, 테크 리드)",
        "feedback_character": "나친절 (32세, 시니어 개발자)",
        "interview_prompt": (
            "당신은 나엄격(42세), 대형 IT기업의 테크 리드입니다.\n"
            "성격: '실력 없는 친절은 현업에서 민폐다'라고 생각하는 철저한 실력 지상주의자.\n"
            "말끝을 흐리거나 '노력하겠다'는 추상적인 답변을 가장 싫어합니다.\n"
            "질문의 핵심을 찌르며 답변이 길어지면 '그래서 결론이 뭐죠?'라고 말을 자릅니다.\n"
            "네이버, 카카오, 토스 등의 기술 블로그 내용을 인용하며 지원자의 경험이 진짜인지 꼬리 질문으로 파헤칩니다.\n"
            "반드시 한국어로 질문하세요."
        ),
        "feedback_prompt": (
            "당신은 나친절(32세), 시니어 개발자입니다.\n"
            "성격: '성장 가능성이 최고의 스펙이다'라고 믿는 긍정주의자.\n"
            "지원자의 작은 장점(태도, 기본기)을 크게 칭찬하며 자신감을 북돋아 줍니다.\n"
            "부족한 기술 스택을 보완할 수 있는 맞춤형 학습 방향을 제안합니다.\n"
            "반드시 한국어로 피드백하세요."
        ),
        "char2_question_prompt": (
            "당신은 나친절(32세), 시니어 개발자입니다.\n"
            "성장 가능성을 믿기에 지원자의 잠재력을 이끌어내는 따뜻한 질문을 합니다.\n"
            "'이 프로젝트에서 가장 뿌듯했던 순간이 뭐였나요?'처럼 지원자의 강점을 드러낼 수 있는 질문을 합니다.\n"
            "지원자가 자신 있게 경험을 풀어놓을 수 있도록 안전하고 격려하는 분위기를 만들어주세요.\n"
            "반드시 한국어로 질문하세요."
        ),
        "char1_feedback_prompt": (
            "당신은 나엄격(42세), 테크 리드입니다.\n"
            "답변의 부족한 점을 직설적으로 지적합니다. 칭찬 없이 바로 개선이 필요한 부분을 짚어냅니다.\n"
            "'이 정도 답변으로는 현업에서 살아남기 어렵습니다'는 식으로 냉정하고 구체적인 피드백을 제공합니다.\n"
            "반드시 한국어로 피드백하세요."
        ),
    },
    "business-roi": {
        "id": "business-roi",
        "emoji": "📈",
        "name": "마계산 / 오네트",
        "summary": "ROI 집착 전략가 + 비즈니스 확장 PM | 숫자와 수익성만 보는 본부장이 비용 효율을 추궁하고, 창업가 출신 PM이 기술의 비즈니스 가능성을 열어줍니다.",
        "interview_character": "마계산 (45세, 사업전략 본부장)",
        "feedback_character": "오네트 (35세, 창업가 출신 PM)",
        "interview_prompt": (
            "당신은 마계산(45세), 사업전략 본부장입니다.\n"
            "숫자와 효율이 전부인 냉철한 현실주의자.\n"
            "'그 모델 돌리는 데 GPU 비용은 얼마나 나오죠?', '그 작업 AI 안 쓰고 사람이 하는 게 더 싼 거 아닌가요?'라며 수익성을 집요하게 묻습니다.\n"
            "ROI, 시장 차별화 포인트를 데이터로 증명하라고 요구합니다.\n"
            "반드시 한국어로 질문하세요."
        ),
        "feedback_prompt": (
            "당신은 오네트(35세), 창업가 출신 PM입니다.\n"
            "실패에 너그럽고 아이디어를 현실로 만드는 과정을 즐깁니다.\n"
            "지원자의 기술이 돈이 될 수 있는 비즈니스 확장성을 칭찬하며 사업가적 마인드를 심어줍니다.\n"
            "반드시 한국어로 피드백하세요."
        ),
        "char2_question_prompt": (
            "당신은 오네트(35세), 창업가 출신 PM입니다.\n"
            "기술의 비즈니스 가능성을 탐색하는 질문을 합니다.\n"
            "'이 기술을 서비스로 만든다면 어떤 사용자 문제를 해결하고 싶으세요?'처럼 제품과 시장 관점에서 지원자의 사업가적 사고를 이끌어냅니다.\n"
            "반드시 한국어로 질문하세요."
        ),
        "char1_feedback_prompt": (
            "당신은 마계산(45세), 사업전략 본부장입니다.\n"
            "답변의 비용 효율성과 수익 기여 가능성을 냉정하게 평가합니다.\n"
            "숫자가 없는 답변은 인정하지 않으며 '이 결과물이 실제 매출에 얼마나 기여했나요?'식으로 데이터 기반 피드백을 제공합니다.\n"
            "반드시 한국어로 피드백하세요."
        ),
    },
    "infra-scale": {
        "id": "infra-scale",
        "emoji": "🏗️",
        "name": "권스케일 / 이안정",
        "summary": "인프라 확장성 집착 + SRE 실무 멘토 | 장애 시나리오로 설계 허점을 파고드는 아키텍트와, 포스트모텀 기반으로 실력을 키워주는 SRE 멘토의 조합입니다.",
        "interview_character": "권스케일 (45세, 인프라/SRE 아키텍트)",
        "feedback_character": "이안정 (38세, 시니어 SRE 엔지니어)",
        "interview_prompt": (
            "당신은 권스케일(45세), 인프라/SRE 아키텍트입니다.\n"
            "'코드가 예쁘면 뭐해요, 서버 죽으면 그냥 장애잖아요.' 시스템 안정성과 확장성만을 바라봅니다.\n"
            "'트래픽 10배 되면 어떻게 버팁니까?', '단일 장애점(SPOF)은 어디예요?'라며 설계 허점을 파고듭니다.\n"
            "반드시 한국어로 질문하세요."
        ),
        "feedback_prompt": (
            "당신은 이안정(38세), 시니어 SRE 엔지니어입니다.\n"
            "인프라 고수이지만 학습 과정을 존중하는 멘토.\n"
            "포스트모텀 사례와 함께 실무 감각을 키워주고 단계별 성장 방향을 안내합니다.\n"
            "반드시 한국어로 피드백하세요."
        ),
        "char2_question_prompt": (
            "당신은 이안정(38세), 시니어 SRE 엔지니어입니다.\n"
            "지원자의 인프라 경험과 장애 대응 실무를 파악하는 질문을 합니다.\n"
            "'실제로 운영 환경에서 장애를 경험한 적 있나요? 그때 어떻게 대응했나요?'처럼 실전 경험을 이끌어내는 구체적인 질문을 합니다.\n"
            "반드시 한국어로 질문하세요."
        ),
        "char1_feedback_prompt": (
            "당신은 권스케일(45세), 인프라/SRE 아키텍트입니다.\n"
            "답변의 인프라적 허점과 스케일링 문제를 날카롭게 지적합니다.\n"
            "'이 설계, 장애 나면 누가 책임집니까?'식으로 운영 관점의 리스크를 구체적으로 짚어냅니다.\n"
            "반드시 한국어로 피드백하세요."
        ),
    },
    "algo-global": {
        "id": "algo-global",
        "emoji": "💻",
        "name": "박알고 / 최코치",
        "summary": "FAANG식 알고리즘 심층 면접 + CS 기초 코칭 | 시간복잡도와 자료구조를 집요하게 파고드는 글로벌 인터뷰어와, 알고리즘 학습 로드맵을 제시하는 코치입니다.",
        "interview_character": "박알고 (38세, FAANG 출신 테크 인터뷰어)",
        "feedback_character": "최코치 (33세, 코딩 인터뷰 코치)",
        "interview_prompt": (
            "당신은 박알고(38세), FAANG 출신 테크 인터뷰 전문가입니다.\n"
            "'시간복잡도 모르면 엔지니어라고 할 수 없죠.' 알고리즘 효율성에 집착하는 글로벌 스탠다드 지향자.\n"
            "'Brute force 말고 더 효율적인 방법은?', '이 자료구조 선택 이유가 뭔가요?'라며 CS 기초부터 최적화까지 파고듭니다.\n"
            "반드시 한국어로 질문하세요."
        ),
        "feedback_prompt": (
            "당신은 최코치(33세), 코딩 인터뷰 코치입니다.\n"
            "'알고리즘은 연습의 영역이에요. 포기만 안 하면 돼요.' 체계적인 훈련 로드맵을 제시하는 인내의 멘토.\n"
            "지원자가 막힌 유형별 문제 세트와 풀이 전략을 맞춤형으로 안내합니다.\n"
            "반드시 한국어로 피드백하세요."
        ),
        "char2_question_prompt": (
            "당신은 최코치(33세), 코딩 인터뷰 코치입니다.\n"
            "지원자의 알고리즘 사고 과정을 친절하게 탐색하는 질문을 합니다.\n"
            "'이 문제를 처음 봤을 때 어떤 접근법이 떠올랐나요?'처럼 사고 과정을 자연스럽게 이끌어냅니다.\n"
            "반드시 한국어로 질문하세요."
        ),
        "char1_feedback_prompt": (
            "당신은 박알고(38세), FAANG 출신 테크 인터뷰어입니다.\n"
            "알고리즘 정확성과 시간복잡도 분석의 오류를 냉정하게 지적합니다.\n"
            "'O(n²)으로 푸셨는데, 글로벌 스탠다드에서 이건 탈락 수준입니다'처럼 명확하게 부족한 점을 제시합니다.\n"
            "반드시 한국어로 피드백하세요."
        ),
    },
}

# Similarity threshold — 실험으로 결정. 자세한 근거: docs/rag-threshold-analysis.md
# 요약: 음성 대조군("블록체인 NFT 투자 전략") max score = 0.3647 → 0.3은 무관 문서를 통과시킴.
# 0.40 상향 시 음성 대조군 100% 배제 + 관련 쿼리 상위권만 유지.
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.4"))

# Multi-Query Rewriting (Advanced RAG) — 원본 쿼리를 N개 관점으로 확장해 검색 재현율을 보완.
# 자세한 설계: docs/rag-threshold-analysis.md 의 "Trade-off" 섹션 참고.
ENABLE_QUERY_EXPANSION = os.getenv("RAG_QUERY_EXPANSION", "1") == "1"
QUERY_EXPANSION_COUNT = int(os.getenv("RAG_QUERY_EXPANSION_COUNT", "3"))
QUERY_REWRITE_MODEL = os.getenv("RAG_REWRITE_MODEL", "gpt-4o-mini")

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


def _deep_sanitize(obj):
    """응답 직렬화 전 모든 문자열에서 lone surrogate 제거."""
    if isinstance(obj, str):
        return "".join(ch for ch in obj if not (0xD800 <= ord(ch) <= 0xDFFF))
    if isinstance(obj, dict):
        return {k: _deep_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_sanitize(item) for item in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    """응답 직렬화 시 surrogate 문자 재귀 제거 후 UTF-8 인코딩."""
    def render(self, content) -> bytes:  # type: ignore[override]
        return json.dumps(_deep_sanitize(content), ensure_ascii=False).encode("utf-8")

app = FastAPI(title="Tech-Prep Copilot API", lifespan=lifespan, default_response_class=SafeJSONResponse)


class SanitizeBodyMiddleware(BaseHTTPMiddleware):
    """JSON 요청 바디의 lone surrogate를 Pydantic 검증 전에 제거한다."""
    async def dispatch(self, request: Request, call_next):
        if (
            request.method in ("POST", "PUT", "PATCH")
            and "application/json" in request.headers.get("content-type", "")
        ):
            raw = await request.body()
            try:
                text = raw.decode("utf-8", "surrogatepass")
                clean = "".join(ch for ch in text if not (0xD800 <= ord(ch) <= 0xDFFF))
                request._body = clean.encode("utf-8")  # type: ignore[attr-defined]
            except Exception:
                pass
        return await call_next(request)


@app.exception_handler(RequestValidationError)
async def safe_validation_exception_handler(request: Request, exc: RequestValidationError):
    """422 에러 응답 자체에 surrogate가 포함돼 500이 나는 현상 방지."""
    return SafeJSONResponse(
        status_code=422,
        content=_deep_sanitize({"detail": jsonable_encoder(exc.errors())}),
    )


app.add_middleware(SanitizeBodyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:9000"],
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
    expanded_queries: list[str] = Field(
        default_factory=list,
        description="Query Rewriting 으로 실제 검색에 사용된 쿼리 목록 (원본 + 확장). 투명성/디버깅 용도.",
    )


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


# ── 페르소나 / 인터뷰 모델 ────────────────────────────────────────────────────
class PersonaInfo(BaseModel):
    id: str
    emoji: str
    name: str
    summary: str
    interview_character: str
    feedback_character: str


class PersonaListResponse(BaseModel):
    personas: list[PersonaInfo]


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class InterviewQuestionRequest(BaseModel):
    resume_text: str = Field(min_length=1, max_length=10000)
    company_name: str = Field(min_length=1, max_length=100)
    company_tech_stack: list[str] = []
    company_description: str = ""
    history: list[ChatMessage] = []
    persona_id: str = "dual-strict"
    active_char: str = "interviewer"   # "interviewer" | "feedback_giver"
    context_summary: str = ""
    recent_questions: list[str] = []


class InterviewQuestionResponse(BaseModel):
    question: str
    persona_id: str
    interviewer_name: str


class EvaluateAnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(min_length=1, max_length=5000)
    company_name: str = Field(min_length=1, max_length=100)
    company_tech_stack: list[str] = []
    persona_id: str = "dual-strict"
    active_char: str = "interviewer"   # 질문했던 캐릭터 — 피드백은 반대 캐릭터가 담당
    context_summary: str = ""


class EvaluateAnswerResponse(BaseModel):
    accuracy: int
    logic: int
    suggestion: str
    referenceQuote: str
    feedback_name: str


class InterviewTurnRequest(BaseModel):
    """evaluate + next question을 Gemini 1회 호출로 처리하는 통합 엔드포인트용 모델."""
    resume_text: str = Field(min_length=1, max_length=10000)
    company_name: str = Field(min_length=1, max_length=100)
    company_tech_stack: list[str] = []
    company_description: str = ""
    history: list[ChatMessage] = []
    persona_id: str = "dual-strict"
    feedback_char: str = "interviewer"   # 피드백 담당 캐릭터 (= 질문했던 캐릭터)
    next_char: str = "interviewer"       # 다음 질문 담당 캐릭터 (랜덤 선택)
    context_summary: str = ""
    recent_questions: list[str] = []
    last_question: str = ""
    user_answer: str = Field(min_length=1, max_length=5000)


class InterviewTurnResponse(BaseModel):
    feedback_accuracy: int
    feedback_logic: int
    feedback_suggestion: str
    feedback_reference_quote: str
    feedback_name: str
    next_question: str
    next_interviewer_name: str
    next_asked_by: str


def _normalize_company_id(company_id: str) -> str:
    return company_id.strip().lower()


def _rewrite_query(query: str, company_id: str = "", n: int = QUERY_EXPANSION_COUNT) -> list[str]:
    """
    원본 질문을 관점이 다른 N개의 검색 쿼리로 확장한다.

    - Naive RAG 의 재현율(recall) 한계 보완: 하나의 단어 선택이 관련 문서를 놓치는 경우를 여러 관점으로 커버.
    - 모든 LLM 프로바이더 실패 시 빈 리스트 → 호출부에서 원본 쿼리로 fallback.
    """
    company_hint = f" (대상 회사: {company_id})" if company_id else ""
    system_prompt = (
        "너는 한국어 기술 블로그 검색 쿼리를 다듬는 도우미다. "
        "입력된 IT 면접 주제 질문을 기술 블로그에서 관련 글을 잘 찾을 수 있는 서로 다른 관점의 "
        f"{n}개 검색 쿼리로 재작성한다. 원본 의도를 유지하되, 동의어/세부기술/상위개념 등으로 다양성을 준다. "
        '반드시 JSON 객체 한 개만 반환한다. 형식: {"queries": ["쿼리1", "쿼리2", ...]}'
    )
    user_prompt = f"원본 질문{company_hint}: {query}"

    try:
        content, _provider = generate_chat_json(
            system_prompt,
            user_prompt,
            openai_model_override=QUERY_REWRITE_MODEL,
        )
        parsed = json.loads(content)
    except (AllProvidersFailed, json.JSONDecodeError, TypeError):
        return []

    candidates: list[str] = []
    if isinstance(parsed, dict):
        for value in parsed.values():
            if isinstance(value, list):
                candidates = value
                break
    elif isinstance(parsed, list):
        candidates = parsed

    return [q.strip() for q in candidates if isinstance(q, str) and q.strip()][:n]


def _search_rag(
    company_id: str,
    query: str,
    top_k: int,
    use_query_expansion: bool = ENABLE_QUERY_EXPANSION,
) -> tuple[list[RagResult], bool, list[str]]:
    """
    Multi-Query RAG 검색:
      1) (선택) 원본 쿼리를 N개 관점으로 확장
      2) 각 쿼리로 회사 도메인 필터 검색 (비어있으면 전역 검색으로 fallback)
      3) URL(source) 기준 dedup, 여러 쿼리에서 나오면 최고 score 채택
      4) RAG_SIMILARITY_THRESHOLD 로 필터 후 score 내림차순 상위 top_k 반환
    """
    if vectorstore is None:
        return [], False, []

    normalized_company_id = _normalize_company_id(company_id)
    domains = COMPANY_DOMAINS.get(normalized_company_id)

    queries: list[str] = [query]
    if use_query_expansion:
        expanded = _rewrite_query(query, normalized_company_id)
        for q in expanded:
            if q and q not in queries:
                queries.append(q)

    # 쿼리별 검색 결과를 URL(source) 로 병합. 동일 source 는 최고 score 로 합친다.
    merged: dict[str, tuple[float, RagResult]] = {}
    per_query_k = max(top_k, 3)

    for q in queries:
        if domains:
            where_filter = {"domain": {"$in": domains}}
            docs_and_scores = vectorstore.similarity_search_with_relevance_scores(
                q, k=per_query_k, filter=where_filter
            )
            if not docs_and_scores:
                docs_and_scores = vectorstore.similarity_search_with_relevance_scores(
                    q, k=per_query_k
                )
        else:
            docs_and_scores = vectorstore.similarity_search_with_relevance_scores(q, k=per_query_k)

        for doc, score in docs_and_scores:
            numeric_score = float(score)
            if numeric_score <= RAG_SIMILARITY_THRESHOLD:
                continue
            source = doc.metadata.get("source", "") or doc.page_content[:80]
            result = RagResult(
                content=doc.page_content,
                title=doc.metadata.get("title", ""),
                source=doc.metadata.get("source", ""),
                score=round(numeric_score, 4),
            )
            prev = merged.get(source)
            if prev is None or numeric_score > prev[0]:
                merged[source] = (numeric_score, result)

    ranked = sorted(merged.values(), key=lambda item: item[0], reverse=True)
    filtered_results = [result for _, result in ranked[:top_k]]
    return filtered_results, True, queries


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
    # 외부 소스(Tavily 등) 텍스트에 포함될 수 있는 surrogate 제거
    return _sanitize("\n".join(context_lines))


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
        "llm_provider_order": os.getenv("LLM_PROVIDER_ORDER", "gemini,openai,upstage"),
        "llm_gemini_configured": bool(
            os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        ),
        "llm_openai_configured": bool(os.getenv("OPENAI_API_KEY", "")),
        "llm_upstage_configured": bool(os.getenv("UPSTAGE_API_KEY", "")),
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
        results, rag_available, expanded_queries = _search_rag(
            normalized_company_id, query, req.top_k
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vector search failed: {exc}")

    return RagSearchResponse(
        results=results,
        company_id=normalized_company_id,
        rag_available=rag_available,
        expanded_queries=expanded_queries,
    )


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


# ── Gemini 헬퍼 ──────────────────────────────────────────────────────────────
def _sanitize(text: str) -> str:
    """lone surrogate(U+D800–U+DFFF) 제거 — SDK 입·출력 UTF-8 인코딩 오류 방지."""
    return "".join(ch for ch in text if not (0xD800 <= ord(ch) <= 0xDFFF))


def _llm_generate(system_prompt: str, user_prompt: str) -> str:
    """Gemini → OpenAI → Upstage 순차 failover (LLM_PROVIDER_ORDER 로 재정렬 가능)."""
    try:
        text, provider = generate_chat_json(system_prompt, user_prompt)
        print(f"[llm] ok provider={provider}")
        return text
    except AllProvidersFailed as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "LLM API를 모두 사용할 수 없습니다. GOOGLE_API_KEY, OPENAI_API_KEY, "
                f"UPSTAGE_API_KEY 중 최소 하나와 네트워크를 확인하세요. ({exc})"
            ),
        ) from exc


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
    rag_results, rag_available, _ = _search_rag(company_id, query, req.top_k)

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


# ── 페르소나 / 인터뷰 엔드포인트 ──────────────────────────────────────────────
@app.get("/api/personas", response_model=PersonaListResponse)
async def list_personas():
    personas = [
        PersonaInfo(
            id=p["id"],
            emoji=p["emoji"],
            name=p["name"],
            summary=p["summary"],
            interview_character=p["interview_character"],
            feedback_character=p["feedback_character"],
        )
        for p in INTERVIEWER_PERSONAS.values()
    ]
    return PersonaListResponse(personas=personas)


@app.post("/api/interview/question", response_model=InterviewQuestionResponse)
async def generate_interview_question(req: InterviewQuestionRequest):
    persona = INTERVIEWER_PERSONAS.get(req.persona_id, INTERVIEWER_PERSONAS["dual-strict"])

    # active_char에 따라 질문 프롬프트와 발화자 이름 결정
    if req.active_char == "feedback_giver":
        system_prompt = persona["char2_question_prompt"]
        interviewer_name = persona["feedback_character"]
    else:
        system_prompt = persona["interview_prompt"]
        interviewer_name = persona["interview_character"]

    history_text = "\n".join(
        f"{'면접관' if m.role == 'assistant' else '지원자'}: {m.content}"
        for m in req.history
    ) or "없음"

    context_section = (
        f"\n엔지니어링 컨텍스트 (RAG):\n{req.context_summary}\n"
        if req.context_summary
        else ""
    )
    anti_repeat = (
        "\n다음 질문은 반복하지 마세요:\n" + "\n".join(req.recent_questions)
        if req.recent_questions
        else ""
    )

    user_prompt = (
        f"회사: {req.company_name}\n"
        f"기술 스택: {', '.join(req.company_tech_stack)}\n"
        f"회사 소개: {req.company_description}\n"
        f"{context_section}"
        f"{anti_repeat}\n"
        f"지원자 이력서:\n{req.resume_text[:3000]}\n\n"
        f"인터뷰 히스토리:\n{history_text}\n\n"
        "위 이력서와 회사 기술 스택을 바탕으로 심층 기술 면접 질문을 하나 만드세요. "
        "반드시 다음 JSON 형식으로만 답변하세요: {\"question\": \"질문 내용\"}"
    )

    try:
        raw = await asyncio.to_thread(_llm_generate, system_prompt, user_prompt)
        parsed = json.loads(raw)
        question = parsed.get("question", "").strip()
        if not question:
            raise ValueError("empty question")
    except Exception as exc:
        import traceback
        print(f"[ERROR /api/interview/question] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"면접 질문 생성 실패: {type(exc).__name__}: {exc}")

    return InterviewQuestionResponse(
        question=question,
        persona_id=persona["id"],
        interviewer_name=interviewer_name,
    )


@app.post("/api/interview/evaluate", response_model=EvaluateAnswerResponse)
async def evaluate_interview_answer(req: EvaluateAnswerRequest):
    persona = INTERVIEWER_PERSONAS.get(req.persona_id, INTERVIEWER_PERSONAS["dual-strict"])

    # 질문한 캐릭터의 반대 캐릭터가 피드백 담당
    if req.active_char == "feedback_giver":
        system_prompt = persona["char1_feedback_prompt"]
        feedback_name = persona["interview_character"]
    else:
        system_prompt = persona["feedback_prompt"]
        feedback_name = persona["feedback_character"]

    context_section = (
        f"\n평가 참고 컨텍스트:\n{req.context_summary}\n"
        if req.context_summary
        else ""
    )

    user_prompt = (
        f"회사: {req.company_name}\n"
        f"기술 스택: {', '.join(req.company_tech_stack)}\n"
        f"{context_section}\n"
        f"질문: {req.question}\n"
        f"지원자 답변: {req.answer}\n\n"
        "위 답변을 평가하고 한국어로 피드백을 제공하세요. "
        "반드시 다음 JSON 형식으로만 답변하세요:\n"
        "{\"accuracy\": 0~100 숫자, \"logic\": 0~100 숫자, "
        "\"suggestion\": \"개선 제안 (한국어)\", "
        "\"referenceQuote\": \"관련 기술 개념이나 참고 사항, 없으면 빈 문자열\"}"
    )

    try:
        raw = await asyncio.to_thread(_llm_generate, system_prompt, user_prompt)
        parsed = json.loads(raw)
        return EvaluateAnswerResponse(
            accuracy=int(parsed.get("accuracy", 50)),
            logic=int(parsed.get("logic", 50)),
            suggestion=parsed.get("suggestion", ""),
            referenceQuote=parsed.get("referenceQuote", ""),
            feedback_name=feedback_name,
        )
    except Exception as exc:
        import traceback
        print(f"[ERROR /api/interview/evaluate] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"답변 평가 실패: {type(exc).__name__}: {exc}")


@app.post("/api/interview/turn", response_model=InterviewTurnResponse)
async def interview_turn(req: InterviewTurnRequest):
    """피드백 + 다음 질문을 Gemini 1회 호출로 처리 — 쿼터 절약용 통합 엔드포인트."""
    persona = INTERVIEWER_PERSONAS.get(req.persona_id, INTERVIEWER_PERSONAS["dual-strict"])

    # 피드백 캐릭터 결정
    if req.feedback_char == "feedback_giver":
        feedback_system = persona["char1_feedback_prompt"]
        feedback_name = persona["interview_character"]
    else:
        feedback_system = persona["feedback_prompt"]
        feedback_name = persona["feedback_character"]

    # 다음 질문 캐릭터 결정
    if req.next_char == "feedback_giver":
        next_question_system = persona["char2_question_prompt"]
        next_interviewer_name = persona["feedback_character"]
    else:
        next_question_system = persona["interview_prompt"]
        next_interviewer_name = persona["interview_character"]

    context_section = f"\n참고 컨텍스트:\n{req.context_summary}\n" if req.context_summary else ""
    anti_repeat = (
        "\n다음 질문은 반복하지 마세요:\n" + "\n".join(req.recent_questions)
        if req.recent_questions else ""
    )
    history_text = "\n".join(
        f"{'면접관' if m.role == 'assistant' else '지원자'}: {m.content}"
        for m in req.history
    ) or "없음"

    system_prompt = (
        f"[피드백 역할]\n{feedback_system}\n\n"
        f"[다음 질문 역할]\n{next_question_system}"
    )
    user_prompt = (
        f"회사: {req.company_name}\n"
        f"기술 스택: {', '.join(req.company_tech_stack)}\n"
        f"회사 소개: {req.company_description}\n"
        f"{context_section}"
        f"지원자 이력서:\n{req.resume_text[:2000]}\n\n"
        f"인터뷰 히스토리:\n{history_text}\n\n"
        f"방금 질문: {req.last_question}\n"
        f"지원자 답변: {req.user_answer}\n"
        f"{anti_repeat}\n\n"
        "위 답변에 대한 피드백을 제공하고, 이어서 다음 기술 면접 질문을 하나 생성하세요. "
        "반드시 다음 JSON 형식으로만 답변하세요:\n"
        "{\n"
        '  "feedback": {\n'
        '    "accuracy": 0~100 숫자,\n'
        '    "logic": 0~100 숫자,\n'
        '    "suggestion": "개선 제안 (한국어)",\n'
        '    "referenceQuote": "참고 개념, 없으면 빈 문자열"\n'
        "  },\n"
        '  "question": "다음 면접 질문 (한국어)"\n'
        "}"
    )

    try:
        raw = await asyncio.to_thread(_llm_generate, system_prompt, user_prompt)
        parsed = json.loads(raw)
        fb = parsed.get("feedback", {})
        next_q = parsed.get("question", "").strip()
        if not next_q:
            raise ValueError("empty question in turn response")
        return InterviewTurnResponse(
            feedback_accuracy=int(fb.get("accuracy", 50)),
            feedback_logic=int(fb.get("logic", 50)),
            feedback_suggestion=fb.get("suggestion", ""),
            feedback_reference_quote=fb.get("referenceQuote", ""),
            feedback_name=feedback_name,
            next_question=next_q,
            next_interviewer_name=next_interviewer_name,
            next_asked_by=req.next_char,
        )
    except Exception as exc:
        import traceback
        print(f"[ERROR /api/interview/turn] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"인터뷰 턴 처리 실패: {type(exc).__name__}: {exc}")
