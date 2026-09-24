# Phase 0 환경 구축 결과

검증일: 2026-09-24 (Asia/Seoul). 작업 저장소: `~/work/reflexguard`.

## 기본 환경

| 항목 | 결과 |
|---|---|
| OS | Ubuntu 22.04.5 LTS |
| 아키텍처 / 가상화 | x86_64 / VMware |
| CPU | i7-11800H로 보고되는 가상 CPU 8개 |
| 메모리 | 15 GiB, 최초 점검 사용 가능 약 14 GiB |
| 디스크 | 루트 98 GiB, 설치 전 여유 약 80 GiB |
| Python | 3.10.12 |
| 데스크톱 OpenGL | SVGA3D, OpenGL 4.3, direct rendering Yes |

데스크톱 `DISPLAY=:0 glxinfo -B`는 SVGA3D 및 OpenGL 4.3을 보고했습니다.
동시에 `Accelerated: no`, 비디오 메모리 1 MB가 보고되어 실제 3D 가속 성능을 입증한 것은 아닙니다.
Xvfb 배치 실행은 소프트웨어 렌더링 경고를 출력했지만 공식 샘플 시뮬레이션을 완료했습니다.
Phase 2 카메라·월드 통합 시 VMware 콘솔에서 화면 및 성능을 별도로 확인해야 합니다.

## 설치 버전

| 도구 | 버전 |
|---|---|
| Git | 2.34.1 |
| curl | 7.81.0 |
| GCC / Make | 11.4.0 / 4.3 |
| 시스템 pip / pipx | 22.0.2 / 1.0.0 |
| 프로젝트 venv pip / setuptools | 26.2.1 / 84.0.0 |
| pytest | 9.1.1 |
| Xvfb | Ubuntu 패키지 2:21.1.4-2ubuntu1.7~22.04.16 |
| Docker Engine | 29.8.1 |
| Docker Compose | 5.5.1 |
| Docker Buildx | 0.37.1 |
| Webots | R2025a |
| Bandit | 1.9.4 |
| Semgrep | 1.178.0 |
| pip-audit | 2.10.1 |
| pre-commit | 4.6.2 |
| cyclonedx-bom | 7.4.0 |
| pip-tools | 7.6.1 |
| ibus-hangul | 1.5.4-1build2 |

Docker는 공식 apt 저장소에서 설치했고, `rg`를 docker 그룹에 등록했습니다.
현재 로그인 세션의 그룹 갱신에는 로그아웃·재로그인이 필요하며, 검증에서는 `sg docker -c ...`를 사용했습니다.
프로젝트와 pipx 도구의 직접·전이 Python 의존성은 해시 잠금 파일로 설치했습니다.

Webots 설치 파일: `webots_2025a_amd64.deb` (162,910,802 bytes).
공식 HTTPS 릴리스에서 받은 파일의 SHA-256:

```text
6253d58c9b625a83ed7b62cd85a640fd0542d441c48d633a60932208b40b0657
```

이 해시는 이번 다운로드의 기록이며, 공급자가 별도 서명한 체크섬으로 검증했다는 뜻은 아닙니다.
부트스트랩의 후속 설치에서는 기록된 해시와 일치해야 진행합니다.

## 실행 검증

- Docker `hello-world` 정상 실행.
- `xvfb-run -a webots --version`: R2025a.
- 공식 `console.wbt`를 batch / fast / no-rendering 모드로 실행.
- 샘플 컨트롤러는 `wb_robot_step(4096)` 이후 정상 종료했고, 정상 종료 로그를 확인.
- GUI가 계속 열려 있는 Webots 프로세스는 제한 시간 후 종료: 프로세스 코드 124는 의도한 타임아웃.
- `scripts/bootstrap.sh`를 구성된 VM에서 끝까지 재실행해 설치 재적용, Docker/Webots, 품질 게이트 통과.
- 테스트 20개 통과: 비밀·상태 파일의 Git 제외, 부트스트랩 미리보기 무변경, 잘못된 경로·옵션의 설치 전 거부.

로그는 [logs](logs/)에 보관합니다. 부트스트랩 새 실행 로그는 `~/.cache/reflexguard-bootstrap/logs/`에 생성됩니다.
운영체제만 있는 두 번째 VM을 새로 만들어 검증하지는 않았습니다. 초기 설치 명령 실행과 현재 VM 재실행을 검증했습니다.
애플리케이션 기능은 아직 없으므로 보안 검사 결과는 Phase 0의 초기 파일·의존성에 대한 결과입니다.

## 다음 단계

Phase 1: 공통 뇌 API 스키마, mock 뇌 서버, mTLS 클라이언트, 인증서 생성, 계약 테스트.
현재 저장소에는 뇌 모델·주행 로직·관제 API가 없습니다.

## 공식 설치 출처

- [Docker Ubuntu 설치](https://docs.docker.com/engine/install/ubuntu/)
- [Docker 사용자 그룹 설정](https://docs.docker.com/engine/install/linux-postinstall/)
- [Webots R2025a 릴리스: Ubuntu 22.04 지원 deb](https://github.com/cyberbotics/webots/releases/tag/R2025a)
