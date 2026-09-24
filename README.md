# ReflexGuard

**현재 개발 버전: 0.5.0 — Phase 5 보안 문서·KISA 매핑·SBOM**

MaleCNS 커넥톰을 기반으로 초파리 신경회로에서 배운 충돌 회피 기술을 전동휠체어의 생체모방 안전 보조에 적용하는 프로젝트입니다. 평소에는 사용자가 운전하고 위험 상황에서만 시스템이 개입합니다.
이 저장소는 대회 제출용 보안판입니다. 현재 시뮬레이션은 **규칙 기반 mock**을 사용하며 실제 MaleCNS 데이터·가중치는 아직 연결하지 않았습니다.

## 현재 기능

- mTLS 뇌 API·클라이언트, 카메라 루밍 인코더, 히스테리시스 디코더와 공유 제어
- Webots 휠체어 및 복도 3종, SSH 배치 실행·충돌/거리 기록
- HTTPS 보호자 대시보드, bcrypt 로그인·잠금·세션·역할별 권한
- 휠체어별 HMAC 원격 정지·속도 제한, 재전송 방어, 통신 실패 시 정지
- 뉴런 발화·판단 로그, 해시 체인/HMAC 무결성 검증, 권한에 따른 NDJSON 내보내기

## 개발 환경

Ubuntu 22.04 / Python 3.10 / Webots R2025a를 기준으로 검증했습니다.
OS만 설치된 새 VM은 [부트스트랩 안내](docs/bootstrap.md)를 따릅니다. 저장소가 있다면 `bash scripts/bootstrap.sh`로 구성할 수 있습니다.

```bash
cd ~/work/reflexguard
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
pre-commit install
scripts/security_check.sh
```

보안 도구와 pip-tools는 pipx로 설치합니다. 잠금 갱신은 `pip-compile --generate-hashes --allow-unsafe requirements.in`을 사용합니다.
핵심 의존성은 FastAPI·HTTPX·Pydantic·Uvicorn·NumPy·OpenCV·SQLAlchemy·Jinja2·bcrypt입니다.
Semgrep 규칙 및 취약점 데이터 조회는 네트워크가 필요합니다. 설치·그래픽 확인 결과는 [환경 보고서](docs/environment.md)에 있습니다.

## 실행

[Phase 1 안내](docs/phase1.md)로 `.env`와 로컬 인증서를 준비합니다. 관제 초기화는 한 번만 실행하며 기존 파일을 덮어쓰지 않습니다.

```bash
scripts/init_control.sh
```

초기 관리자 계정은 Git에서 제외된 `.env.admin`에 저장됩니다. **이 파일을 편집해도 DB 비밀번호는 변경되지 않습니다.** 로그인 복구는 `scripts/reset_admin.sh`를 실행한 뒤 갱신된 파일의 비밀번호로 다시 로그인합니다. 비밀번호는 UTF-8 12..72바이트이며 `1`은 허용되지 않습니다. 다음 명령은 각각 별도 터미널에서 실행합니다.

```bash
# 1. mock 뇌 서버
set -a
source .env
set +a
scripts/run_mock_brain.sh

# 2. HTTPS 관제 서버
scripts/run_control_server.sh

# 3. VMware 데스크톱의 Webots 화면
scripts/run_webots.sh corridor_basic
```

브라우저 주소는 `https://localhost:8444/login`입니다. 로컬 개발 CA를 브라우저에 신뢰 등록한 뒤 접속합니다. 원격 접속은 SSH 포트 포워딩을 사용하며 서버는 localhost에만 바인딩합니다.
보호자 지정, 원격 정지 후 재시작, 인증서 갱신과 장비별 환경변수 분리는 [Phase 4 안내](docs/phase4.md)를 따릅니다.

## 검증

```bash
scripts/check_pipeline.sh  # mock + 복도 3종 + 무조작 시험
scripts/check_control.sh   # 임시 HTTPS 관제 + Webots 주행 후 원격 정지 + 로그 검증
scripts/security_check.sh  # Bandit + Semgrep + pip-audit + pytest
```

Phase 3 복도 3종의 각 10초 시험에서 충돌 0회를 확인했습니다. Phase 4 통합 시험에서는 약 0.33m 주행한 뒤 서명된 원격 정지로 모터 출력 0, 충돌 0회와 로그 무결성을 확인했습니다.
세부 조건과 제한은 [보정 기록](docs/calibration.md), [관제 검증](docs/phase4.md), `docs/logs/`에 보관합니다. 이 시뮬레이션 결과는 실제 하드웨어의 안전성·제동 거리 보증이 아닙니다.

## 개발 기록과 다음 단계

- [변경 이력](CHANGELOG.md): 버전별 변경·검증·호환성
- [현재 계획](docs/development_plan.md): 다음 단계는 외부 GPU 장비의 Phase 6 MaleCNS 실제 모델 구현
- [MaleCNS 기준](docs/malecns.md): v1.0 데이터 출처와 실제 모델 구현 계획
- [개발 규칙](AGENTS.md), [외부 라이선스](THIRD_PARTY_NOTICES.md)

버전 갱신 시 README·CHANGELOG·관련 내부 문서를 같은 커밋에서 갱신합니다.


## 보안 검토 자료

[위협 모델](docs/threat_model.md), [KISA 2023 가이드 매핑](docs/kisa_mapping.md), [서비스 개요서 초안](docs/service_overview.md), [SBOM](docs/sbom.json)을 제공합니다.
KISA 관련 27개 항목은 함수·동작 테스트와 연결하고 부분 적용·잔여 위험을 명시했습니다. SBOM은 현재 Python 가상환경의 32개 패키지이며 OS/Webots/GPU 모델 전체 목록이 아닙니다.
`scripts/generate_sbom.sh`로 SBOM과 입력 해시를, `.venv/bin/python scripts/render_security_docs.py`로 매핑 표를 다시 생성합니다. 의존성/버전 변경 후 문서 일치 검사가 통과해야 합니다. [Phase 5 범위와 검증](docs/phase5.md)을 참조하세요.
