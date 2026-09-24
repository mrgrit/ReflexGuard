# 변경 이력

프로젝트 버전은 `src/reflexguard/__init__.py`의 `__version__`으로 관리한다.
여기서 버전은 ReflexGuard 애플리케이션 버전이며 MaleCNS 데이터 릴리스나 mock 모델 버전과 별개다.

## 0.4.0 — 2026-09-24

- HTTPS 관제 서버와 서버 렌더링 대시보드, bcrypt 로그인·잠금·CSRF·역할별 접근 제어 추가.
- HMAC 서명 원격 정지·바퀴 속도 제한, boot ID·시간·nonce 검증, 장치 인증과 정지 고정 추가.
- 판단/뉴런 로그, 해시 체인·HMAC·말단 검증, 권한별 NDJSON 내보내기 추가.
- 관리자 계정 초기화·사용자/보호자 관리, 운영자 뉴런 침묵 요청 추가.
- 실제 HTTPS→Webots 주행 중 원격 정지→로그 검증 자동화 추가. 최종 6.016초 시험에서 약 0.33m 주행 후 정지, 충돌 0회, 최종 출력 0, 감사 체인 검증 통과.
- 관제 사용 시 `.env.control` 설정과 HTTPS 신뢰 CA가 필요하다. 기존 Phase 3 구성은 관제 URL 없이 계속 실행된다. 정지 고정 해제는 현장 확인 후 컨트롤러 재시작으로 한다.
- 규칙 기반 mock을 사용한다. 실제 MaleCNS 시뮬레이션·외부 GPU 연결은 미구현이다.
- 실행/보안 설계/검증 제한: [Phase 4](docs/phase4.md). 전체 보안 검사 기록: [phase4-security.log](docs/logs/phase4-security.log).

## 이전 단계 — 애플리케이션 버전 미지정

- `103217c`: MaleCNS 기준 전환, Phase 3 카메라 인코더·디코더·공유 제어와 mock 통합 검증.
- `9e392e5`: Phase 2 Webots 휠체어·복도 3종·키보드/배치 실행.
- `252a9e1`: Phase 1 mTLS mock 뇌 API·클라이언트·보안 검사.

이전 단계에 소급해 릴리스 태그나 버전 번호를 부여하지 않는다.
