# AGENTS.md — ReflexGuard

## 프로젝트
- ReflexGuard: 초파리 신경회로(MaleCNS 커넥톰)에서 배운 충돌 회피 반사를 전동휠체어 안전 보조에 적용한 시스템.
- 평소에는 사용자가 조이스틱으로 운전하고, 충돌 직전에만 시스템이 감속·정지·회피한다 (공유 제어).
- 목적: 2026 SW개발보안 경진대회(소개딩) 트랙 A 출품. 심사는 "제거되지 않은 보안위협 수"를 센다.


## 커넥톰 기준
- 기준 데이터는 MaleCNS v1.0 (`male-cns:v1.0`)이다. `config/malecns.json`, `docs/malecns.md`, `docs/development_plan.md`를 따른다.
- 공식 출처: https://male-cns.janelia.org/download/ . 데이터 라이선스는 CC-BY-4.0이다.
- 뉴런 ID·유형·좌우·전달물질·연결 가중치는 동일한 MaleCNS 릴리스에서 검증한다. 다른 데이터셋 ID나 가중치를 재사용하지 않는다.
- 원본 주석은 Feather로 읽고 스키마·참조 무결성을 검사한다. 시뮬레이션용 가중치는 검증·변환 후 서명된 safetensors/npz로 배포한다.
- 파일 SHA-256은 실제 다운로드 후 기록한다. 근거 없는 뉴런 ID, 가짜 해시·서명, 데이터 없는 실제 모델 표기를 만들지 않는다.
- 현재 mock의 가상 뉴런은 데이터셋 뉴런으로 취급하지 않는다. 기존 단계별 프롬프트의 데이터 소스 가정은 이 기준으로 대체한다.

## 저장소 구분 (가장 중요)
- 이 저장소(reflexguard)는 **대회 제출용 보안판**이다. 의도적 취약점, 공격 스크립트, 취약 모드 플래그를 절대 넣지 않는다.
- 취약판·공격 스크립트·Attack Lab은 별도 저장소 `reflexguard-lab`에만 둔다.

## 언어·스택
- Python 3.10 (Ubuntu 22.04 기본), 가상환경 `.venv`. 3.11 이상 전용 문법은 쓰지 않는다 (GPU 장비가 3.12여도 그대로 돌게).
- 웹은 FastAPI + Jinja2 + SQLAlchemy + SQLite.
- 영상: OpenCV, NumPy. HTTP 클라이언트: httpx. 스키마: pydantic.
- JavaScript는 대시보드 화면에 필요한 최소한만 쓰고, 로직은 서버(Python)에 둔다.

## 시큐어코딩 규칙 (KISA Python 시큐어코딩 가이드 2023 기준)
- eval, exec, pickle, marshal, shelve, yaml.load(비안전), subprocess의 shell=True 금지.
- 모델·가중치는 safetensors 또는 npz로만 로드하고, 로드 전 SHA-256 해시와 서명을 검증한다.
- SQL은 SQLAlchemy 파라미터 바인딩만 쓴다. 문자열 포맷으로 쿼리 조립 금지.
- 모든 외부 입력은 pydantic으로 타입·범위를 검증한다.
- 비밀번호는 bcrypt, 토큰·nonce는 secrets 모듈. random 모듈로 보안값 생성 금지.
- 비밀값은 환경변수(.env, 커밋 금지)로만. 코드·주석에 비밀값 금지.
- httpx는 verify=False 금지. 뇌 서버와는 mTLS로 통신한다.
- 템플릿은 자동 이스케이프 유지. |safe, Markup 사용 금지.
- 오류 응답에는 일반 메시지만 반환하고, 상세 내용은 서버 로그에 남긴다. debug=False.
- 파일 조회는 사용자 입력 경로를 쓰지 않고 ID → 경로 매핑으로만 한다.
- 로그인 시도 횟수 제한, 역할 기반 권한(guardian, operator, admin)을 적용한다.

## 품질 게이트 (커밋 전 반드시 통과)
- `scripts/security_check.sh`: Bandit, Semgrep, pip-audit, pytest 전부 통과해야 한다.
- 의존성은 버전과 해시를 고정한다 (requirements.txt, `--require-hashes`).
- 새 기능에는 테스트를 같이 작성한다.

## 작업 방식
- 버전 또는 개발 단계 완료 시 README.md, CHANGELOG.md, docs/development_plan.md와 관련 내부 문서를 같은 커밋에서 갱신한다. 변경 내용·실행 방법·검증 결과·남은 제한을 기록하고 실제 구현 상태와 일치시킨다.
- 작업은 SSH 세션에서 한다. 화면이 필요한 명령(Webots, glxinfo)은 `xvfb-run -a`로 가상 화면에서 실행하거나, 데스크톱에 로그인된 세션이 있으면 `DISPLAY=:0`을 붙인다.
- sudo, 패키지 설치, 파일 삭제, 네트워크 포트 개방은 실행 전에 명령을 보여주고 승인을 받는다.
- 모르는 버전·URL·뉴런 ID는 추측하지 말고 공식 문서나 저장소에서 확인한 뒤 출처를 남긴다.
- 줄바꿈은 LF. 커밋 메시지는 한국어로 "무엇을, 왜"를 쓴다.
- 오픈소스 라이선스(MIT, Apache-2.0, CC-BY 4.0)는 THIRD_PARTY_NOTICES.md에 기록한다.

## 표현 원칙
- "초파리가 운전한다", "초파리 뇌를 단 휠체어" 같은 표현을 코드·문서·UI 어디에도 쓰지 않는다.
- "초파리 신경회로에서 배운 충돌 회피 기술", "생체모방 안전 보조"로 표현한다.

## 뇌 API 계약 (진짜 뇌 서버와 가짜 뇌가 똑같이 따른다)
- GET  /v1/health → {"status":"ok","model_version":str,"weights_sha256":str}
- POST /v1/sessions → {"session_id":str}
- POST /v1/sessions/{id}/step
  요청: {"t_ms":int>=0, "dt_ms":int 1..100, "left_looming":float 0..1, "right_looming":float 0..1}
  응답: {"escape":float 0..1, "turn_left":float 0..1, "turn_right":float 0..1,
         "top_neurons":[{"id":str,"type":str,"rate_hz":float}], "model_version":str}
- POST /v1/sessions/{id}/silence (operator 이상, 허용목록 뉴런만, 최대 10개)
  요청: {"neuron_ids":[str]} → {"accepted":[str]}
- 모든 요청은 mTLS + API 토큰 헤더(Authorization: Bearer)를 요구한다.
