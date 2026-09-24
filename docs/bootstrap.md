# 새 Ubuntu VM 설치

대상은 Ubuntu **22.04 Desktop x86_64**, Python 3.10입니다. 외부 GPU 서버(Phase 6)용 설치가 아닙니다.
VMware 설정의 **Accelerate 3D graphics**는 호스트에서 켜야 합니다. VM 안의 스크립트로 이 설정을 바꾸지는 않습니다.

## OS만 설치된 경우

관리자 권한이 있는 일반 사용자로 로그인한 뒤 터미널에 아래 블록을 한 번 붙여넣습니다.
Ubuntu에 기본 포함된 Python 3로 HTTPS 다운로드하고, 성공한 경우에만 실행합니다.

```bash
bootstrap_file=$(mktemp --suffix=.sh) &&
python3 -c 'import sys, urllib.request; urllib.request.urlretrieve("https://raw.githubusercontent.com/mrgrit/reflexguard/main/scripts/bootstrap.sh", sys.argv[1])' "$bootstrap_file" &&
bash "$bootstrap_file"
```

시스템 설치를 위한 sudo 비밀번호는 로컬 터미널에 입력합니다. 스크립트나 로그에 비밀번호를 저장하지 않습니다.
인터넷 연결이 필요합니다. 기본 작업 경로는 `~/work/reflexguard`입니다.
설치 전에 내용을 확인하려면 마지막 줄을 `bash "$bootstrap_file" --dry-run`으로 바꿀 수 있습니다.

## 이미 저장소가 있는 경우

```bash
cd ~/work/reflexguard
bash scripts/bootstrap.sh
```

다른 경로는 `--prefix /absolute/path/reflexguard`로 지정합니다.
`sudo bash scripts/bootstrap.sh`로 실행하지 않습니다. 사용자 도구와 가상환경은 일반 사용자 소유로 설치해야 합니다.

## 설치 내용

- Git, curl, 빌드 도구, Python venv/pip, pipx, Xvfb, mesa-utils
- Docker 공식 apt 저장소의 Engine·Buildx·Compose, 현재 사용자의 docker 그룹 등록
- Webots R2025a: 공식 Ubuntu 22.04용 deb의 기록된 SHA-256을 검사한 후 설치
- Bandit, Semgrep, pip-audit, pre-commit, cyclonedx-bom, pip-tools: 도구별 pipx 환경과 전이 의존성 해시 잠금
- 프로젝트 `.venv`, 해시 고정 requirements, 커밋 전 검사 훅
- ibus-hangul: GNOME 데스크톱 세션이 있으면 기존 입력기를 유지하면서 한글 추가

반복 실행 시 apt는 설치 상태를 확인하며, 동일 Webots 버전은 다시 내려받지 않습니다.
Python 도구는 잠금 파일을 다시 적용합니다. 기존 Git 작업은 pull/reset/삭제하지 않습니다.
다른 저장소가 목적지에 있거나 충돌하는 Docker 패키지가 있으면 자동 제거하지 않고 오류로 종료합니다.
자동 커밋·push·재부팅·로그아웃은 하지 않습니다.

## 검증과 로그

설치 후 Docker hello-world, Xvfb Webots 공식 console 샘플, Bandit, Semgrep, pip-audit, pytest를 실행합니다.
로그 경로는 `~/.cache/reflexguard-bootstrap/logs/`입니다. 실패하면 성공 메시지 없이 종료합니다.
Webots 샘플 컨트롤러의 정상 종료 로그가 있어야 통과하며, 단순히 창이 살아 있는 것으로 통과시키지 않습니다.
GUI를 계속 열어 두는 Webots 프로세스는 테스트 제한 시간 이후 종료하므로 종료 코드 124가 기록될 수 있습니다.

Docker 그룹과 한글 입력을 반영하려면 완료 후 **로그아웃·재로그인**합니다.
한글/영문 전환은 Super(Windows)+Space입니다. SSH만 연결된 상태라면 한글 입력기는 설치만 하고,
데스크톱 로그인 후 Settings → Keyboard → Input Sources에서 Korean (Hangul)을 추가합니다.

Xvfb에서는 소프트웨어 렌더링 경고가 나올 수 있습니다. VMware GPU 가속은 데스크톱 터미널의
`glxinfo -B`로 별도 확인합니다. 운영 서비스나 외부 포트는 이 스크립트가 구성하지 않습니다.

Webots와 Python 도구는 고정 버전입니다. apt 시스템 패키지는 설치 시점의 공식 저장소 보안 업데이트를 받습니다.
Python 잠금은 Ubuntu 22.04의 Python 3.10에서 생성했으며 다른 Python 버전 재현은 이 단계의 검증 대상이 아닙니다.
Semgrep `p/python` 규칙과 취약점 데이터베이스는 검사 시점에 조회합니다.

## 공식 출처

- https://docs.docker.com/engine/install/ubuntu/
- https://docs.docker.com/engine/install/linux-postinstall/
- https://github.com/cyberbotics/webots/releases/tag/R2025a
- https://github.com/pypa/pipx
- https://github.com/jazzband/pip-tools
