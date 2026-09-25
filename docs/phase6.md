# 실제 MaleCNS 뇌 서버 설치·실행 — 0.7.0

실제 MaleCNS v1.0 연결 수로 구성한 축소 LIF 서버를 Thor에 배포하고 개발 VM의 동일 BrainClient로 검증했다. 모델 선정은 [neurons.md](neurons.md), 성능은 [brain_perf.md](brain_perf.md), 전체 시험은 [test_report.md](test_report.md)를 참조한다.

## 구성

GPU 컨테이너는 `reflexguard-brain` 전용 internal Docker 네트워크에만 연결한다. 호스트/외부 공개 포트는 없다. 비루트 UID, 읽기 전용 루트/모델/인증서, cap-drop, no-new-privileges, 8GiB·4CPU·256 PID 한도를 사용한다. Docker 제한은 공유 GPU 시간·통합 메모리 완전 격리를 뜻하지 않는다.

NVIDIA 기본 이미지 다이제스트는 `brain_server/Dockerfile`에 고정했다. 애플리케이션은 별도 clean venv를 사용하고 NVIDIA torch 패키지만 연결한다. 해당 torch의 NumPy ABI에 맞춰 GPU는 NumPy 1.26.4, 개발 VM은 2.2.6을 사용한다. 전이 의존성과 pip도 GPU 별도 requirements에 해시로 고정한다.

서버는 `/model/assets.lock`의 Ed25519 서명을 환경변수의 신뢰 공개키로 검사한다. 침묵 목록도 별도 서명과 manifest SHA-256을 확인한다. weights.npz는 SHA-256을 확인한 같은 bytes에서 숫자 int64 배열만 읽는다. 크기·압축 해제 크기·NPY 헤더 shape·dtype·간선·ID를 검증하여 object 역직렬화와 과도한 할당을 거부한다. 디렉터리에 들어 있는 공개키를 자동 신뢰하지 않는다.

## 새 장비 준비 순서

1. VM은 `scripts/bootstrap.sh`, JetPack이 준비된 Thor는 `scripts/bootstrap_gpu.sh`로 환경을 확인한다. `docker build -f brain_server/Dockerfile -t reflexguard-brain:phase6 .`로 서비스 이미지를 만든다. 태그는 개발 배포용이며 실행 스크립트는 해당 로컬 이미지 ID를 해석해서 실행한다.
2. [공식 다운로드](https://male-cns.janelia.org/download/)의 3종 Feather를 GPU의 `~/work/reflexguard-data/malecns-v1.0/`에 받는다. `brain_server/prepare.py`의 고정 SHA-256과 일치해야 변환된다. 출처를 바꿔 해시 검사를 우회하지 않는다.
3. 컨테이너의 clean Python에서 `python -m brain_server.prepare`를 실행한다. 환경 `REFLEXGUARD_SOURCE_DIR`은 읽기 전용 raw 마운트, `REFLEXGUARD_MODEL_DIR`은 새 출력 디렉터리를 가리킨다. GPU 연산 없이 변환할 수 있다. 기존 출력 디렉터리는 덮어쓰지 않는다.
4. VM에서 `scripts/gen_certs.sh certs/brain`을 실행한 뒤 `.venv/bin/python scripts/init_brain_deployment.py`를 한 번 실행한다. 초기화 도구는 `.env.model-signing`, `.env.brain-client`, `certs/brain/server.env`를 0600으로 만들며 기존 파일을 덮어쓰지 않는다. 초기화된 기존 배포에서는 재실행하지 않는다.
5. unsigned 산출물을 VM의 `.local-models/malecns-v1-lif-v1/`로 가져와 검토한다. 아래 명령으로 VM에서만 서명한다. weights.npz와 서명된 assets.lock/silence.json을 GPU `~/work/reflexguard-models/malecns-v1-lif-v1/`로 돌려보낸다.
6. `server.env`, `server.key`, `server.crt`, `ca.crt`만 GPU `~/work/reflexguard-secrets/brain/`에 전달한다(디렉터리 0700, 개인키/환경 파일 0600). CA 개인키·클라이언트 개인키·모델 서명 개인키는 전달하지 않는다. `bash scripts/run_brain_server.sh`로 시작한다. 실행 중인 같은 이름의 컨테이너가 있으면 먼저 점검하고 명시적으로 교체해야 한다.

```bash
set -a
source .env.model-signing
set +a
export PYTHONPATH=src:.
export REFLEXGUARD_MODEL_DIR="$PWD/.local-models/malecns-v1-lif-v1"
.venv/bin/python scripts/sign_model.py
```

## 다음 접속에서 실행

VPN에 접속하고 `.env.gpu`에 `REFLEXGUARD_GPU_HOST`, `REFLEXGUARD_GPU_USER`, `REFLEXGUARD_GPU_PORT`를 설정한다. 주소·계정·비밀번호를 Git에 넣지 않는다. 비밀번호는 이 파일에 저장할 필요가 없다. SSH 인증/호스트 키는 기존 운영 설정을 따른다.

```bash
# 터널이 끊어진 경우 별도 터미널에서 실행하고 유지
scripts/connect_gpu.sh

# 실제 GPU 모델 + Webots 화면 (VMware 데스크톱)
REFLEXGUARD_BRAIN_PROFILE=real scripts/run_webots.sh corridor_basic

# SSH에서 전체 리허설
scripts/e2e.sh real
scripts/e2e.sh mock
```

이미 localhost:18443 터널이 살아 있으면 새 터널을 중복 실행하지 않는다. `REFLEXGUARD_BRAIN_PROFILE=real`은 `.env.brain-client`를 사용한다. 기본값은 mock이고 관제 CA는 별도로 유지한다. GUI 실행은 `.env.control`이 있으면 관제에 연결하므로 `scripts/run_control_server.sh`도 실행되어 있어야 한다.

연결 실패는 정지 상태로 고정한다. 복구했다고 운전을 자동 재개하지 않는다. mock으로 전환할 때는 정지한 시뮬레이션을 종료하고 mock 서버를 시작한 다음 `REFLEXGUARD_BRAIN_PROFILE=mock scripts/run_webots.sh corridor_basic`으로 새 세션을 연다. 실제 뇌의 모델·세션·침묵 상태를 mock에 이어붙이지 않는다.

## 보안 검사 범위

`scripts/security_check.sh`는 VM 잠금과 GPU 애플리케이션 잠금을 모두 pip-audit한다. `docs/sbom-gpu.json`은 GPU 잠금 의존성 목록, `docs/logs/gpu-python-inventory.json`은 설치 메타데이터 목록(별도 공급되는 NVIDIA torch 포함)이다. `docs/gpu_provenance.json`은 이미지·잠금·모델·코드 해시를 연결한다. NVIDIA 기본 이미지 전체 OS와 vendor torch 개발 빌드의 취약점 0건을 입증하는 검사는 아니다. 외부 공개 운영 배포는 범위 밖이다.
