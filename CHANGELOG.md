# Changelog

이 문서는 프로젝트의 주요 변경 사항을 기록합니다.

## v0.1.1 - 2026-04-13

- Resume PDF 파싱 안정화: `pdf.js` worker 로딩 경로를 CDN에서 번들 경로로 전환
- PDF 문서 로딩 시 입력 타입을 `Uint8Array`로 명시해 호환성 강화
- E2E 시나리오 문서에 JD 테스트 템플릿과 실행 준비 절차 보강
