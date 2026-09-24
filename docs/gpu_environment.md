# 외부 GPU 환경 — Phase 6 준비

2026-09-25 점검. GPU 환경과 데이터 준비 기록이며, 실제 뇌 API 구현 완료 보고서가 아니다.

| 항목 | 확인 결과 |
|---|---|
| 장비 | NVIDIA Jetson Thor / aarch64 |
| OS | Ubuntu 24.04.4 LTS, 커널 6.8.12-tegra |
| JetPack / Jetson Linux | 7.1-b112 / R38.4.0 |
| 호스트 Python | 3.12.3 (프로젝트 소스는 Python 3.10 호환 유지) |
| 드라이버 / CUDA Toolkit | 580.00 / 13.0.48 |
| 메모리 | 통합 메모리 122GiB, 최초 점검 시 available 약 71GiB |
| 저장 공간 | 최초 점검 시 루트 파일시스템 여유 약 702GB |
| NVIDIA Container Toolkit | 1.18.1-1, Docker nvidia 런타임 존재 |

Thor의 GPU와 CPU는 통합 메모리를 사용한다. `nvidia-smi`의 전체 메모리는 Not Supported로 표시되므로 별도 전용 VRAM 122GiB로 해석하지 않는다. CUDA에서 확인한 메모리와 버전은 [연산 점검 결과](logs/gpu-environment.json)에 있다. 메모리 여유는 실행 중인 다른 서비스에 따라 달라진다.

## 다시 구성하기

NVIDIA가 설치한 JetPack 7.1, Docker, NVIDIA Container Toolkit이 준비된 장비에서 저장소를 배치한 뒤 실행한다.
OS만 설치한 일반 ARM64 서버에 JetPack 드라이버를 설치하거나 플래싱하는 스크립트는 아니다.
Ubuntu 22.04 x86_64 개발 VM의 설치는 기존 [부트스트랩](bootstrap.md)을 사용한다.

```bash
bash scripts/bootstrap_gpu.sh --dry-run
bash scripts/bootstrap_gpu.sh
```

스크립트는 [NVIDIA Thor 공식 Docker 안내](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/0.1.0/setup_docker.html)의
`nvcr.io/nvidia/pytorch:25.08-py3` 중 ARM64 이미지를 다음 불변 다이제스트로 고정한다.

```text
nvcr.io/nvidia/pytorch@sha256:d724ba5b68075cd3b96eefbc510a45d36e60dd16fd70b217708625f1f4b37bc1
```

다이제스트는 NGC에서 조회한 플랫폼별 manifest이며 별도의 배포자 서명 검증을 뜻하지 않는다.
컨테이너의 CUDA 13.0/PyTorch 구성 근거는 [25.08 릴리스 노트](https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/rel-25-08.html)다.

임시 컨테이너는 현재 사용자 UID로 실행하며 파일시스템을 읽기 전용으로 두고, 네트워크·외부 포트·추가 capabilities를 사용하지 않는다. CPU 4개, 메모리 8GiB, 프로세스 256개를 한도로 둔다. 이는 컨테이너 자원 제한이며 다른 프로세스와의 GPU 연산 시간 격리 또는 통합 GPU 메모리의 엄격한 상한 보장은 아니다.

`scripts/check_gpu.py`는 CUDA 사용 가능 여부, 작은 dense 행렬 곱과 희소 행렬 곱을 기준값과 비교한다. GPU가 없는 경우 실패한다. 작은 희소 연산 시간은 **LIF 모델의 dt_ms=50 처리 성능이 아니다**. 기존 vLLM 등 다른 컨테이너의 설정·프로세스는 변경하지 않았다.

## 데이터와 남은 작업

MaleCNS 원본은 GPU 서버의 `~/work/reflexguard-data/malecns-v1.0/`에 별도로 보관한다. 원본·모델·접속 정보·인증서는 Git에 넣지 않는다.
원본 SHA-256과 Arrow 스키마 점검은 [데이터 점검 결과](logs/malecns-source-inspection.json)에 기록한다. 이 해시는 내려받은 내용의 식별값이며 원본 공급자가 공개한 서명/해시라고 주장하지 않는다.
`config/malecns.json`은 다운로드 계획 스키마로 유지한다. 실제 모델용 `assets.lock`과 서명된 가중치는 아직 생성하지 않았다.

다음 작업은 전체 참조 무결성·결측/전달물질 검증, 후보 회로 선정의 생리학적 근거, 서명된 가중치·허용목록, 세션별 LIF, mTLS API, GPU 자원/시간 제한, 50ms 성능, 실제 서버로 Webots 복도 3종 검증이다.
현 대시보드와 시뮬레이션은 계속 규칙 기반 mock을 사용한다.

현재 보안 게이트와 `docs/sbom.json`은 개발 VM의 애플리케이션 Python 환경을 검사한다. NVIDIA 컨테이너 전체 OS/Python 패키지 취약점 검사와 GPU 전용 SBOM은 아직 수행하지 않았으며, 이 이미지를 외부에 노출하는 서비스로 배포하지 않았다. 실제 서비스 이미지 생성 시 별도 잠금·SBOM·취약점 검사가 필요하다.

VPN은 사용자 지정 서버의 인증서를 지문으로 고정해 접속했고, SSH는 최초 연결 호스트 키를 저장해 이후 변경을 검증한다. 서버 주소·계정·비밀번호는 이 문서와 스크립트에 포함하지 않는다.

## 이번 실행 결과

- CUDA 사용 가능, PyTorch `2.8.0a0+34c6371d24.nv25.08`, CUDA 13.0, compute capability 11.0. dense/sparse 기준값 비교 모두 통과.
- CUDA가 보고한 순간 free 메모리는 약 2.16GiB였다. Linux의 reclaim 가능한 available 약 71GiB와 같지 않으므로 모델 메모리 예산은 별도 실측해야 한다.
- 주석 211,577행, 전달물질 1,835,518행, 연결 가중치 151,856,684행의 Arrow 스키마를 확인했다. 원본 파일 3개는 실제 SHA-256 계산을 완료했다.
- 주석의 `type` 열에서 LPLC2를 포함하는 185개 행을 확인했다. `bodyId`가 MaleCNS 식별자다. `flywireType` 등 원문 비교용 열의 이름은 스키마 기록에만 보존하며 외부 데이터셋 ID·가중치를 가져오지 않는다. 기능·회피 출력 매핑은 아직 검증하지 않았다.
- 개발 VM의 Bandit·Semgrep·pip-audit와 전체 253개 pytest 통과. [검사 원문](logs/v0.5.1-security.log). GPU 이미지 전체 취약점 통과를 뜻하지 않는다.
