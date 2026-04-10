"""
범용 기술 블로그 크롤러
- 메타 태그(og:title, og:description) 우선 추출
- 사이트별 본문 셀렉터 매핑 (토스, 네이버 등)
- 매핑 없는 사이트는 휴리스틱(article, main, 긴 p태그)으로 폴백
- 토스 테크 블로그 아티클 URL 목록 수집
  · fetch_toss_article_urls        : requests 기반 (정적 HTML, 1페이지만)
  · fetch_toss_article_urls_js     : Playwright 기반 (JS 렌더링 + 페이지네이션 전체)
- 네이버 D2 아티클 URL 수집 / 본문 API 크롤링
  · fetch_naver_d2_urls            : REST API 기반 (전체 페이지)
- 카카오 테크 블로그 아티클 URL 수집 / 본문 API 크롤링
  · fetch_kakao_article_urls       : REST API 기반 (전체 페이지)
"""

import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

# ── 사이트별 본문 CSS 셀렉터 ──────────────────────────────────────────────────
SITE_SELECTORS: dict[str, dict] = {
    "toss.tech": {
        "title":   "h1",
        "content": "article",
    },
    "techblog.woowahan.com": {
        "title":   "h1.post-title",
        "content": "div.post-content",
    },
    # d2.naver.com: React SPA → _crawl_naver_d2_api() 로 처리
    # tech.kakao.com: Nuxt SSR → _crawl_kakao_api() 로 처리
    "engineering.linecorp.com": {
        "title":   "h1",
        "content": "div.entry-content",
    },
    "kakaoenterprise.github.io": {
        "title":   "h1",
        "content": "div.post-content",
    },
    "medium.com": {
        "title":   "h1",
        "content": "article",
    },
}

# ── 데이터 클래스 ─────────────────────────────────────────────────────────────
@dataclass
class CrawlResult:
    url: str
    title: str
    content: str
    source: str  # "meta" | "selector" | "heuristic"


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────
def _get_soup(url: str, timeout: int = 10) -> BeautifulSoup:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        status = resp.status_code
        reason = {
            400: "잘못된 요청 (Bad Request)",
            401: "인증 필요 (Unauthorized)",
            403: "접근 차단됨 — 봇 감지 또는 권한 없음 (Forbidden)",
            404: "페이지를 찾을 수 없음 (Not Found)",
            429: "요청 횟수 초과 — 잠시 후 재시도 필요 (Too Many Requests)",
            500: "서버 내부 오류 (Internal Server Error)",
            502: "게이트웨이 오류 (Bad Gateway)",
            503: "서비스 일시 중단 (Service Unavailable)",
        }.get(status, "알 수 없는 HTTP 오류")
        raise requests.HTTPError(
            f"[HTTP {status}] {reason} — {url}", response=resp
        ) from e
    resp.encoding = resp.apparent_encoding
    return BeautifulSoup(resp.text, "html.parser")


def _meta_title(soup: BeautifulSoup) -> str:
    for attr in [("property", "og:title"), ("name", "twitter:title")]:
        tag = soup.find("meta", {attr[0]: attr[1]})
        if tag and tag.get("content"):
            return tag["content"].strip()
    if soup.title:
        return soup.title.string.strip()
    return ""


def _clean_text(raw: str) -> str:
    """연속 공백·개행 정리."""
    text = re.sub(r"\n{3,}", "\n\n", raw)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _heuristic_content(soup: BeautifulSoup) -> str:
    """사이트 셀렉터가 없을 때 범용 추출."""
    # 1순위: <article>
    article = soup.find("article")
    if article:
        return _clean_text(article.get_text("\n"))

    # 2순위: <main>
    main = soup.find("main")
    if main:
        return _clean_text(main.get_text("\n"))

    # 3순위: 글자 수 기준으로 가장 긴 <div> 하나
    divs = soup.find_all("div")
    best = max(divs, key=lambda d: len(d.get_text()), default=None)
    if best:
        return _clean_text(best.get_text("\n"))

    # 4순위: 모든 <p> 합산
    paragraphs = [p.get_text(" ") for p in soup.find_all("p") if len(p.get_text()) > 40]
    return _clean_text("\n\n".join(paragraphs))


# ── 사이트별 API 크롤러 ──────────────────────────────────────────────────────
def _crawl_naver_d2_api(url: str, timeout: int = 10) -> CrawlResult:
    """
    네이버 D2는 React SPA이므로 REST API로 본문을 가져온다.
    URL 형식: https://d2.naver.com/helloworld/{postHtmlId}
              https://d2.naver.com/news/{postHtmlId}
    API: GET /api/v1/contents/{postHtmlId}
         → { postTitle, postHtml (전체 HTML), authors, ... }
    """
    # URL에서 postHtmlId 추출 (/helloworld/7997284 → 7997284)
    m = re.search(r"/(helloworld|news)/([^/?#]+)", url)
    if not m:
        raise ValueError(f"네이버 D2 URL 형식을 인식할 수 없습니다: {url}")
    post_id = m.group(2)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://d2.naver.com/",
    }
    api_url = f"https://d2.naver.com/api/v1/contents/{post_id}"
    resp = requests.get(api_url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    title = data.get("postTitle", "")
    html_content = data.get("postHtml", "")
    if not html_content:
        raise ValueError(f"네이버 D2 API 본문이 비어 있습니다: {url}")

    # HTML → 일반 텍스트
    soup = BeautifulSoup(html_content, "html.parser")
    content = _clean_text(soup.get_text("\n"))
    return CrawlResult(url=url, title=title, content=content, source="api")


def _crawl_kakao_api(url: str, timeout: int = 10) -> CrawlResult:
    """
    카카오 테크 블로그는 Nuxt SSR이며 REST API로 본문을 가져온다.
    URL 형식: https://tech.kakao.com/posts/{id}
    API: GET /api/v1/posts/{id}
         → { title, content (전체 HTML), ... }
    """
    m = re.search(r"/posts/(\d+)", url)
    if not m:
        raise ValueError(f"카카오 테크 URL 형식을 인식할 수 없습니다: {url}")
    post_id = m.group(1)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://tech.kakao.com/blog/",
    }
    api_url = f"https://tech.kakao.com/api/v1/posts/{post_id}"
    resp = requests.get(api_url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    title = data.get("title", "")
    html_content = data.get("content", "")
    if not html_content:
        raise ValueError(f"카카오 API 본문이 비어 있습니다: {url}")

    soup = BeautifulSoup(html_content, "html.parser")
    content = _clean_text(soup.get_text("\n"))
    return CrawlResult(url=url, title=title, content=content, source="api")


# ── 공개 API ─────────────────────────────────────────────────────────────────
def crawl(url: str, timeout: int = 10) -> CrawlResult:
    """
    URL을 받아 제목과 본문 텍스트를 반환한다.

    Args:
        url: 크롤링할 페이지 URL
        timeout: HTTP 요청 타임아웃(초)

    Returns:
        CrawlResult(url, title, content, source)

    Raises:
        requests.HTTPError: HTTP 오류 응답
        requests.Timeout: 타임아웃
        ValueError: 본문을 전혀 추출하지 못한 경우
    """
    hostname = urlparse(url).hostname or ""
    domain = hostname.removeprefix("www.")

    # ── SPA/API 전용 사이트 우선 처리 ───────────────────────────────────────
    if domain == "d2.naver.com":
        return _crawl_naver_d2_api(url, timeout)
    if domain == "tech.kakao.com":
        return _crawl_kakao_api(url, timeout)

    soup = _get_soup(url, timeout)

    # ── 제목 추출 (메타 우선) ────────────────────────────────────────────────
    title = _meta_title(soup)

    # ── 본문 추출 ────────────────────────────────────────────────────────────
    selector = next(
        (v for k, v in SITE_SELECTORS.items() if domain.endswith(k)),
        None,
    )

    if selector:
        # 사이트별 셀렉터 사용
        if not title:
            title_tag = soup.select_one(selector["title"])
            title = title_tag.get_text(strip=True) if title_tag else ""

        content_tag = soup.select_one(selector["content"])
        if not content_tag:
            raise ValueError(f"본문 셀렉터({selector['content']})를 찾지 못했습니다: {url}")

        content = _clean_text(content_tag.get_text("\n"))
        source = "selector"
    else:
        # 휴리스틱 폴백
        content = _heuristic_content(soup)
        source = "heuristic"

    if not content:
        raise ValueError(f"본문을 추출하지 못했습니다: {url}")

    return CrawlResult(url=url, title=title, content=content, source=source)


def crawl_many(
    urls: list[str],
    timeout: int = 10,
    skip_errors: bool = True,
) -> list[CrawlResult]:
    """
    여러 URL을 순차적으로 크롤링한다.

    Args:
        urls: 크롤링할 URL 목록
        timeout: 개별 요청 타임아웃(초)
        skip_errors: True면 실패 URL을 건너뜀, False면 예외를 올림

    Returns:
        성공한 CrawlResult 목록
    """
    results = []
    for url in urls:
        try:
            results.append(crawl(url, timeout))
        except Exception as e:
            if skip_errors:
                print(f"[SKIP] {url} — {e}")
            else:
                raise
    return results


# ── 토스 테크 블로그 URL 수집 ────────────────────────────────────────────────
_TOSS_BASE = "https://toss.tech"
_TOSS_ARTICLE_PREFIX = f"{_TOSS_BASE}/article"
_TOSS_LISTING_URL = f"{_TOSS_BASE}/tech"


def fetch_toss_article_urls(
    listing_url: str = _TOSS_LISTING_URL,
    timeout: int = 10,
) -> list[str]:
    """
    토스 테크 블로그 목록 페이지에서 아티클 URL을 수집한다.

    페이지 내 <a href="/article/{slug}"> 패턴의 링크를 추출해
    전체 URL(https://toss.tech/article/{slug}) 리스트로 반환한다.

    Args:
        listing_url: 목록 페이지 URL (기본값: https://toss.tech/tech)
        timeout: HTTP 요청 타임아웃(초)

    Returns:
        중복 제거된 아티클 전체 URL 목록 (slug 알파벳순 정렬)

    Raises:
        requests.HTTPError: HTTP 오류 응답
        requests.Timeout: 타임아웃
    """
    soup = _get_soup(listing_url, timeout)
    slugs: set[str] = set()
    for a in soup.find_all("a", href=True):
        m = re.match(r"^/article/([^/?#]+)", a["href"])
        if m:
            slugs.add(m.group(1))
    return [f"{_TOSS_ARTICLE_PREFIX}/{slug}" for slug in sorted(slugs)]


# ── 토스 테크 블로그 전체 URL 수집 (Playwright / JS 렌더링) ──────────────────
_TOSS_TABS = [
    "https://toss.tech/tech",          # Engineering
    "https://toss.tech/design",        # Design
    "https://toss.tech/product",       # Product
]

# 다음 페이지 버튼 후보 셀렉터 (우선순위 순)
# DOM을 확인한 후 맞는 셀렉터로 교체 가능
_NEXT_BTN_CANDIDATES = [
    "button[aria-label*='next']",
    "button[aria-label*='다음']",
    "[data-direction='next']",
    "nav button:last-child",           # 일반적인 마지막 버튼
    "ul.pagination li:last-child a",
]


def _collect_slugs_on_page(page) -> set[str]:  # type: ignore[no-untyped-def]
    """현재 렌더링된 페이지에서 /article/{slug} 링크를 모두 수집."""
    slugs: set[str] = set()
    for handle in page.query_selector_all('a[href^="/article/"]'):
        href = handle.get_attribute("href") or ""
        m = re.match(r"^/article/([^/?#]+)", href)
        if m:
            slugs.add(m.group(1))
    return slugs


def _try_go_next_page(page, timeout_ms: int) -> bool:  # type: ignore[no-untyped-def]
    """
    다음 페이지 버튼을 찾아 클릭한다.
    성공하면 True, 더 이상 페이지가 없거나 버튼을 못 찾으면 False.
    """
    import time

    # ── 전략 1: 후보 셀렉터로 버튼 탐색 ─────────────────────────────────────
    for sel in _NEXT_BTN_CANDIDATES:
        btn = page.query_selector(sel)
        if btn and btn.is_visible() and btn.is_enabled():
            btn.click()
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                pass
            time.sleep(1.0)
            return True

    # ── 전략 2: 현재 활성 페이지 번호 다음 번호 클릭 ─────────────────────────
    # 숫자 버튼이 <button> 또는 <a> 로 렌더링되는 경우를 모두 처리
    active = page.query_selector(
        "button[aria-current='page'], a[aria-current='page'], "
        ".active > button, .active > a, [class*='active'] button"
    )
    if active:
        active_text = (active.inner_text() or "").strip()
        if active_text.isdigit():
            next_num = str(int(active_text) + 1)
            # 같은 레벨에서 다음 번호 텍스트를 가진 버튼/링크를 탐색
            candidates = page.query_selector_all("button, a")
            for c in candidates:
                if (c.inner_text() or "").strip() == next_num and c.is_visible():
                    c.click()
                    try:
                        page.wait_for_load_state("networkidle", timeout=timeout_ms)
                    except Exception:
                        pass
                    time.sleep(1.0)
                    return True

    return False


def fetch_toss_article_urls_js(
    tab_urls: list[str] | None = None,
    max_pages_per_tab: int = 100,
    timeout_ms: int = 30_000,
    headless: bool = True,
) -> list[str]:
    """
    Playwright로 JS를 렌더링해 토스 테크 블로그 전체 아티클 URL을 수집한다.

    · Engineering / Design / Product 탭을 순서대로 방문
    · 각 탭에서 페이지가 더 없을 때까지 다음 페이지 버튼을 클릭
    · 새 slug가 더 이상 나오지 않으면 해당 탭 수집 종료

    사전 조건:
        pip install playwright
        playwright install chromium

    Args:
        tab_urls        : 수집할 탭 URL 목록 (None이면 기본 3개 탭 전체)
        max_pages_per_tab: 탭당 최대 페이지 클릭 수 (무한루프 방지)
        timeout_ms      : 페이지 로드 타임아웃(ms)
        headless        : True면 브라우저 창 없이 실행

    Returns:
        중복 제거된 아티클 전체 URL 목록

    Raises:
        ImportError: playwright 미설치 시
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "Playwright가 설치되어 있지 않습니다.\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    targets = tab_urls if tab_urls is not None else _TOSS_TABS
    all_slugs: set[str] = set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            },
        )

        for tab_url in targets:
            pg = ctx.new_page()
            print(f"[toss] 탭 로드: {tab_url}")
            try:
                pg.goto(tab_url, wait_until="networkidle", timeout=timeout_ms)
            except Exception as e:
                print(f"[SKIP] 탭 로드 실패: {tab_url} — {e}")
                pg.close()
                continue

            for page_idx in range(max_pages_per_tab):
                slugs_before = len(all_slugs)
                new_slugs = _collect_slugs_on_page(pg)
                all_slugs.update(new_slugs)
                print(
                    f"  페이지 {page_idx + 1}: "
                    f"+{len(new_slugs - (all_slugs - new_slugs))}개 "
                    f"(누적 {len(all_slugs)}개)"
                )

                has_next = _try_go_next_page(pg, timeout_ms)
                if not has_next:
                    print(f"  → 마지막 페이지 도달 (다음 버튼 없음)")
                    break
                if len(all_slugs) == slugs_before + len(new_slugs) == slugs_before:
                    # 페이지 전환 후 새 slug가 0개면 종료
                    print(f"  → 새 아티클 없음, 수집 종료")
                    break
            else:
                print(f"  → max_pages_per_tab({max_pages_per_tab}) 도달")

            pg.close()

        browser.close()

    return [f"{_TOSS_ARTICLE_PREFIX}/{slug}" for slug in sorted(all_slugs)]


# ── 네이버 D2 URL 수집 ───────────────────────────────────────────────────────
_NAVER_D2_LIST_API = "https://d2.naver.com/api/v1/contents"
_NAVER_D2_CATEGORY_HELLOWORLD = 2   # 기술 블로그 (Hello World)
_NAVER_D2_CATEGORY_NEWS = 3         # D2 News


def fetch_naver_d2_urls(
    max_pages: int = 20,
    category_id: int = _NAVER_D2_CATEGORY_HELLOWORLD,
    page_size: int = 20,
    timeout: int = 10,
) -> list[str]:
    """
    네이버 D2 REST API로 아티클 URL을 수집한다.

    페이지 번호는 0-indexed.  max_pages=0 이면 마지막 페이지까지 전부 수집.

    Args:
        max_pages   : 수집할 최대 페이지 수 (0 = 전체)
        category_id : 2 = Hello World(기술블로그), 3 = D2 News
        page_size   : 페이지당 항목 수 (최대 20 권장)
        timeout     : HTTP 타임아웃(초)

    Returns:
        중복 제거된 아티클 전체 URL 목록
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    urls: list[str] = []
    page = 0

    while True:
        resp = requests.get(
            _NAVER_D2_LIST_API,
            params={"categoryId": category_id, "page": page, "size": page_size},
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        for post in data.get("content", []):
            post_url = post.get("url", "")          # 예: /helloworld/7997284
            if post_url:
                urls.append(f"https://d2.naver.com{post_url}")

        # 마지막 페이지 판별: 'next' 링크가 없으면 끝
        has_next = any(
            link.get("rel") == "next"
            for link in data.get("links", [])
        )
        page += 1
        if not has_next:
            break
        if max_pages and page >= max_pages:
            break

    return list(dict.fromkeys(urls))   # 순서 유지 중복 제거


# ── 카카오 테크 블로그 URL 수집 ──────────────────────────────────────────────
_KAKAO_LIST_API = "https://tech.kakao.com/api/v2/posts"
_KAKAO_POST_BASE = "https://tech.kakao.com/posts"

# 수집 대상 카테고리 코드 (categories API 기준)
_KAKAO_CATEGORY_CODES = ["blog"]


def fetch_kakao_article_urls(
    category_codes: list[str] | None = None,
    max_pages: int = 20,
    timeout: int = 10,
) -> list[str]:
    """
    카카오 테크 블로그 REST API로 아티클 URL을 수집한다.

    카카오 블로그는 Nuxt SSR + REST API 구조이므로
    Playwright 없이 requests만으로 전체 목록을 수집할 수 있다.

    API: GET /api/v2/posts?page={page}&code={category_code}
         → { totalPageCount, postList: [{ id, title, ... }] }

    Args:
        category_codes : 수집할 카테고리 코드 목록 (None 이면 기본 ['blog'])
        max_pages      : 카테고리당 최대 페이지 수 (0 = 전체)
        timeout        : HTTP 타임아웃(초)

    Returns:
        중복 제거된 아티클 전체 URL 목록
    """
    if category_codes is None:
        category_codes = _KAKAO_CATEGORY_CODES

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://tech.kakao.com/blog/",
    }
    seen: set[str] = set()
    urls: list[str] = []

    for code in category_codes:
        page = 1
        while True:
            resp = requests.get(
                _KAKAO_LIST_API,
                params={"page": page, "code": code},
                headers=headers,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            post_list = data.get("postList", [])
            if not post_list:
                break

            for post in post_list:
                post_url = f"{_KAKAO_POST_BASE}/{post['id']}"
                if post_url not in seen:
                    seen.add(post_url)
                    urls.append(post_url)

            total_pages = data.get("totalPageCount", 1)
            if page >= total_pages:
                break
            if max_pages and page >= max_pages:
                break
            page += 1

    return urls


# ── CLI 간단 테스트 ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    use_js = "--js" in sys.argv

    if use_js:
        print("=== 토스 아티클 URL 수집 (Playwright) ===")
        toss_urls = fetch_toss_article_urls_js(headless=True)
    else:
        print("=== 토스 아티클 URL 수집 (정적) ===")
        toss_urls = fetch_toss_article_urls()
    print(f"토스 수집 URL 수: {len(toss_urls)}")
    for u in toss_urls[:3]:
        print(f"  {u}")

    print()
    print("=== 네이버 D2 URL 수집 (API) ===")
    naver_urls = fetch_naver_d2_urls(max_pages=30)
    print(f"네이버 D2 수집 URL 수: {len(naver_urls)}")
    for u in naver_urls[:3]:
        print(f"  {u}")

    print()
    print("=== 카카오 테크 URL 수집 (API) ===")
    kakao_urls = fetch_kakao_article_urls(max_pages=30)
    print(f"카카오 수집 URL 수: {len(kakao_urls)}")
    for u in kakao_urls[:3]:
        print(f"  {u}")

    all_tech_urls = toss_urls + naver_urls + kakao_urls
    with open("all_tech_urls.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(all_tech_urls))
    print(f"\n전체 URL {len(all_tech_urls)}개 → all_tech_urls.txt 저장 완료")

    # 개별 아티클 크롤링 테스트
    print()
    test_urls = [
        "https://toss.tech/article/firesale-system",
        "https://d2.naver.com/helloworld/7997284",
        "https://tech.kakao.com/posts/817",
    ]
    for result in crawl_many(test_urls):
        print(f"\n{'='*60}")
        print(f"URL    : {result.url}")
        print(f"제목   : {result.title}")
        print(f"추출법 : {result.source}")
        print(f"본문   : {result.content[:300]}...")
