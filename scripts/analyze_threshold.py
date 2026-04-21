"""
Similarity Threshold 분석 스크립트

기존 `backend/main.py` 의 `score > 0.3` 하드코딩 임계값이 적절한지 검증.
테스트 쿼리를 여러 개 실행하여 score 분포를 측정하고, 관련 있는/없는 문서의 경계를 확인한다.

실행:
    python scripts/analyze_threshold.py
"""

import os
import sys
import io

# Force UTF-8 output so Korean prints cleanly regardless of Windows console codepage.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

CHROMA_DIR = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "finance_tech"
EMBED_MODEL = "BAAI/bge-m3"
TOP_K = 10

COMPANY_DOMAINS = {
    "toss": ["toss.tech", "toss.im", "toss"],
    "kakao": ["tech.kakao.com", "kakao"],
    "naver": ["d2.naver.com", "naver"],
    "coupang": ["medium.com", "coupang"],
}

TEST_QUERIES = [
    ("toss", "결제 시스템 아키텍처 설계"),
    ("toss", "대규모 트랜잭션 일관성 보장"),
    ("kakao", "Kafka 기반 데이터 파이프라인"),
    ("kakao", "대규모 트래픽 처리 경험"),
    ("naver", "검색 엔진 성능 최적화"),
    ("naver", "MySQL 샤딩 전략"),
    ("coupang", "마이크로서비스 아키텍처"),
    ("coupang", "실시간 추천 시스템"),
    ("toss", "금융 도메인 API 설계"),
    ("", "블록체인 NFT 투자 전략"),  # 의도적으로 무관한 쿼리 (음성 대조군)
]


def search(vs: Chroma, company_id: str, query: str, k: int = TOP_K):
    domains = COMPANY_DOMAINS.get(company_id)
    if domains:
        where_filter = {"domain": {"$in": domains}}
        results = vs.similarity_search_with_relevance_scores(query, k=k, filter=where_filter)
        if not results:
            results = vs.similarity_search_with_relevance_scores(query, k=k)
    else:
        results = vs.similarity_search_with_relevance_scores(query, k=k)
    return results


def main():
    print(f"Loading embedding model: {EMBED_MODEL}")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )
    vs = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )
    print(f"Collection '{COLLECTION_NAME}' loaded. Chunks: {vs._collection.count()}\n")
    print("=" * 100)

    all_scores = []
    by_query = []
    for company_id, query in TEST_QUERIES:
        tag = f"[{company_id or 'none'}]".ljust(10)
        print(f"\n{tag} Query: {query}")
        print("-" * 100)
        results = search(vs, company_id, query, k=TOP_K)
        scores = [round(float(s), 4) for _, s in results]
        all_scores.extend(scores)
        by_query.append({"company": company_id, "query": query, "scores": scores, "results": results})

        for rank, (doc, score) in enumerate(results, 1):
            title = doc.metadata.get("title", "(no title)")[:60].replace("\xa0", " ")
            source = doc.metadata.get("source", "")[:70]
            snippet = doc.page_content[:100].replace("\n", " ").replace("\xa0", " ")
            print(f"  {rank:>2}. score={score:.4f}  {title}")
            print(f"       src: {source}")
            print(f"       txt: {snippet}...")

    print("\n" + "=" * 100)
    print("SCORE DISTRIBUTION SUMMARY")
    print("=" * 100)
    all_scores_sorted = sorted(all_scores, reverse=True)
    if all_scores_sorted:
        print(f"Total results: {len(all_scores_sorted)}")
        print(f"Max: {all_scores_sorted[0]:.4f}")
        print(f"Min: {all_scores_sorted[-1]:.4f}")
        mid = len(all_scores_sorted) // 2
        print(f"Median: {all_scores_sorted[mid]:.4f}")
        above_05 = sum(1 for s in all_scores_sorted if s >= 0.5)
        above_04 = sum(1 for s in all_scores_sorted if s >= 0.4)
        above_03 = sum(1 for s in all_scores_sorted if s >= 0.3)
        above_025 = sum(1 for s in all_scores_sorted if s >= 0.25)
        print(f"Above 0.50: {above_05} ({above_05 / len(all_scores_sorted) * 100:.1f}%)")
        print(f"Above 0.40: {above_04} ({above_04 / len(all_scores_sorted) * 100:.1f}%)")
        print(f"Above 0.30: {above_03} ({above_03 / len(all_scores_sorted) * 100:.1f}%)")
        print(f"Above 0.25: {above_025} ({above_025 / len(all_scores_sorted) * 100:.1f}%)")

    print("\n" + "=" * 100)
    print("BUCKETS (count per 0.05 range):")
    buckets = {}
    for s in all_scores:
        b = round(s * 20) / 20  # nearest 0.05
        buckets[b] = buckets.get(b, 0) + 1
    for b in sorted(buckets, reverse=True):
        bar = "#" * buckets[b]
        print(f"  {b:.2f}: {buckets[b]:>3}  {bar}")

    print("\n" + "=" * 100)
    print("NEGATIVE CONTROL: '블록체인 NFT 투자 전략' (irrelevant to finance dev blogs)")
    print("=" * 100)
    neg = next(q for q in by_query if q["query"] == "블록체인 NFT 투자 전략")
    print(f"  Max score for irrelevant query: {max(neg['scores']):.4f}")
    print(f"  Expected: high irrelevant max score → need stricter threshold to exclude")


if __name__ == "__main__":
    main()
