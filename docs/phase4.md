# Phase 4 — 관제 서버와 보호자 대시보드

FastAPI·Jinja2·SQLAlchemy·SQLite 관제를 구현했다. 현재 뇌는 `mock-rules-v1`이며 실제 MaleCNS 모델은 아직 연결 전이다.

## 로컬 실행

프로젝트 루트에서 `.venv` 의존성을 `requirements.txt --require-hashes`로 설치한 환경을 사용한다.

1. 최초 한 번 `scripts/init_control.sh`를 실행한다. 기존 파일을 덮어쓰지 않고 `.env.control`, `.env.admin`, `control.db`를 만든다. 모두 Git에서 제외한다. `.env.admin`의 초기 관리자 계정으로 로그인한다. 이 파일은 서비스가 읽지 않는다.
2. 뇌 서버: `set -a; source .env; set +a; scripts/run_mock_brain.sh`
3. 관제 서버: `scripts/run_control_server.sh`
4. 화면 시뮬레이터: `scripts/run_webots.sh corridor_basic`
5. VMware 데스크톱 브라우저에서 `https://localhost:8444/login`으로 접속한다. 먼저 `certs/ca.crt` 개발 CA를 신뢰 저장소에 등록한다. 인증서 검증을 끄지 않는다. 개발 인증서는 7일 유효하므로 만료 시 새 디렉터리에 발급하고 `.env` 경로를 바꾼다.

SSH 원격 브라우저는 로컬 포트 포워딩을 사용할 수 있다. 서버는 127.0.0.1에만 바인딩하며 방화벽 포트를 개방하지 않는다.
관리자는 대시보드에서 보호자 계정을 생성한 뒤 반환된 사용자 ID로 `seat-a`를 지정한다. 사용자 역할 변경·비활성화도 대시보드에서 가능하며 기존 세션을 폐기한다.
`.env.control`은 한 VM의 시연용 설정이다. 별도 장비에서는 관제 서버에 전체 장치 목록·감사 키를, 휠체어에는 자기 장치 토큰·원격 서명 키만 제공한다. 관제 감사 키를 휠체어에 배포하지 않는다.

## 인증·권한과 원격 명령

- 비밀번호 bcrypt(cost 12), UTF-8 12..72바이트. 5회 실패하면 계정 15분 잠금, 출발지별 15분에 30회 로그인 한도.
- 서버 저장 세션: 랜덤 토큰의 SHA-256만 DB 저장, 30분 만료, 로그인 시 같은 사용자의 이전 세션 폐기.
- `__Host-` 쿠키: Secure·HttpOnly·SameSite=Strict·Path=/, Domain 없음. HTTPS/Host 검증. 모든 브라우저 변경 요청은 정확한 Origin과 CSRF 토큰 검증. 로그인도 별도 일회 세션 전 CSRF 쿠키 사용.
- guardian: 지정 휠체어 조회·로그 검증/내보내기·정지. operator: 전체 휠체어 조회·정지·속도 제한·침묵 요청. admin: 여기에 사용자·보호자 연결 관리.
- `/remote`는 stop과 speed_limit(0..0.6m/s)만 허용한다. 서버가 권한 검증 후 정규 JSON 본문에 HMAC-SHA256 서명한다. 본문에는 휠체어 ID·시작 식별자·secrets nonce·발급 UTC ms를 포함한다.
- 휠체어는 TLS 서버 인증, 장치별 Bearer 인증, HMAC, 대상, ±2초, nonce 재사용을 검사한다. 재시작마다 새로운 boot ID를 써 과거 명령이 다시 적용되지 않는다.
- 정지는 즉시 모터 출력 0으로 고정한다. 속도 명령은 좌·우 바퀴 속도를 함께 제한하고 정지 고정을 해제하지 않는다. 정지 후 현장 확인과 컨트롤러 재시작이 필요하다.
- 관제 연결을 사용하도록 설정했다면 연결 실패·잘못된 응답·서명 거부도 정지 고정한다. `REFLEXGUARD_CONTROL_URL`이 없는 기존 Phase 3 실행은 관제 미연결 구성이다.
- 뇌 통신은 기존 mTLS+토큰을 유지한다. operator 침묵 요청은 장치의 기존 뇌 세션으로 전달하며 최종 허용목록 검증은 뇌 서버가 한다. 대시보드의 queued 응답은 실제 침묵 성공을 뜻하지 않는다. 요청 실패 시 장치가 정지한다.
- 명령 전송은 2초 유효한 단일 대기함을 사용한다. 확인된 nonce는 적용 기록을 남긴다. 대기 중 stop을 speed_limit으로 덮어쓸 수 없다. 만료된 미확인 명령은 장치가 오류로 취급하여 정지한다.

## 판단 로그와 내보내기

장치 시작·명령 요청/적용과 주기별 판단(UTC/시뮬레이션 시각, 좌/우 루밍, 발화 뉴런, 모델 버전, 원인, 출력)을 저장한다. 장치별 sequence 중복·역전을 거부한다.
SQLAlchemy 바인딩과 SQLite `BEGIN IMMEDIATE`로 로그 추가·명령 확인·잠금 갱신을 직렬화한다. 로그별 이전 해시와 현재 SHA-256, 별도 감사 키의 HMAC, 체인 말단 개수를 보관한다.
`/logs/{chair_id}/verify`는 수정·중간 삭제·말단 삭제·키 없는 해시 재계산을 탐지한다. DB 전체를 과거의 유효한 스냅샷으로 돌리는 공격은 외부 체크포인트 없이는 탐지하지 못한다. 감사 키 탈취도 별도 운영 위협이다.
`/exports/{chair_id}`는 허가된 ID의 DB 레코드를 NDJSON으로 생성한다. 사용자 파일 경로를 받거나 파일을 열지 않는다.
템플릿 자동 이스케이프·CSP·no-store 적용. 상세 예외 종류는 서버 로그, 외부에는 일반 메시지만 반환한다.

## 검증과 한계

`tests/test_control_server.py`, `tests/test_control_device.py`: 권한/소유권, CSRF, 잠금, 세션 폐기, 서명 위조, nonce 재전송, 만료, 부팅 식별자, 장치 인증, 바퀴 속도 제한, 정지 고정, 로그 변조, 동시 append, SQL 특수문자, XSS 이스케이프, 실패/타임아웃을 시험한다.
`scripts/check_control.sh`: 임시 자격증명·임시 CA·임시 DB로 실제 HTTPS 로그인, 대시보드 정지 API, Webots 주행 후 정지, 장치 적용 확인, 로그 체인 검증을 자동 실행한다. 임시 서버는 종료하고 영구 운영 데이터를 사용하지 않는다. 브라우저 클릭 자체의 자동화가 아닌 같은 버튼 API 경로에 대한 통합 시험이다.
실측 결과는 `docs/logs/phase4-control.json`, Webots 원문은 `phase4-webots.log`, 전체 게이트는 `phase4-security.log`에 보관한다.

관제 브라우저와 장치는 HTTPS+각자의 인증을 사용한다. 브라우저에 클라이언트 인증서를 요구하지 않으며 뇌 API의 필수 mTLS와 구분한다. TLS 연결의 신뢰 경계는 테스트의 TestClient 가상 요청만으로 검증한 것이 아니라 실제 HTTPS 통합 실행으로도 확인한다.
Webots의 시뮬레이션 시간은 HTTP 대기 중 진행하지 않으므로 이 결과는 실제 하드웨어의 제동 거리나 실시간 응답 보증이 아니다. 실제 장비 배포 전 제어 루프 분리·네트워크 지연·부하·외부 감사 체크포인트 설계가 필요하다.

Bandit의 통합 시험용 subprocess import/호출 5곳은 고정 실행 파일·고정 모듈/월드·프로그램이 생성한 임시 경로만 쓰며 shell을 사용하지 않아, 코드 옆에 근거와 B404/B603 국소 예외를 기록했다. HTTP 서비스에는 프로세스 실행 경로가 없다. 전체 규칙을 끄지 않는다.

## 공식 구현 참고

- [SQLAlchemy SQLite 트랜잭션](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
- [Starlette 템플릿 자동 이스케이프](https://starlette.dev/templates/)
- [bcrypt 패키지·사용법](https://pypi.org/project/bcrypt/)


## 0.4.1 로그인 복구

`.env.admin`은 최초 계정/복구 자격증명을 기록한 파일이다. 서버가 로그인할 때 읽는 설정 파일이 아니며 비밀번호 검증은 SQLite의 bcrypt 해시를 사용한다. 파일 편집만으로 비밀번호를 변경할 수 없다.

프로젝트 루트에서 `scripts/reset_admin.sh`를 실행하면 새 무작위 비밀번호를 생성해 DB와 `.env.admin`(권한 0600)을 함께 갱신하고, admin 계정 잠금·기존 세션·로컬 접속 주소의 로그인 제한을 해제한다. 일반 사용자를 관리자로 승격시키지 않는다. 다른 휠체어 설정과 판단 로그는 유지한다. 실행 중인 서버 재시작은 필요하지 않다.
새 비밀번호는 이 파일의 `REFLEXGUARD_ADMIN_PASSWORD=` 뒤 값만 복사한다. `https://localhost:8444/login`을 새로 열어 CSRF 쿠키를 갱신한 다음 로그인한다.
직접 고른 비밀번호는 `REFLEXGUARD_ADMIN_PASSWORD` 환경변수로 전달할 수 있으며 UTF-8 12..72바이트를 검증한다. 명령행 인자나 로그에 비밀번호를 넣지 않는다. 로그인 화면에도 길이 조건을 표시한다.
