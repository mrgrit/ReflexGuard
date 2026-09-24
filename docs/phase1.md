# Phase 1: mock 뇌 API와 mTLS 클라이언트

이 구현은 생체모방 안전 보조 파이프라인을 연결하기 위한 **규칙 기반 mock**입니다.
실제 초파리 뉴런 ID나 신경망 가중치는 사용하지 않습니다.

## 구성

- `src/reflexguard/common/schemas.py`: 두 뇌 서버가 공유할 v1 계약. 엄격한 타입·범위, 유한 수, 추가 필드 거부.
- `common/config.py`: 환경변수와 인증서 파일 설정 검증. 잘못된 설정은 시작 전 실패하며 비밀값을 오류에 포함하지 않음.
- `mock_brain/app.py`: health, session, step, silence.
- `mock_brain/security.py`: 모든 HTTP 경로의 Bearer 인증, HTTPS 확인, 요청 본문 16 KiB 및 수신 1초 제한.
- `mock_brain/store.py`: 사용자별 세션 소유권, 시간 순서 검증, 세션 수·유휴 수명 제한.
- `mock_brain/__main__.py`: 클라이언트 인증서를 반드시 요구하는 TLS 서버 실행.
- `brain_client/client.py`: 비동기 HTTPX 클라이언트. 신뢰할 수 없는 응답은 예외로 전달.
- `scripts/gen_certs.sh`: 로컬 CA 및 서버·클라이언트 인증서 생성.
- `encoder`, `decoder`, `control`, `control_server`, `brain_server`, `webots`의 후속 구현용 디렉터리.

## 로컬 실행

먼저 저장소 루트에서 `.venv/bin/python -m pip install --require-hashes -r requirements.txt`로 의존성을 맞춥니다.

### 1. 인증서와 비밀 환경변수 준비

```bash
cd ~/work/reflexguard
scripts/gen_certs.sh
.venv/bin/python - <<'PY'
import json
import os
import secrets
import shlex

token = secrets.token_urlsafe(32)
values = {
    "REFLEXGUARD_BRAIN_TOKEN": token,
    "REFLEXGUARD_API_TOKENS": json.dumps([
        {"token": token, "subject": "local-wheelchair", "role": "operator"}
    ]),
    "REFLEXGUARD_BRAIN_URL": "https://localhost:8443",
    "REFLEXGUARD_TLS_CA": "certs/ca.crt",
    "REFLEXGUARD_TLS_SERVER_CERT": "certs/server.crt",
    "REFLEXGUARD_TLS_SERVER_KEY": "certs/server.key",
    "REFLEXGUARD_TLS_CLIENT_CERT": "certs/client.crt",
    "REFLEXGUARD_TLS_CLIENT_KEY": "certs/client.key",
    "REFLEXGUARD_MOCK_PORT": "8443",
}
descriptor = os.open(".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as output:
    for key, value in values.items():
        output.write(key + "=" + shlex.quote(value) + "\n")
print("Created .env without printing credentials.")
PY
```

이미 존재하는 `certs/`나 `.env`는 덮어쓰지 않습니다. `.env`와 `certs/`는 Git에서 제외됩니다.
개발용 CA의 유효기간은 30일, 서버·클라이언트 인증서는 7일입니다. 개인키 파일은 0600으로 생성합니다.
이 CA와 인증서는 로컬 개발용이며, 외부 GPU 서버의 인증서 운영은 Phase 6에서 별도로 구성합니다.

### 2. 서버 시작

```bash
cd ~/work/reflexguard
set -a
source .env
set +a
scripts/run_mock_brain.sh
```

지원하는 실행 경로는 이 스크립트(`python -m reflexguard.mock_brain`)입니다.
전송 계층의 `CERT_REQUIRED`가 실제 mTLS를 강제합니다. ASGI 앱을 임의의 다른 서버 설정으로 배포하면
동일한 TLS 보장이 생기는 것이 아니므로, 앱 모듈만 별도 Uvicorn 명령으로 띄우지 않습니다.
프록시 헤더를 신뢰하지 않으며 TLS 최소 버전은 1.2입니다. 기본 바인딩은 루프백입니다.

### 3. 별도 터미널에서 호출

```bash
cd ~/work/reflexguard
set -a
source .env
set +a
scripts/smoke_brain.sh
```

health → session 생성 → step 순서로 요청하고, 비밀값과 세션 ID를 제외한 health·step 결과를 JSON으로 출력합니다.
예제는 왼쪽 루밍 0.9, 오른쪽 0.1이므로 `escape > 0`, `turn_right > turn_left`가 됩니다.
서버는 종료할 때 Ctrl+C를 누릅니다. 인증서 또는 환경 설정이 없으면 시작이 실패합니다.

## 계약과 상태 규칙

| 경로 | 입력 | 출력 |
|---|---|---|
| GET `/v1/health` | 없음 | `status`, `model_version`, `weights_sha256` |
| POST `/v1/sessions` | 빈 본문 또는 `{}` | `session_id` |
| POST `/v1/sessions/{id}/step` | `t_ms >= 0`, `dt_ms 1..100`, 좌·우 루밍 `0..1` | `escape`, 좌·우 turn, `top_neurons`, `model_version` |
| POST `/v1/sessions/{id}/silence` | 중복 없는 `neuron_ids`, 최대 10개 | `accepted` |

모든 경로는 mTLS + `Authorization: Bearer ...`가 필요합니다. 스키마 오류는 422,
토큰 오류는 401, 역할 부족은 403입니다. 없는 세션과 다른 사용자 세션은 동일한 404입니다.
세션 생성 본문으로 소유자나 역할을 바꿀 수 없습니다. 토큰의 `subject`와 `role`만 사용합니다.

- 토큰: `secrets.token_urlsafe(32)`로 생성. 설정 스키마는 URL-safe 문자 32..256자를 허용하며 중복 토큰은 거부합니다.
- `guardian`, `operator`, `admin`은 자신의 세션을 생성하고 step 호출 가능. silence는 operator·admin만 가능.
- 같은 `subject`로 발급한 토큰들은 세션을 공유할 수 있습니다. 서로 다른 이용자에게 같은 subject를 부여하지 않습니다.
- 세션은 최대 256개, 유휴 900초 후 만료. 재시작하면 사라지는 메모리 상태입니다. 단일 프로세스로 실행합니다.
- 첫 step은 `t_ms=0` 가능. 이후에는 같은 세션에서 시간이 엄격히 증가해야 하며 재전송·역행은 409입니다.
- 식별자는 1..128자이며 영문·숫자·`_`·`-`로 시작합니다. 이후 `.`·`:`도 허용합니다. 경로 구분자와 점 경로는 허용하지 않습니다.
- mock의 허용 뉴런은 `mock-escape`, `mock-turn-left`, `mock-turn-right`입니다. 실제 생물학적 뉴런 ID가 아닙니다.
- silence는 현재 침묵 집합을 **대체**합니다. 빈 배열은 해제이며, 허용되지 않은 ID가 하나라도 있으면 전체 요청을 거부합니다.

## mock 계산

좌·우 루밍 중 큰 값이 0.35를 넘으면 escape가 `(peak - 0.35) / 0.65`로 증가합니다.
오른쪽 루밍이 크면 왼쪽 turn, 왼쪽이 크면 오른쪽 turn이 증가하며, 크기는 두 루밍의 양의 차이입니다.
양쪽이 같으면 turn은 0입니다. 출력은 모두 0..1이며, 가상 뉴런의 rate는 해당 출력 × 100 Hz입니다.
침묵된 가상 뉴런의 해당 출력과 rate는 0이 됩니다.

`model_version`은 `mock-rules-v1`입니다. health의 `weights_sha256`은 **정규화된 mock 규칙 정의의 SHA-256**입니다.
가중치 파일을 사용하지 않으므로 이 값을 실제 뇌 가중치의 검증 증거로 해석하지 않습니다.

## 클라이언트와 실패 처리

`BrainClient`는 `async with`와 `await`로 사용합니다. 환경변수 이름은 `.env.example`에 있습니다.
인증서 경로와 토큰을 환경에서 읽고, CA 및 호스트 이름 검증을 유지합니다.
HTTPS origin만 허용하고 프록시 환경변수와 HTTP 리다이렉트를 사용하지 않습니다.

HTTPX의 connect/read/write/pool 타임아웃을 각각 200 ms로 두고, 별도로 `asyncio.wait_for`를 이용해
전체 요청·본문 수신에도 200 ms의 취소 기한을 적용합니다. Python 스케줄링 및 취소 정리 시간 때문에 하드 실시간 보장은 아닙니다.
본문은 최대 64 KiB, 압축 응답은 거부하며 모든 정상 응답도 Pydantic 계약으로 다시 검증합니다.

접속·TLS·HTTP 오류, 기한 초과, 스키마 오류는 `BrainClientError`로 전달합니다. 자동 재시도나 mock 자동 전환은 하지 않습니다.
시간 초과 시 서버가 이미 해당 step을 처리했을 수 있으므로 같은 요청을 자동 재전송하지 않습니다.
Phase 3 공유 제어기는 이 예외를 받아 안전 정지를 수행해야 합니다. 아직 모터 제어는 구현하지 않았습니다.

## 검증

```bash
scripts/security_check.sh
```

최종 검증: **88개 테스트 통과**, Bandit 0건, Semgrep 0건, pip-audit 알려진 취약점 0건.
[검사 로그](logs/phase1-security.log)에 실행 결과를 보관합니다.

| 검증 항목 | 테스트 |
|---|---|
| 타입·범위·NaN/Infinity·추가 필드 | `test_schemas.py` |
| mock 반응·침묵·역할·소유권·세션 만료·오류 비노출 | `test_mock_brain.py` |
| HTTPS 설정·전체 기한·응답 검증·크기·압축·리다이렉트 거부 | `test_brain_client.py` |
| 실제 TLS 성공, 인증서 누락·다른 CA·호스트 이름 오류 거부 | `test_mtls_integration.py` |
| 인증서 + 토큰 모두 필요, 평문 거부, CLI smoke 성공 | `test_mtls_integration.py` |
| 개인키 권한 및 인증서 덮어쓰기 거부 | `test_mtls_integration.py` |

TLS 통합 테스트는 별도 프로세스와 루프백 TCP 소켓을 사용하고 종료 시 프로세스를 정리합니다.
새 테스트용 토큰과 CA를 매 실행 생성하며 운영 비밀값을 요구하지 않습니다.
테스트 실행 시 Starlette 1.7.0의 HTTPX TestClient 지원 폐기 예정 경고 1건이 있습니다.
경고를 숨기지 않았으며, 실제 HTTPX 클라이언트·mTLS 통신은 통과했습니다.

## 확인한 공식 자료

- [HTTPX SSL context와 클라이언트 인증서](https://www.python-httpx.org/advanced/ssl/)
- [HTTPX의 단계별 타임아웃 의미](https://www.python-httpx.org/advanced/timeouts/)
- [Python 3.10 asyncio.wait_for](https://docs.python.org/3.10/library/asyncio-task.html#asyncio.wait_for)
- [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/)
- Uvicorn 0.53.0 설치 패키지 `uvicorn/config.py`의 `create_ssl_context`와 `Config.load` 구현을 확인.
  [공식 소스 저장소](https://github.com/Kludex/uvicorn)
