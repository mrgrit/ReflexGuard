# ReflexGuard

MaleCNS 커넥톰을 기반으로 초파리 신경회로에서 배운 충돌 회피 기술을 전동휠체어의 생체모방 안전 보조에 적용하는 프로젝트입니다.

이 저장소는 대회 제출용 보안판입니다. **Phase 3: 영상 인코더·mock 뇌 연결·공유 제어**를 구현했습니다.
실제 뇌 시뮬레이션과 관제 기능은 이후 단계에서 구현합니다.

## 개발 시작

OS만 설치된 새 VM은 [부트스트랩 안내](docs/bootstrap.md)를 따라 한 번에 구성할 수 있습니다.
저장소가 이미 있다면 일반 사용자로 `bash scripts/bootstrap.sh`를 실행합니다.

Ubuntu 22.04 / Python 3.10 환경에서 다음을 실행합니다.

```bash
cd ~/work/reflexguard
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
pre-commit install
scripts/security_check.sh
```

Bandit, Semgrep, pip-audit, pre-commit, cyclonedx-bom, pip-tools는 pipx로 각각 설치합니다.
잠금 파일 변경 시 `pip-compile --generate-hashes --allow-unsafe requirements.in`을 사용합니다.
현재 requirements에는 FastAPI, HTTPX, Pydantic, Uvicorn과 검사 의존성이 포함됩니다.
Semgrep 규칙 및 취약점 데이터 조회에는 인터넷 연결이 필요합니다.

## 환경 검증

설치 버전, 실행 결과와 공식 출처는 [환경 보고서](docs/environment.md)에 기록합니다.
Docker 그룹 변경은 완전히 로그아웃한 후 다시 로그인하면 현재 세션에도 적용됩니다.

## Mock 뇌 서버

[Phase 1 실행 안내](docs/phase1.md)에 따라 로컬 인증서와 환경변수를 준비한 후 실행합니다.

```bash
set -a
source .env
set +a
scripts/run_mock_brain.sh
```

별도 터미널에서 동일한 환경변수를 읽고 `scripts/smoke_brain.sh`로 health → session → step을 호출합니다.
서버는 `127.0.0.1:8443`에 바인딩하며 모든 요청에 mTLS와 Bearer 토큰을 요구합니다.

개발 규칙은 [AGENTS.md](AGENTS.md)를 따릅니다. 현재 화면 조종과 SSH 실행은 [Phase 3 안내](docs/phase3.md)를 따릅니다. `scripts/check_pipeline.sh`로 mock 뇌와 복도 3종을 검증합니다. 다음 단계는 Phase 4의 관제 서버입니다.

커넥톰 기준은 **MaleCNS v1.0**입니다. [데이터 기준](docs/malecns.md)과 [현재 개발 계획](docs/development_plan.md)을 따릅니다. 실제 데이터/가중치는 아직 다운로드·연결하지 않았으며 현재 시뮬레이션은 mock 뇌를 사용합니다.
