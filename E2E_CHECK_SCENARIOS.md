# E2E Check Scenarios

## 1) RAG 기반 JD 분석
- 준비: `.venv_pptx`가 활성화되어 있다면 `deactivate`로 비활성화한 뒤, FastAPI 서버를 miniconda 기본 파이썬으로 실행(`python -m uvicorn backend.main:app --reload --port 8000`)하고 프론트를 실행(`npm run dev`).
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

#### JD Test 양식
```
[포지션] 백엔드 소프트웨어 엔지니어 (Fintech Payments)

[회사 소개]
우리는 대규모 트래픽 환경에서 빠르고 안전한 결제/정산 인프라를 구축하는 핀테크 기업입니다.
사용자에게 신뢰할 수 있는 금융 경험을 제공하기 위해 안정성, 보안, 데이터 기반 의사결정을 중요하게 생각합니다.

[주요 업무]
- 결제, 정산, 송금, 한도/리스크 관리 등 핵심 금융 도메인 백엔드 서비스 개발
- MSA 환경에서 API 설계/개발 및 서비스 간 데이터 일관성 보장
- 대용량 트래픽 처리 성능 개선 및 장애 대응 체계 고도화
- 거래 데이터 파이프라인 구축 및 모니터링 지표 설계
- 보안/컴플라이언스 요구사항(접근 제어, 감사 로그, 개인정보 보호) 반영
- Product, Data, Frontend, QA와 협업하여 기능 출시 리드

[자격 요건]
- 백엔드 개발 경력 3년 이상 또는 그에 준하는 역량
- Java/Kotlin 또는 Python 기반 서버 개발 경험
- REST API, RDBMS(MySQL/PostgreSQL), 트랜잭션 처리에 대한 이해
- 분산 시스템 환경에서 장애 분석 및 문제 해결 경험
- 테스트 코드 작성(Unit/Integration) 및 코드 리뷰 문화에 익숙하신 분
- 논리적 커뮤니케이션과 문서화 역량

[우대 사항]
- 결제/정산/회계/리스크 등 금융 도메인 경험
- Kafka, Redis, Kubernetes, Docker 운영 경험
- 대규모 트래픽 서비스 성능 최적화 경험
- 모니터링/관측성 도구(Prometheus, Grafana, Datadog 등) 활용 경험
- 개인정보보호 및 전자금융 관련 규제 대응 경험
- 클라우드(AWS/GCP) 환경 운영 경험

[기술 스택]
- Language: Kotlin, Java, Python
- Framework: Spring Boot, FastAPI
- Infra: AWS, Kubernetes, Docker
- Data: MySQL, PostgreSQL, Redis, Kafka
- DevOps: GitHub Actions, Terraform, ArgoCD

[협업 방식]
- 작은 단위의 배포와 빠른 피드백을 지향합니다.
- 코드 품질(리뷰/테스트/리팩터링)과 사용자 임팩트를 동시에 중요하게 생각합니다.
- 실패를 투명하게 공유하고 재발 방지를 시스템으로 해결합니다.
```

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
