# ReflexGuard 위협 모델 — 0.5.0

검토일: 2026-09-24. 범위는 현재 Ubuntu VM의 mock·Webots·HTTPS 관제와 관리 스크립트다. 실제 MaleCNS 데이터, GPU LIF 서버, 실물 휠체어, Attack Lab은 현재 실행 범위에 포함되지 않는다. 보안 검사 통과는 위협이 모두 제거됐다는 뜻이 아니다.

## 자산·주체·신뢰 경계

| 자산 | 보호 목적 |
|---|---|
| 최종 좌/우 모터 명령, 정지 고정 상태 | 잘못된 입력·인증 실패가 이동 명령으로 이어지지 않도록 보호 |
| 비밀번호 해시, 세션, 장치/뇌 토큰, 원격 HMAC·감사 키, TLS 개인키 | 다른 사용자·장치의 권한 행사와 기록 위조 방지 |
| 카메라 프레임, 루밍·발화·판단·원격 명령 기록 | 변조/재전송 구분, 권한별 열람, 문제 재현 |
| 코드, requirements 잠금, 배포 자산, SBOM | 어떤 소프트웨어를 검증했는지 추적 |

주체는 보호자(guardian), 운영자(operator), 관리자(admin), 인증된 휠체어 장치, 인증된 뇌 클라이언트, 익명 네트워크/브라우저 요청자, 로컬 OS 운영자다. 동일 OS 계정이 `.env`·개인키·DB를 모두 읽고 수정할 수 있는 상황을 원격 인증만으로 방어한다고 가정하지 않는다.

```mermaid
flowchart LR
  Browser[보호자·운영자·관리자 브라우저] -->|HTTPS · 세션 · CSRF| Control[관제 서버]
  Control -->|SQLAlchemy 바인딩| DB[(SQLite · 판단 체인)]
  Camera[Webots 카메라·사용자 입력] --> Pipeline[인코더·디코더·공유 제어]
  Pipeline <-->|mTLS · Bearer · 200ms 제한| Brain[현재 mock 뇌 서버]
  Device[휠체어 장치 클라이언트] <-->|HTTPS · 장치 토큰 · HMAC 명령| Control
  Pipeline --> Guard[원격 명령 검증·속도 제한·정지 고정]
  Device --> Guard
  Guard --> Motors[Webots 좌·우 모터]
  Admin[로컬 OS 운영자] --> Secrets[환경변수·TLS 키·잠금 파일]
  Secrets -. 배포 신뢰 경계 .-> Control
  Secrets -. 배포 신뢰 경계 .-> Pipeline
```

현재 두 서버는 127.0.0.1에만 바인딩한다. SSH 포워딩·개발 CA를 사용하는 시연 구성이며 인터넷 운영 배포가 아니다. 브라우저/장치의 HTTPS와 뇌 API의 필수 mTLS를 구분한다. Webots 접촉 센서는 결과 측정용이고 회피 파이프라인의 입력으로 사용하지 않는다.

## 구성요소별 STRIDE

S=신원 위조, T=변조, R=행위 부인, I=정보 노출, D=서비스 거부, E=권한 상승. 각 셀의 화살표 뒤는 현재 대응 또는 남은 작업이다.

| 구성요소 | S | T | R | I | D | E |
|---|---|---|---|---|---|---|
| 브라우저·로그인·세션 | 계정/쿠키 탈취 → bcrypt·무작위 세션·만료 | CSRF/XSS → Origin·CSRF·자동 이스케이프·CSP | 로그인/사용자 관리의 완전한 감사 이벤트는 미구현 | Secure/HttpOnly·일반 오류, 로컬 브라우저 침해는 잔여 | 로그인 잠금·IP 한도, 잠금 유발·분산 요청은 잔여 | 역할은 DB에서 조회, 보호자 범위 검사, 세션 폐기 |
| 관제 API·DB·내보내기 | 장치 토큰을 휠체어 ID와 결합 | SQL 바인딩·sequence·해시 체인/HMAC | 명령 요청·적용 기록, 독립 제3자 부인방지 아님 | ID별 권한 확인, 파일 경로 미수용; DB 저장 암호화 미구현 | SQLite 직렬화·본문 크기 한도; 긴 업로드·로그 증가/내보내기 제한 미흡 | 원격 행동은 stop/speed_limit, 관리자 기능은 별도 역할 |
| 휠체어 장치·모터 | TLS 서버 검증·장치별 HMAC 키 | 대상·boot ID·±2초·nonce 검사 | 적용 nonce와 최종 출력 기록 | 장치별 자격증명 분리 필요, 로컬 데모는 단일 신뢰 호스트 | 관제 오류는 정지 고정; 네트워크 DoS가 운행 중단 가능 | 원격 명령은 운전 시작/정지 해제 불가, 침묵은 운영자 요청 |
| 뇌 API·mock 세션 | 실행기의 mTLS와 별도 Bearer 토큰 | Pydantic·t_ms 단조 증가·침묵 허용목록 | 모델 버전·발화 기록; 실제 커넥톰 근거는 아직 없음 | 세션 소유권·일반 오류·토큰 비노출 | 세션 수/수명, 요청 1초·16KiB, 클라이언트 총 200ms 제한 | 역할과 세션 소유자를 함께 확인 |
| 영상·인코더·공유 제어 | 현재 카메라는 로컬 시뮬레이터 신뢰 입력; 물리적 영상 교란 방어 없음 | 프레임 크기·시간·유한값 확인; 장면 조작은 감지 보장 못함 | 루밍/뉴런/결정 기록, 원본 영상은 보관하지 않아 재구성 제한 | 현재 영상은 저장·전송하지 않음; 판단 기록 보유 정책 필요 | 영상·뇌 오류는 정지; 실물 하드 실시간 제동 시험 없음 | 사용자의 중립 입력에 자율 이동을 생성하지 않고 정지/조향 한도 적용 |
| 로컬 배포·공급망 | 운영자/패키지 공급자 신뢰 필요 | 버전·해시 잠금·스캐너·SBOM; 모델 자산 서명은 계획 | Git 커밋·검증 로그·SBOM 입력 해시, 서명 릴리스는 미구현 | Git 제외·파일 0600; 호스트/백업/이미 공유된 비밀 관리 필요 | 잘못된 설정·만료 인증서는 운행 중단; 복구 절차 문서화 | 관리자 복구는 로컬 파일/DB 권한을 가진 운영자 전용, 웹 기능 아님 |

## 공격 경로와 검증 근거

| 경로 | 차단/감지 지점 | 주요 동작 시험 |
|---|---|---|
| 보호자가 다른 휠체어를 조회·정지 | `chair_for` 서버 소유권 | `test_guardian_scope_and_remote_roles` |
| 운영자 권한 없이 침묵/속도 제한 호출 | 역할 검사와 뇌 허용목록 | `test_operator_silence_and_pending_stop_priority`, `test_silence_role_permissions` |
| 원격 명령 본문 수정·재전송·지난 부팅 재사용 | `RemoteGuard.accept` | `test_remote_forgery_and_replay`, `test_expired_remote_fails_closed` |
| 다른 CA/호스트의 뇌 서버로 연결 | SSLContext·호스트 이름 | `test_foreign_server_ca_is_rejected`, `test_hostname_verification_is_enabled` |
| DB 판단 수정·말단 삭제·공격자 해시 재계산 | 체인/HMAC/말단 개수 | `test_audit_tampering` |
| 동시 판단으로 체인 분기·중복 sequence | 단일 DB 트랜잭션 | `test_concurrent_audit_append`, `test_device_token_binding_and_sequence` |
| 네트워크 단절 중 이전 속도로 계속 주행 | 뇌/관제 실패 고정 | `test_real_mtls_disconnect_causes_latched_gradual_stop`, `test_poll_failure_stops_and_latches` |
| 초기 계정 파일 수정으로 권한 우회 | DB 해시 검증, 로컬 복구 역할 제한 | `test_admin_recovery_cannot_promote_guardian` |

파일 경로와 테스트 전체 이름은 [KISA 매핑](kisa_mapping.md)에 기록했다. 검증은 단위·실제 TLS·Webots 통합으로 구분하며, 브라우저의 실제 클릭이나 실제 하드웨어 제동까지 자동 검증했다고 주장하지 않는다.

## 잔여 위험과 후속 조건

| 우선순위 | 남은 위험 | 이후 조치 / 완료 확인 |
|---|---|---|
| 높음: 실제 장비 전 필수 | HTTP 호출 중 Webots 시뮬레이션 시간이 멈추므로 실제 제어 주기/제동 거리 보장 없음 | 제어·통신 루프 분리, watchdog, 실제 장비 지연·제동 시험 |
| 높음: 네트워크 운영 전 | 관제 `Boundary` 본문 수신에 전체 타임아웃 없음; SQLite 전역 쓰기 잠금에서 bcrypt 계산 | 수신 deadline·인증 전 자원 한도, 로그인 부하/느린 본문 시험, 트랜잭션 경합 개선 |
| 높음: 운영 데이터 증가 전 | 로그/내보내기 무제한, 검증 시 전 체인 읽음 | 페이지·보유량·크기 한도, 보관/삭제 정책과 체인 checkpoint 설계 |
| 높음: 장비 분리 전 | 로컬 데모 `.env.control`에 서버/장치 키가 함께 있음 | 서버 감사 키와 각 장치 키 분리, 회전·폐기·최소 권한 배포 검증 |
| 중간 | 전체 DB를 유효한 과거 스냅샷으로 되돌리거나 감사 키까지 탈취하면 로컬 체인만으로 탐지 못함 | 외부 append-only checkpoint와 키 격리; rollback 시험 |
| 중간 | 파일/DB 평문 저장, 브라우저/OS 침해, 원격 정지 DoS·시계 이동 | 호스트/디스크·시간 동기화·관제 복구 정책, 침해 및 가용성 리허설 |
| 중간 | 긴 반복 비밀번호 수용, MFA·유출 목록 검사 없음, 일부 관리 행위 감사 누락 | 계정 정책·MFA·관리 감사 이벤트와 회귀 시험 |
| 모델 단계 필수 | 실제 MaleCNS 자산 검증·뉴런 선택·성능·서명 로더 미구현 | Phase 6 공식 출처/실제 해시/서명·검증된 변환·계약/월드 시험 |

이 표는 남은 일을 숨기지 않기 위한 개발 목록이다. 순위는 현재 팀의 정성 평가이며 대회 공식 취약점 점수나 의학적 위험 등급이 아니다.
