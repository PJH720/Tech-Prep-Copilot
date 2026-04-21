"""
finance_tech_content.json → ChromaDB 벡터 저장소 구축

임베딩 모델: BAAI/bge-m3 (HuggingFace, 로컬 실행)
  - 한국어+영어 멀티링구얼, 8192 토큰 컨텍스트, T4에서 ~2.3GB 사용
  - 최초 실행 시 모델 자동 다운로드 (~2.3GB)

실행:
    python utils/build_vectorstore.py

필요 패키지:
    pip install langchain-huggingface sentence-transformers
"""

import json
import re
import os
import sys
from datetime import datetime
from urllib.parse import urlparse

import torch
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.schema import Document

load_dotenv()

# ── 설정 ─────────────────────────────────────────────────────────────────────
INPUT_FILE      = "finance_tech_content.json"
CHROMA_DIR      = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "finance_tech"
CHUNK_SIZE      = 800                  # 청크 최대 글자 수
CHUNK_OVERLAP   = 100                  # 청크 간 겹침 글자 수
EMBED_MODEL     = "BAAI/bge-m3"        # HuggingFace 멀티링구얼 임베딩 모델
DEVICE          = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE      = 64                   # T4 기준 적정값 (메모리 부족 시 32로 낮춤)


# ── 1단계: 텍스트 정제 ────────────────────────────────────────────────────────
def clean_text(text: str) -> str:
    # 마크다운 이미지/링크 제거  ![alt](url)  [text](url)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # 이미지 캡션 괄호 (너무 공격적으로 제거하지 않도록 한글 포함 여부 확인)
    text = re.sub(r'\[[^\]]{1,30}\]', '', text)          # [그림 1], [출처] 등 짧은 것만
    # 날짜 패턴
    text = re.sub(r'\d{4}[년.\-]\s*\d{1,2}[월.\-]\s*\d{1,2}일?', '', text)
    # URL 단독 줄
    text = re.sub(r'https?://\S+', '', text)
    # 공유/SNS 버튼 문구
    noise = ["공유하기", "복사하기", "카카오톡", "트위터", "페이스북", "링크드인", "목차로 이동"]
    for n in noise:
        text = text.replace(n, "")
    # 연속 공백·개행 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


# ── 2단계: 메타데이터 추출 ───────────────────────────────────────────────────
_DATE_PATTERNS = [
    r'(\d{4})[.\-년]\s*(\d{1,2})[.\-월]\s*(\d{1,2})',   # 2024.03.15 / 2024년 3월 15일
    r'(\d{4})-(\d{2})-(\d{2})',                           # 2024-03-15 (ISO)
]

def extract_date(text: str) -> str:
    """본문에서 첫 번째 날짜를 YYYY-MM-DD 형태로 추출. 없으면 빈 문자열."""
    for pat in _DATE_PATTERNS:
        m = re.search(pat, text)
        if m:
            y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
            try:
                datetime(int(y), int(mo), int(d))   # 유효성 확인
                return f"{y}-{mo}-{d}"
            except ValueError:
                continue
    return ""


def extract_source_domain(url: str) -> str:
    try:
        return urlparse(url).hostname.removeprefix("www.")
    except Exception:
        return ""


# ── 3단계: 문장 경계 인식 청킹 ───────────────────────────────────────────────
_SENTENCE_END = re.compile(r'(?<=[.!?。])\s+|(?<=\n)')

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    문장 끝(. ! ? 줄바꿈)을 경계로 청크를 나눈다.
    경계를 찾지 못하면 글자 단위로 fallback.
    """
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + size
        if end >= len(text):
            chunks.append(text[start:])
            break

        # size 위치 이전에서 가장 가까운 문장 경계 탐색
        segment = text[start:end]
        best_cut = -1
        for m in _SENTENCE_END.finditer(segment):
            best_cut = m.start()        # 계속 갱신 → 마지막(가장 뒤) 경계

        if best_cut > size // 2:        # 너무 앞에서 잘리면 글자 단위 fallback
            end = start + best_cut + 1

        chunks.append(text[start:end].strip())
        start = end - overlap           # overlap만큼 되돌아가서 문맥 연결

    return [c for c in chunks if len(c) > 30]   # 너무 짧은 조각 제거


# ── 4단계: Document 변환 ─────────────────────────────────────────────────────
def build_documents(data: list[dict]) -> list[Document]:
    docs: list[Document] = []

    for entry in data:
        url     = entry.get("url", "")
        title   = entry.get("title", "")
        content = entry.get("content", "")

        cleaned  = clean_text(content)
        pub_date = extract_date(cleaned)          # 정제 전 원본에서도 탐색
        if not pub_date:
            pub_date = extract_date(content)
        domain   = extract_source_domain(url)

        chunks = chunk_text(cleaned)
        total  = len(chunks)

        for i, chunk in enumerate(chunks):
            docs.append(Document(
                page_content=chunk,
                metadata={
                    "source":      url,
                    "title":       title,
                    "domain":      domain,
                    "pub_date":    pub_date,
                    "chunk_id":    i,
                    "chunk_total": total,
                },
            ))

    return docs


# ── 5단계: ChromaDB 저장 ─────────────────────────────────────────────────────
def save_to_chroma(docs: list[Document]) -> Chroma:
    print(f"임베딩 모델 로드 중: {EMBED_MODEL}  (device={DEVICE})")
    print("  ※ 최초 실행 시 모델 다운로드(~2.3GB)가 진행됩니다.")

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": DEVICE},
        encode_kwargs={
            "batch_size": BATCH_SIZE,
            "normalize_embeddings": True,   # 코사인 유사도 검색 최적화
        },
    )

    print(f"ChromaDB 저장 시작 ({len(docs)}개 청크) → {CHROMA_DIR}/")
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_DIR,
    )
    print(f"저장 완료: collection='{COLLECTION_NAME}', 경로='{CHROMA_DIR}/'")
    return vectorstore


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main() -> None:
    # 입력 파일 확인
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] {INPUT_FILE} 파일이 없습니다. run_filter_crawl.py 를 먼저 실행하세요.")
        sys.exit(1)

    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    print(f"입력 데이터: {len(data)}개 아티클 로드 완료")

    # Document 생성
    docs = build_documents(data)
    print(f"청킹 완료: {len(data)}개 → {len(docs)}개 청크")

    # 중간 확인용 JSON 저장 (선택)
    preview_path = "final_vector_data.json"
    with open(preview_path, "w", encoding="utf-8") as f:
        json.dump(
            [{"page_content": d.page_content, "metadata": d.metadata} for d in docs],
            f, ensure_ascii=False, indent=2,
        )
    print(f"중간 확인용 저장: {preview_path}")

    # ChromaDB 저장
    save_to_chroma(docs)


if __name__ == "__main__":
    main()
