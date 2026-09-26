# ReflexGuard

**현재 개발 버전: 0.8.2 — MaleCNS 실시간 회로·회피 주행·통합 설정**

초파리 신경회로에서 배운 충돌 회피 기술을 전동휠체어의 생체모방 안전 보조에 적용하는 프로젝트입니다. 사용자가 운전하고 위험 상황에서만 시스템이 개입합니다. 이 저장소는 대회 제출용 보안판입니다.

실제 MaleCNS v1.0의 **LPLC2→DNp01 축소 회로(187뉴런·185간선)**를 LIF로 실행합니다. GUI 기본값은 로컬 CPU이며, `real` 프로필로 외부 Thor GPU를 선택할 수 있습니다. 규칙 기반 mock도 별도 모드로 유지합니다. 전체 뇌나 생리학적으로 검증된 모델이 아니며, 현재 검증 범위는 Webots 시뮬레이션입니다.

## 현재 기능

- 카메라 루밍 → mTLS 뇌 API → 히스테리시스 디코더 → 공유 제어 → Webots 모터
- 서명·SHA-256 검증 모델/침묵 목록, 세션별 상태·역할·소유권·시간/자원 제한
- 복도 3종, SSH 배치 실행과 충돌·주행 거리·무조작 검증
- HTTPS 보호자 대시보드, bcrypt 로그인·잠금·세션·역할별 접근
- HMAC 원격 정지/속도 제한·재전송 방어, 판단 로그 체인 검증·권한별 내보내기
- 뇌 통신 단절 시 감속 정지 고정, 관제 실패 시 정지 고정

## 사이트 접속과 초기 계정

아래 화면은 하나의 관제 사이트이며 같은 계정으로 로그인합니다. 관제는 `0.0.0.0:8444`에서 수신합니다. 아래는 현재 개발 VM 주소이며 같은 네트워크의 다른 PC에서도 접속합니다. 새 설치에서는 `.env.control`의 접속 주소와 해당 IP/DNS의 인증서를 설정하세요. [외부 접속·인증서·계정 안내](docs/access.md).

| 화면 | 주소 | 주요 기능 |
|---|---|---|
| 로그인 | https://192.168.0.149:8444/login | 계정 로그인 |
| 관제 대시보드 | https://192.168.0.149:8444/ | 상태·원격 정지·속도 제한·판단 로그·사용자 관리 |
| 주행 설정 | https://192.168.0.149:8444/settings/control | 속도·루밍 민감도·정지/조향 임계값 |
| MaleCNS LIVE | https://192.168.0.149:8444/activity/seat-a | 뉴런 187개 발화·연결·위험 출력·주행 판단 |

초기 아이디는 **`admin`**, 비밀번호는 초기화할 때 **설치별로 무작위 생성**됩니다. 고정 공통 비밀번호는 없습니다. 서버에서 프로젝트 루트의 `.env.admin`을 열어 `REFLEXGUARD_ADMIN_PASSWORD` 값을 확인하세요. 이 파일과 실제 비밀번호는 Git에 포함하지 않습니다.

```bash
cd ~/work/reflexguard
cat .env.admin  # 본인 터미널에서만 확인; 출력 공유 금지
```

비밀번호 분실·잠금 복구가 필요할 때는 `scripts/reset_admin.sh` 실행 후 `.env.admin`을 다시 확인합니다. 파일만 편집해도 DB 비밀번호는 바뀌지 않습니다. 최초 설치·역할별 권한·SSH 계정과의 차이는 [접속 안내](docs/access.md)에 정리했습니다.

## 주행 설정과 시연

운영자·관리자는 관제의 **주행 설정** (`/settings/control`)에서 속도, 정지·조향 임계값, 루밍 민감도와 평활 시간을 저장·복원할 수 있습니다. 저장값은 같은 VM의 Webots를 다시 시작할 때 적용됩니다. 사용자 설정은 별도 주행 검증이 필요합니다.

인자 없이 `scripts/run_webots.sh`를 실행하면 **60m × 10m 시연 복도**가 열립니다. 기본 요청 속도는 **4.0m/s**, 시연 설정 상한은 6.0m/s입니다. 가까운 장애물·회피 조향 중에는 2.0m/s 이하로 낮추고 제동 여유를 함께 검사합니다. 기존 시험 월드 3종은 0.6m/s 상한을 유지합니다. 박스 3종·횡단 보행자 2명·3m 통로를 배치하고 전후방 및 구간별 관람 카메라를 추가했습니다. 4방향·두 높이 거리 센서와 휠 오도메트리로 빈 공간을 찾아 우회합니다. 신경회로는 위험 출력을, 로컬 회피기는 조향을 맡습니다. [설정·시연 안내](docs/control_settings.md)를 참고하세요.

## MaleCNS 실시간 시각화

관제의 **MaleCNS 실시간 신경회로 보기**를 누릅니다. 기본 장치에서는 `https://192.168.0.149:8444/activity/seat-a`입니다. 실제 뉴런 ID·연결, 187개 계산 발화율, 좌우 루밍, DNp01 출력, 최종 주행 판단과 최근 이력을 함께 표시합니다. 모델/가중치가 일치할 때만 실제 회로를 켜며 mock·수신 지연은 구분합니다. [시각화 안내](docs/neural_activity.md) · [실제 GPU 실행 화면](docs/logs/malecns-live.png).

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

# 터미널 2: VMware 데스크톱 — 동일한 서명 MaleCNS 회로를 VM CPU에서 실행
scripts/run_webots.sh

# 외부 GPU 경로를 선택할 때만 VPN과 터널을 준비
# REFLEXGUARD_BRAIN_PROFILE=real scripts/run_webots.sh
```

GUI 기본 프로필은 `local`이며 mock이 아닙니다. 같은 서명 MaleCNS 가중치를 NumPy로 계산하고 mTLS를 사용합니다. GPU는 `real`, 가짜 뇌는 `mock`으로 명시합니다. 주행 중 자동 프로필 전환은 없습니다.

터널 접속 값은 Git에서 제외된 `.env.gpu`, 실제 뇌 토큰·인증서는 `.env.brain-client`에 있습니다. 이미 localhost:18443 터널이나 관제가 실행 중이면 중복 실행하지 않습니다. 3D 화면을 클릭하고 방향키로 조종합니다. 시연 월드는 가능한 경로로 우회 후 사용자 진행 방향으로 돌아오며, 공간이 없으면 정지합니다. 기존 3개 회귀 월드는 위험 정지 후 키를 놓아 중립으로 돌아갑니다. 통신 실패·원격 정지는 문제를 해결한 뒤 시뮬레이션을 다시 시작해야 합니다. 시작 스크립트는 mTLS 상태를 확인하고, 실제 뇌 연결이 없으면 설치된 터널 서비스를 시작한 뒤 재확인합니다. 실패하면 멈춘 Webots 창을 열지 않고 종료합니다. 터널 설치와 `BRAIN FAILURE` 복구는 [연결 복구 안내](docs/brain_connection.md)를 참고하세요.

대시보드는 `https://192.168.0.149:8444/login`입니다. 개발 CA를 신뢰 등록한 브라우저에서 접속합니다. 초기 관리자 계정은 `.env.admin`에 있으며 **이 파일을 편집해도 DB 비밀번호는 바뀌지 않습니다**. 복구는 `scripts/reset_admin.sh`를 실행합니다. 비밀번호는 UTF-8 12..72바이트입니다. 보호자 연결과 운영 절차는 [Phase 4](docs/phase4.md)를 참고하세요.

GPU 없이 mock으로 실행하려면 별도 터미널에서 다음을 실행한 뒤 `REFLEXGUARD_BRAIN_PROFILE=mock scripts/run_webots.sh`을 실행합니다.

```bash
set -a
source .env
set +a
scripts/run_mock_brain.sh
```

GUI 기본 프로필은 local이며, 프로필을 지정하지 않은 배치 실행은 mock입니다. 실제 뇌 연결 실패를 자동으로 mock 성공 응답으로 대체하지 않습니다. 정지 후 명시적으로 프로필을 선택하고 새 세션으로 시작합니다.

## 검증 결과와 재실행

```bash
scripts/e2e.sh real  # GPU 계약·복도 3종·무조작·단절·관제 정지·로그 검증
scripts/e2e.sh mock  # 시험 전용 mock을 직접 시작/종료하므로 기존 mock은 종료할 것
scripts/security_check.sh  # 정적 검사 + VM/GPU 잠금 감사 + pytest
```

0.7.0 기준 실제 모델과 mock 모두 복도 3종에서 충돌 0회, 의미 있는 주행, 통신 오류 0회로 통합 시험을 통과했습니다. 무조작 시험은 개입 0회, 원격 정지는 약 0.31m 주행 후 모터 출력 0과 감사 체인 유효를 확인했습니다. GPU 계산과 CPU 기준 발화 결과도 일치했습니다. 실패했던 초기 보정 및 VPN 시간 초과도 기록했습니다.

0.8.0의 회피·시각화 시험과 통신 실패 기록은 [시연 시험 보고서](docs/demo_report.md)에 별도로 기록합니다.

결과는 제한된 시뮬레이션 조건의 재현 기록이며 실제 휠체어 안전·제동 거리 보증이 아닙니다. [통합 시험 보고서](docs/test_report.md), [보정 기록](docs/calibration.md), [뉴런 근거](docs/neurons.md), [성능](docs/brain_perf.md)을 확인하세요.

## 문서와 다음 버전

- [변경 이력](CHANGELOG.md), [현재 계획](docs/development_plan.md), [MaleCNS 출처](docs/malecns.md)
- [사이트 외부 접속·인증서·초기 계정](docs/access.md)
- [위협 모델](docs/threat_model.md), [KISA 27항목 매핑](docs/kisa_mapping.md), [서비스 개요](docs/service_overview.md)
- [VM SBOM](docs/sbom.json), [GPU 잠금 SBOM](docs/sbom-gpu.json), [라이선스 고지](THIRD_PARTY_NOTICES.md)

VM Python 35개 패키지와 GPU 애플리케이션 잠금을 별도로 관리합니다. NVIDIA 기본 이미지 전체 취약점 검사까지 완료했다는 뜻은 아닙니다. `scripts/generate_sbom.sh`와 `.venv/bin/python scripts/render_security_docs.py`로 관련 문서를 재생성합니다.

첫 시뮬레이션 버전을 마친 다음, **Jev로 감속·정지·좌/우 회피·사용자 명령 유지 중 안전한 행동을 선택하는 확장**을 진행할 계획입니다. Jev의 구체적 모델/API는 다음 버전에서 확정합니다. Attack Lab은 별도 저장소이며 현재 제출용 저장소에 취약 기능을 넣지 않습니다.
