"""
금융/회계 키워드 필터 크롤러
- all_tech_urls.txt 의 URL을 순회하며 본문을 크롤링
- KEYWORDS 중 하나라도 포함된 아티클만 finance_tech_content.json 에 저장
"""

import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.crawler import crawl

# ── 설정 ─────────────────────────────────────────────────────────────────────
INPUT_FILE  = "all_tech_urls.txt"
OUTPUT_FILE = "finance_tech_content.json"
DELAY_SEC   = 0.5   # 요청 간 딜레이 (서버 부하 방지)

KEYWORDS = [
    "정산", "결제", "수수료", "입금", "출금", "송금", "원장", "이자",
    "회계", "세무", "부가세", "연말정산", "감사", "매출", "자산",
    "bank", "pay", "settlement", "billing", "transaction", "tax", "accounting",
]

# ── 키워드 필터 ───────────────────────────────────────────────────────────────
def is_finance_related(text: str) -> bool:
    lower = text.lower()
    return any(kw.lower() in lower for kw in KEYWORDS)


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main() -> None:
    # 1) URL 목록 로드
    with open(INPUT_FILE, encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    print(f"총 {len(urls)}개 URL 로드 완료")

    results = []
    skipped = 0
    errors  = 0

    for idx, url in enumerate(urls, 1):
        try:
            result = crawl(url)
        except Exception as e:
            print(f"[{idx}/{len(urls)}] ERROR  {url}\n  └ {e}")
            errors += 1
            time.sleep(DELAY_SEC)
            continue

        if not is_finance_related(result.title + " " + result.content):
            skipped += 1
            print(f"[{idx}/{len(urls)}] SKIP   {result.title[:50]}")
            time.sleep(DELAY_SEC)
            continue

        results.append({
            "url":     result.url,
            "title":   result.title,
            "content": result.content,
        })
        print(f"[{idx}/{len(urls)}] HIT    {result.title[:60]}")

        # 중간 저장 (10건마다)
        if len(results) % 10 == 0:
            _save(results)

        time.sleep(DELAY_SEC)

    # 최종 저장
    _save(results)
    print(f"\n완료: 수집 {len(results)}건 / 스킵 {skipped}건 / 오류 {errors}건")
    print(f"저장 경로: {OUTPUT_FILE}")


def _save(data: list) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
