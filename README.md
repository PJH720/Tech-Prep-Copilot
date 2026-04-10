# Tech Prep Copilot

금융/핀테크 직무 면접을 준비하는 개발자를 위한 AI 코파일럿.  
국내 주요 기술 블로그(토스·네이버 D2·카카오)의 실전 아티클을 수집·벡터화하여  
RAG 기반으로 JD 분석, 역량 갭 진단, 기술 면접 시뮬레이션을 제공합니다.

---

## 아키텍처

```
크롤링 파이프라인 (로컬)              벡터 DB 구축 (Colab T4 GPU)
┌─────────────────────┐               ┌───────────────────────────┐
│ crawler.py          │               │ build_vectorstore_colab   │
│  · 토스 (정적/JS)   │──────────────▶│  · BAAI/bge-m3 임베딩     │
│  · 네이버 D2 API    │               │  · ChromaDB 저장           │
│  · 카카오 API       │               │  · chroma_db.zip 다운로드  │
└────────┬────────────┘               └──────────────────────────-┘
         │ all_tech_urls.txt                       │ chroma_db/
         ▼                                         ▼
┌─────────────────────┐               ┌───────────────────────────┐
│ run_filter_crawl.py │               │ React + Vite 프론트엔드    │
│  · 금융 키워드 필터  │               │  · JD 입력 / 이력서 업로드 │
│  · finance_tech_    │               │  · 역량 갭 리포트          │
│    content.json     │               │  · 면접 채팅 시뮬레이션    │
└─────────────────────┘               └───────────────────────────┘
```

---

## 빠른 시작

### 사전 요구사항
- Node.js 18+
- Python 3.11+

### 1. 저장소 클론 및 의존성 설치

```bash
git clone https://github.com/<your-id>/Tech-Prep-Copilot.git
cd Tech-Prep-Copilot

# 프론트엔드
npm install

# Python 파이프라인 환경
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 아래 항목 입력
```

| 변수 | 설명 |
|------|------|
| `OPENAI_API_KEY` | OpenAI API 키 (LLM 추론용) |
| `TAVILY_API_KEY` | Tavily 검색 API 키 |
| `GEMINI_API_KEY` | Gemini API 키 |
| `CHROMA_DB_PATH` | ChromaDB 경로 (기본: `./chroma_db`) |
| `EMBEDDING_MODEL_NAME` | 임베딩 모델 (기본: `BAAI/bge-m3`) |

---

## 데이터 파이프라인

### Step 1 — 기술 블로그 URL 수집

```bash
python utils/crawler.py
# → all_tech_urls.txt 생성
```

| 소스 | 방식 | 수집량 |
|------|------|--------|
| toss.tech | 정적 HTML / `--js` 옵션으로 Playwright | ~300개 |
| d2.naver.com | REST API (`/api/v1/contents`) | ~3,200개 |
| tech.kakao.com | REST API (`/api/v2/posts`) | ~450개 |

### Step 2 — 금융/핀테크 키워드 필터 크롤링

```bash
python utils/run_filter_crawl.py
# → finance_tech_content.json 생성
```

필터 키워드: `정산` `결제` `수수료` `원장` `이자` `회계` `세무` `부가세`  
`bank` `pay` `settlement` `billing` `transaction` `tax` `accounting` 등

### Step 3 — 벡터 DB 구축 (Google Colab T4 권장)

1. `utils/build_vectorstore_colab.ipynb` 를 Colab에 업로드
2. **Runtime > Change runtime type > T4 GPU** 설정
3. 셀 순서대로 실행 — `finance_tech_content.json` 업로드 포함
4. 마지막 셀에서 `chroma_db.zip` 다운로드
5. 프로젝트 루트에 압축 해제

```
Tech-Prep-Copilot/
└── chroma_db/          ← 여기에 압축 해제
    ├── chroma.sqlite3
    └── ...
```

> 로컬 CUDA GPU가 있으면 직접 실행도 가능합니다.
> ```bash
> python utils/build_vectorstore.py
> ```

---

## 프론트엔드 실행

```bash
npm run dev
# → http://localhost:3000
```

| 화면 | 설명 |
|------|------|
| JD 입력 | 채용공고 텍스트 붙여넣기 → 핵심 기술 스택 자동 추출 |
| 이력서 업로드 | PDF 업로드 → 경력 자동 파싱 |
| 역량 갭 리포트 | JD vs 이력서 비교 → 부족한 역량 시각화 |
| 면접 시뮬레이션 | 기술 블로그 RAG 기반 꼬리 질문 생성 |

---

## 프로젝트 구조

```
Tech-Prep-Copilot/
├── src/                              # React + TypeScript 프론트엔드
│   ├── components/
│   │   ├── InterviewChat.tsx         # 면접 시뮬레이션
│   │   ├── GapReport.tsx             # 역량 갭 리포트
│   │   ├── JDInput.tsx               # JD 입력
│   │   └── ResumeUploader.tsx        # 이력서 업로드
│   ├── services/aiService.ts         # AI API 호출
│   └── lib/store.ts                  # Zustand 전역 상태
│
├── utils/                            # Python 데이터 파이프라인
│   ├── crawler.py                    # URL 수집 + 본문 크롤링
│   ├── run_filter_crawl.py           # 키워드 필터 크롤링
│   ├── build_vectorstore.py          # 로컬 벡터 DB 구축
│   └── build_vectorstore_colab.ipynb # Colab용 벡터 DB 구축
│
├── chroma_db/                        # 벡터 DB (Colab에서 생성 후 배치, git 제외)
├── requirements.txt                  # Python 의존성
├── package.json                      # Node 의존성
└── .env.example                      # 환경 변수 템플릿
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | React 19, TypeScript, Vite, Tailwind CSS v4, Zustand |
| AI / RAG | LangChain 0.3, OpenAI GPT-4o-mini, BAAI/bge-m3 |
| 벡터 DB | ChromaDB |
| 크롤링 | requests, BeautifulSoup4, Playwright |
| 서버 | FastAPI, Uvicorn |
