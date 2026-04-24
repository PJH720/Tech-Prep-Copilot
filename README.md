# Tech Prep Copilot

금융/핀테크 직무 면접을 준비하는 개발자를 위한 AI 코파일럿.  
국내 주요 기술 블로그(토스·네이버 D2·카카오)의 실전 아티클을 수집·벡터화하여  
RAG 기반으로 JD 분석, 역량 갭 진단, 기술 면접 시뮬레이션을 제공합니다.

For English documentation, see [README.en.md](README.en.md).

---

## 데모 화면

### 사용자 플로우 (GIF)

<img src="docs/Screencast%20from%202026-04-23%2018-23-18-00.00.00.000-00.02.30.901.gif" alt="Tech-Prep Copilot 데모 GIF" width="560" />

> GitHub README는 GIF를 정적 이미지가 아니라 애니메이션으로 렌더링합니다.

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
└─────────────────────┘               │  · 페르소나 선택 면접관    │
                                      └───────────────────────────┘
                                                   ↕ REST API
                                      ┌───────────────────────────┐
                                      │ FastAPI 백엔드             │
                                      │  · RAG 검색               │
                                      │  · 페르소나 면접 생성      │
                                      │  · 답변 평가 + 피드백      │
                                      │  · LLM Failover (Gemini→   │
                                      │    OpenAI→Upstage)        │
                                      └───────────────────────────┘
```

---

## 빠른 시작

### 사전 요구사항
- Node.js 18+
- Python 3.11+ (Anaconda 환경 권장)

### 1. 저장소 클론 및 의존성 설치

```bash
git clone https://github.com/<your-id>/Tech-Prep-Copilot.git
cd Tech-Prep-Copilot

# 프론트엔드
npm install

# Python 백엔드 환경
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

| 변수 | 필수 | 설명 |
|------|------|------|
| `VITE_GOOGLE_API_KEY` | Gemini 사용 시 | Google AI Studio 키 — 프론트엔드 갭분석용 |
| `GOOGLE_API_KEY` | Gemini 사용 시 | 백엔드 전용 Gemini 키 (위와 동일 값) |
| `OPENAI_API_KEY` | OpenAI 사용 시 | 2순위 LLM 및 프론트 갭분석 |
| `UPSTAGE_API_KEY` | 선택 | 3순위 LLM ([Upstage Solar](https://developers.upstage.ai/), OpenAI 호환 API) |
| `UPSTAGE_MODEL` | 선택 | 기본 `solar-pro` |
| `LLM_PROVIDER_ORDER` | 선택 | 쉼표 구분 시도 순서, 기본 `gemini,openai,upstage` |
| `LLM_TIMEOUT_SEC` | 선택 | 프로바이더당 HTTP 타임아웃(초), 기본 `60` |
| `VITE_BACKEND_URL` | 선택 | FastAPI 주소 (기본: `http://localhost:8000`) |
| `TAVILY_API_KEY` | 선택 | 실시간 검색 보강용 |

> **백엔드 LLM**: `LLM_PROVIDER_ORDER` 순으로 호출하고, 장애·빈 응답 시 다음 프로바이더로 넘어갑니다.  
> 최소 **Gemini**(`GOOGLE_API_KEY`) · **OpenAI** · **Upstage** 중 하나만 설정돼 있어도 면접·RAG 쿼리 확장이 동작합니다.  
> **프론트 갭분석**은 여전히 `VITE_GOOGLE_API_KEY` 또는 `OPENAI_API_KEY`(브라우저)를 사용합니다.

### 2.5. 벡터 DB 설정 (빠른 시작)

프로젝트에 포함된 사전 빌드 벡터 DB를 사용합니다:

```bash
# 자동 설정: 백엔드 시작 시 data/chroma_db1.zip 이 있으면 chroma_db/ 에 자동 압축 해제됩니다.
# 수동 설정이 필요한 경우:
unzip data/chroma_db1.zip -d chroma_db
```

> **참고**: `chroma_db/` 디렉토리는 약 150MB로 git에서 제외됩니다.  
> 직접 벡터 DB를 구축하려면 아래 "데이터 파이프라인" 섹션을 참조하세요.

### 3. FastAPI 백엔드 실행 (면접 시뮬레이션 필수)

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

> 백엔드가 없으면 역량 갭 리포트만 동작하고 면접 시뮬레이션은 비활성화됩니다.  
> 백엔드 LLM은 `GET /api/health`의 `llm_*_configured` 필드로 키 설정 여부를 확인할 수 있습니다.

### 4. 프론트엔드 실행

```bash
npm run dev
# → http://localhost:3000
```

---

## 면접 시뮬레이션 기능 (v0.2)

### 페르소나 시스템

4가지 면접관 유형 중 선택 가능. 각 페르소나의 두 면접관이 질문·피드백을 **랜덤으로 번갈아** 진행합니다.

| 페르소나 | 면접관 A | 면접관 B | 특징 |
|----------|----------|----------|------|
| 🧊 나엄격 / 나친절 | 나엄격 (42세, 테크 리드) | 나친절 (32세, 시니어 개발자) | 압박 기술 검증 + 성장 코칭 |
| 📈 마계산 / 오네트 | 마계산 (45세, 사업전략 본부장) | 오네트 (35세, 창업가 출신 PM) | ROI 임팩트 + 비즈니스 확장 |
| 🏗️ 권스케일 / 이안정 | 권스케일 (45세, 인프라 아키텍트) | 이안정 (38세, 시니어 SRE) | 대규모 확장성 + SRE 실무 |
| 💻 박알고 / 최코치 | 박알고 (38세, FAANG 인터뷰어) | 최코치 (33세, 코딩 코치) | 알고리즘 압박 + CS 기초 |

---

## 데이터 파이프라인

### Step 1 — 기술 블로그 URL 수집

```bash
python utils/crawler.py
# → all_tech_urls.txt 생성
```

| 소스 | 방식 | 수집량 |
|------|------|--------|
| toss.tech | 정적 HTML / Playwright | ~300개 |
| d2.naver.com | REST API | ~3,200개 |
| tech.kakao.com | REST API | ~450개 |

### Step 2 — 금융/핀테크 키워드 필터 크롤링

```bash
python utils/run_filter_crawl.py
# → finance_tech_content.json 생성
```

### Step 3 — 벡터 DB 구축 (Google Colab T4 권장)

1. `utils/build_vectorstore_colab.ipynb` 를 Colab에 업로드
2. **Runtime > Change runtime type > T4 GPU** 설정
3. 셀 순서대로 실행 후 `chroma_db.zip` 다운로드
4. 프로젝트 루트에 압축 해제

```
Tech-Prep-Copilot/
└── chroma_db/
    ├── chroma.sqlite3
    └── ...
```

---

## 프로젝트 구조

```
Tech-Prep-Copilot/
├── src/
│   ├── components/
│   │   ├── InterviewChat.tsx         # 면접 시뮬레이션 (페르소나 랜덤 교체)
│   │   ├── PersonaSelector.tsx       # 면접관 페르소나 선택 UI
│   │   ├── GapReport.tsx             # 역량 갭 리포트
│   │   ├── JDInput.tsx               # JD 입력
│   │   └── ResumeUploader.tsx        # 이력서 업로드
│   ├── services/aiService.ts         # LLM 호출 (Gemini/OpenAI 자동 선택)
│   └── lib/store.ts                  # Zustand 전역 상태
│
├── backend/
│   └── main.py                       # FastAPI (페르소나 면접, RAG, Gemini/OpenAI)
│
├── utils/                            # 데이터 파이프라인
├── test_gemini.py                    # Gemini API 키 확인 스크립트
├── chroma_db/                        # 벡터 DB (git 제외)
├── requirements.txt
├── package.json
└── .env.example
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | React 19, TypeScript, Vite, Tailwind CSS v4, Zustand |
| AI / LLM | Gemini 2.5 Flash Lite (기본) / OpenAI GPT-4o-mini (fallback) |
| RAG | LangChain 0.3, BAAI/bge-m3, ChromaDB |
| 백엔드 | FastAPI, Uvicorn |
| 실시간 검색 | Tavily API (선택) |
| 크롤링 | requests, BeautifulSoup4, Playwright |

---

## 작동 확인용 스크린샷 (PNG)

![GAP 분석 전체 화면](docs/screenshots/gap-analysis-full.png)
