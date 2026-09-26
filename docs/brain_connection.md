# 0.8.1 — BRAIN FAILURE와 시연 연결 복구

`BRAIN FAILURE`는 뇌 통신 실패 후 안전 정지가 고정됐다는 뜻이다. `CONTACTS 0`은 충돌 횟수 0으로 별도 지표다. 연결을 복구해도 이미 멈춘 세션은 방향키로 정지를 해제하지 않으며 새 세션을 시작한다.

2026-09-26 장애에서는 GPU 컨테이너와 VPN은 정상이나 개발 VM의 localhost:18443 SSH 터널 프로세스가 사라져 있었다. 터널을 사용자 서비스로 분리하고 전용 SSH 키를 사용해 임시 SSH master/터미널 수명에 의존하지 않게 했다. 15초 heartbeat 세 번 실패하면 연결을 종료하고 서비스가 3초 뒤 재연결한다. 이는 200ms 주행 응답 제한을 대체하지 않는다.

## 이 VM에서 실행

```bash
# 권장 시연: 같은 MaleCNS 서명 회로를 VM CPU에서 실행 (GUI 기본값)
scripts/run_webots.sh
# 외부 GPU를 명시적으로 선택
REFLEXGUARD_BRAIN_PROFILE=real scripts/run_webots.sh
```

터널 복구 후에도 외부 GPU는 화면 실행 중 200ms 지연이 재현됐다. 따라서 GUI 기본값은 `local`로 정했다. 동일한 서명/해시의 187개 뉴런 LIF를 기존 CPU/CUDA 수치 동등성 검증에 쓰는 NumPy 백엔드로 실행한다. mock으로 대체하지 않으며, 실행 중 자동 fallback도 없다. HUD에 `LOCAL CPU` 또는 `REMOTE GPU`를 표시한다.

`local`은 127.0.0.1:18444에만 바인딩하고 외부 GPU와 같은 서명 로더·mTLS·토큰·세션 격리·시간 상한을 사용한다. 서버 설정은 `.env.local-brain`, 클라이언트 주소/독립 토큰은 `.env.local-client`에 저장한다. 개인키/토큰/가중치는 Git 제외다. 최초 신뢰 공개키는 배포 provenance와 대조하며 자산 폴더 안의 키를 임의로 신뢰하지 않는다. 사용자 서비스 템플릿은 `config/reflexguard-local-brain.service.in`이고 아래 터널 서비스와 같은 방식으로 설치한다.

실제 로컬 API 100회 왕복은 중앙값 3.060ms·p95 4.542ms·최대 5.850ms였다. 클라이언트 인증서/토큰 누락 거부·출력 방향·뉴런 침묵 계약도 통과했다. 이는 장기 부하의 최악 지연 보증은 아니다.

외부 GPU를 선택할 때는 VPN이 먼저 연결되어 있어야 한다. local에는 VPN이 필요 없다. `run_webots.sh`는 mTLS와 Bearer로 읽기 전용 health를 검사하고 real/local/mock 모델 접두사를 확인한다. 아직 GUI가 열리지 않은 단계의 health만 최대 세 번 확인한다. 실패하면 선택한 프로필의 로컬 뇌 또는 터널 서비스를 시작하고 유한 횟수로 재확인한다. 계속 실패하면 설명을 출력하고 창을 열지 않는다. 이 검사는 세션을 생성하거나 step을 재시도하지 않는다.

실행 중 통신 실패는 기존처럼 정지 고정한다. 연결 정상 여부는 `systemctl --user status reflexguard-gpu-tunnel.service`, 서비스 로그는 `journalctl --user -u reflexguard-gpu-tunnel.service`로 확인한다. GPU 서비스 오류·잘못된 인증서·만료·VPN 미접속도 확인해야 한다. 터널 재연결만으로 모든 응답 시간 초과가 해결되는 것은 아니다.

## 새 VM에 자동 재연결 구성

1. `.env.gpu`의 GPU SSH 호스트·사용자·포트, `.env.brain-client`의 실제 API 주소·인증서·토큰을 설정한다. 기존 공식 절차로 GPU SSH 호스트 키를 확인한다.
2. 서비스용 Ed25519 키를 `~/.ssh/reflexguard_gpu_ed25519`에 권한 0600으로 보관한다. 비밀번호나 개인키를 Git에 넣지 않는다. 현재 VM의 서버 측 공개키에는 `restrict,port-forwarding`, 뇌 컨테이너의 8443 포트만 허용하는 `permitopen`, 컨테이너 IP 조회만 수행하는 고정 명령을 적용했다. 셸·PTY·에이전트·X11 전달을 허용하지 않는다. 새 서버도 같은 최소 권한으로 등록한다. 컨테이너 IP 변경 시 허용 목적지도 함께 갱신한다.
3. `config/reflexguard-gpu-tunnel.service.in`의 `@ROOT@`를 저장소 절대 경로로 치환해 `~/.config/systemd/user/reflexguard-gpu-tunnel.service`로 저장한다. 경로에 공백이 있으면 systemd ExecStart 인용 규칙도 적용한다.
4. `systemctl --user daemon-reload`와 `systemctl --user enable --now reflexguard-gpu-tunnel.service`를 실행한다. 사용자 로그인 세션의 서비스이며, OS/VPN 부팅 자동 연결까지 설정하는 기능은 아니다.

서비스가 설치되지 않은 환경에서는 `scripts/connect_gpu.sh`를 별도 터미널에서 계속 실행하는 기존 방식도 가능하다. 이미 정상 터널이 있으면 시작 검사를 통과하므로 새 서비스를 중복 실행하지 않는다.

## 검증

시작 전 health 재확인·세션 미생성·real/mock 혼동 거부·유한 실패, 정상 연결 재사용·터널 시작·복구 실패 시 창 미실행을 `tests/test_brain_startup.py`에서 검사한다. 복구한 실제 GPU 연결의 5초 배치 주행은 1.656m, 156 step, 충돌·뇌 오류 0이었다(`logs/tunnel-recovery-drive.json`).
