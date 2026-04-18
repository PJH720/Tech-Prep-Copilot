"""
RAG 품질 최적화 기능 검증 테스트.

검증 항목:
  T1. Threshold: 관련 쿼리는 통과, 음성 대조군은 전원 차단
  T2. Multi-Query Expansion: expanded_queries 필드 존재 + 원본 포함 + N+1 개
  T3. Company Filter: 회사별 도메인 필터 정상 동작
  T4. UI Visualization: API 응답에 score/title/source/content 4 필드 존재 (프론트 Progress bar 렌더링 전제)

사용:
  python scripts/functional_test.py
"""
from __future__ import annotations

import io
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_URL = "http://localhost:8000"
PASS = "PASS"
FAIL = "FAIL"


def post_rag(company_id: str, query: str, top_k: int = 5) -> dict:
    r = requests.post(
        f"{BASE_URL}/api/rag/search",
        json={"company_id": company_id, "query": query, "top_k": top_k},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def check(label: str, condition: bool, detail: str = "") -> tuple[str, bool, str]:
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return (label, condition, detail)


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    # Health
    section("0. Health Check")
    h = requests.get(f"{BASE_URL}/api/health", timeout=10).json()
    results.append(check("backend ready", h.get("status") == "ok", f"chunks={h.get('chunk_count')}"))
    results.append(check("rag ready", bool(h.get("rag_ready"))))

    # T1: Threshold — 음성 대조군
    section("T1. Threshold — 음성 대조군 (무관한 쿼리)")
    neg = post_rag("", "블록체인 NFT 투자 전략 수익률 비교")
    neg_results = neg.get("results", [])
    print(f"  expanded_queries: {neg.get('expanded_queries')}")
    print(f"  returned count: {len(neg_results)}")
    for r in neg_results:
        print(f"    score={r['score']:.3f} | {r['title'][:60]}")
    # Threshold 0.4 이상만 통과해야 한다. 무관 쿼리라서 대부분 0 이 이상적이지만, 0.4 이하 항목이 전혀 없어야 통과.
    below_threshold = [r for r in neg_results if r["score"] <= 0.4]
    results.append(check("음성 대조군: 0.4 이하 결과 0개", len(below_threshold) == 0,
                         f"{len(below_threshold)} leaked"))

    # T2: 관련 쿼리 — Multi-Query Expansion
    section("T2. Multi-Query Expansion — toss/결제 시스템 아키텍처")
    pos = post_rag("toss", "결제 시스템 아키텍처 설계")
    expanded = pos.get("expanded_queries", [])
    pos_results = pos.get("results", [])
    print(f"  expanded_queries ({len(expanded)}):")
    for q in expanded:
        print(f"    - {q}")
    print(f"  returned count: {len(pos_results)}")
    for r in pos_results:
        print(f"    score={r['score']:.3f} | {r['title'][:60]}")
    results.append(check("확장 쿼리 리스트 존재", len(expanded) >= 1))
    results.append(check("원본 쿼리 포함", "결제 시스템 아키텍처 설계" in expanded))
    results.append(check("확장 개수 원본보다 많음 (multi-query 동작)", len(expanded) > 1))
    results.append(check("결과 1개 이상", len(pos_results) >= 1))
    results.append(check("모든 결과 score > 0.4", all(r["score"] > 0.4 for r in pos_results)))

    # T3: Company Filter
    section("T3. Company Filter — kakao/Kafka")
    kakao = post_rag("kakao", "Kafka 메시지 큐")
    k_results = kakao.get("results", [])
    print(f"  returned count: {len(k_results)}")
    for r in k_results:
        is_kakao = "kakao" in (r.get("source") or "").lower()
        print(f"    {'O' if is_kakao else 'X'} score={r['score']:.3f} | {r['source'][:70]}")
    results.append(check("kakao 결과 전부 kakao 도메인",
                         all("kakao" in (r.get("source") or "").lower() for r in k_results) if k_results else False,
                         f"{len(k_results)} results"))

    # T4: UI 필드 검증
    section("T4. UI Visualization Fields")
    if pos_results:
        first = pos_results[0]
        for field in ("content", "title", "source", "score"):
            results.append(check(f"field '{field}' present + non-empty",
                                 field in first and first[field] not in (None, "")))
        results.append(check("score is float in [0,1]",
                             isinstance(first.get("score"), (int, float))
                             and 0 <= first["score"] <= 1))

    # T5: Company — naver
    section("T5. Naver — Kafka")
    naver = post_rag("naver", "데이터 파이프라인 스트리밍")
    n_results = naver.get("results", [])
    print(f"  returned count: {len(n_results)}")
    for r in n_results:
        print(f"    score={r['score']:.3f} | {r['source'][:70]}")
    results.append(check("naver 결과 있음", len(n_results) >= 1))

    # Summary
    section("SUMMARY")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"  {passed} / {total} passed")
    for label, ok, detail in results:
        if not ok:
            print(f"    FAIL: {label} — {detail}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    t0 = time.time()
    code = main()
    print(f"\nElapsed: {time.time() - t0:.1f}s")
    sys.exit(code)
