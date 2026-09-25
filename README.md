# ReflexGuard

**현재 개발 버전: 0.7.0 — MaleCNS GPU 모델과 통합 리허설 완료**

초파리 신경회로에서 배운 충돌 회피 기술을 전동휠체어의 생체모방 안전 보조에 적용하는 프로젝트입니다. 사용자가 운전하고 위험 상황에서만 시스템이 개입합니다. 이 저장소는 대회 제출용 보안판입니다.

실제 MaleCNS v1.0의 **LPLC2→DNp01 축소 회로(187뉴런·185간선)**를 Thor GPU에서 LIF로 실행합니다. 규칙 기반 mock도 별도 모드로 유지합니다. 전체 뇌나 생리학적으로 검증된 모델이 아니며, 현재 검증 범위는 Webots 시뮬레이션입니다.

## 현재 기능

- 카메라 루밍 → mTLS 뇌 API → 히스테리시스 디코더 → 공유 제어 → Webots 모터
- 서명·SHA-256 검증 모델/침묵 목록, 세션별 상태·역할·소유권·시간/자원 제한
- 복도 3종, SSH 배치 실행과 충돌·주행 거리·무조작 검증
- HTTPS 보호자 대시보드, bcrypt 로그인·잠금·세션·역할별 접근
- HMAC 원격 정지/속도 제한·재전송 방어, 판단 로그 체인 검증·권한별 내보내기
- 뇌 통신 단절 시 감속 정지 고정, 관제 실패 시 정지 고정

## 설치

개발 VM은 Ubuntu 22.04 / Python 3.10 / Webots R2025a로 검증했습니다. OS만 설치한 VM은 [부트스트랩 안내](docs/bootstrap.md)에 따라 `bash scripts/bootstrap.sh`를 실행합니다. GPU는 [환경 준비](docs/gpu_environment.md) 및 [실제 뇌 설치·실행](docs/phase6.md)을 따릅니다.

```bash
cd ~/work/reflexguard
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
pre-commit install
scripts/security_check.sh
```

Bandit·Semgrep·pip-audit·pre-commit·cyclonedx와 pip-tools는 pipx 환경을 사용합니다. 잠금 갱신은 `pip-compile --generate-hashes --allow-unsafe requirements.in`입니다. GPU는 NVIDIA ABI 때문에 별도 `brain_server/requirements.txt`를 사용합니다. 보안 규칙/취약점 조회는 네트워크가 필요합니다.

## 직접 실행

이미 구축된 VM에서는 아래 명령으로 이어서 사용할 수 있습니다. 처음 설치할 때만 [Phase 1](docs/phase1.md)에 따라 `.env`와 TLS를 만들고 `scripts/init_control.sh`로 관제를 초기화합니다.

```bash
# 터미널 1: HTTPS 관제
scripts/run_control_server.sh

# 터미널 2: VPN 연결 후 GPU SSH 터널이 끊겼을 때만 실행
scripts/connect_gpu.sh

# 터미널 3: VMware 데스크톱에서 실제 뇌 연결 Webots
REFLEXGUARD_BRAIN_PROFILE=real scripts/run_webots.sh corridor_basic
```

터널 접속 값은 Git에서 제외된 `.env.gpu`, 실제 뇌 토큰·인증서는 `.env.brain-client`에 있습니다. 이미 localhost:18443 터널이나 관제가 실행 중이면 중복 실행하지 않습니다. 방향키로 조종하고 위험 정지 후에는 키를 놓아 중립으로 돌아갑니다. 통신 실패·원격 정지는 문제를 해결한 뒤 시뮬레이션을 다시 시작해야 합니다.

대시보드는 `https://localhost:8444/login`입니다. 개발 CA를 신뢰 등록한 브라우저에서 접속합니다. 초기 관리자 계정은 `.env.admin`에 있으며 **이 파일을 편집해도 DB 비밀번호는 바뀌지 않습니다**. 복구는 `scripts/reset_admin.sh`를 실행합니다. 비밀번호는 UTF-8 12..72바이트입니다. 보호자 연결과 운영 절차는 [Phase 4](docs/phase4.md)를 참고하세요.

GPU 없이 mock으로 실행하려면 별도 터미널에서 다음을 실행한 뒤 `REFLEXGUARD_BRAIN_PROFILE=mock scripts/run_webots.sh corridor_basic`을 실행합니다.

```bash
set -a
source .env
set +a
scripts/run_mock_brain.sh
```

기본 프로필은 mock입니다. 실제 뇌 연결 실패를 자동으로 mock 성공 응답으로 대체하지 않습니다. 정지 후 명시적으로 프로필을 선택하고 새 세션으로 시작합니다.

## 검증 결과와 재실행

```bash
scripts/e2e.sh real  # GPU 계약·복도 3종·무조작·단절·관제 정지·로그 검증
scripts/e2e.sh mock  # 시험 전용 mock을 직접 시작/종료하므로 기존 mock은 종료할 것
scripts/security_check.sh  # 정적 검사 + VM/GPU 잠금 감사 + pytest
```

실제 모델과 mock 모두 복도 3종에서 충돌 0회, 의미 있는 주행, 통신 오류 0회로 통합 시험을 통과했습니다. 무조작 시험은 개입 0회, 원격 정지는 약 0.31m 주행 후 모터 출력 0과 감사 체인 유효를 확인했습니다. GPU 계산과 CPU 기준 발화 결과도 일치했습니다. 실패했던 초기 보정 및 VPN 시간 초과도 기록했습니다.

결과는 제한된 시뮬레이션 조건의 재현 기록이며 실제 휠체어 안전·제동 거리 보증이 아닙니다. [통합 시험 보고서](docs/test_report.md), [보정 기록](docs/calibration.md), [뉴런 근거](docs/neurons.md), [성능](docs/brain_perf.md)을 확인하세요.

## 문서와 다음 버전

- [변경 이력](CHANGELOG.md), [현재 계획](docs/development_plan.md), [MaleCNS 출처](docs/malecns.md)
- [위협 모델](docs/threat_model.md), [KISA 27항목 매핑](docs/kisa_mapping.md), [서비스 개요](docs/service_overview.md)
- [VM SBOM](docs/sbom.json), [GPU 잠금 SBOM](docs/sbom-gpu.json), [라이선스 고지](THIRD_PARTY_NOTICES.md)

VM Python 35개 패키지와 GPU 애플리케이션 잠금을 별도로 관리합니다. NVIDIA 기본 이미지 전체 취약점 검사까지 완료했다는 뜻은 아닙니다. `scripts/generate_sbom.sh`와 `.venv/bin/python scripts/render_security_docs.py`로 관련 문서를 재생성합니다.

첫 시뮬레이션 버전을 마친 다음, **Jev로 감속·정지·좌/우 회피·사용자 명령 유지 중 안전한 행동을 선택하는 확장**을 진행할 계획입니다. Jev의 구체적 모델/API는 다음 버전에서 확정합니다. Attack Lab은 별도 저장소이며 현재 제출용 저장소에 취약 기능을 넣지 않습니다.
