# E2E Check Scenarios

## 1) RAG 기반 JD 분석
- 준비: FastAPI 서버 실행(`uvicorn backend.main:app --reload --port 8000`) 후 프론트 실행(`npm run dev`).
- 입력: 이력서 PDF 업로드, 회사 선택, JD 텍스트 입력.
- 기대 결과:
  - `Analyze Fit` 실행 후 점수/강점/약점/추천이 표시된다.
  - `Referenced Engineering Sources` 카드에 RAG 출처가 노출된다(벡터스토어가 비어있으면 미노출 가능).

## 2) RAG fallback 동작
- 준비: FastAPI 서버를 중지한 상태로 프론트만 실행.
- 입력: 동일하게 JD 분석 실행.
- 기대 결과:
  - 분석은 실패하지 않고 기존 LLM 기반 결과가 표시된다.
  - 출처 카드가 비어 있거나 표시되지 않는다.

## 3) 면접 꼬리질문 체인
- 준비: FastAPI + 프론트 실행.
- 입력: 인터뷰 시작 후 3턴 이상 답변 반복.
- 기대 결과:
  - 답변마다 피드백(accuracy/logic/suggestion)이 붙는다.
  - 다음 질문 생성 시 이전 질문 반복이 줄어든다(최근 5개 질문 회피).
  - 컨텍스트가 있을 때 질문이 회사 기술 맥락을 반영한다.

## 4) Tavily 실시간 검색 경로
- 준비: `TAVILY_API_KEY` 설정 후 FastAPI 재시작.
- 호출: `/api/realtime/search`에 최신 키워드 포함 질의 전송.
- 기대 결과:
  - `search_used: true`와 함께 결과 목록 반환.
  - Tavily 장애/미설정 시 `search_used: false`, `fallback_reason` 반환.

## 5) Agent 오케스트레이션 경로
- 호출: `/api/agent/brief`에 최신성 키워드 질의(예: "latest kubernetes release in 2026").
- 기대 결과:
  - `summary`에 RAG/Realtime 컨텍스트 요약이 포함된다.
  - `used_realtime_search`가 조건에 따라 true/false로 바뀐다.
  - 프론트 면접 체인에서 해당 `summary`를 질문/평가 컨텍스트로 사용한다.
