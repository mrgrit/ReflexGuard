# Phase 3 — 영상부터 공유 제어까지

후속 실제 모델의 데이터 기준은 [MaleCNS v1.0](malecns.md)이다. 현재 결과는 데이터셋과 독립적인 mock 검증이다.

`카메라 → LoomingEncoder → BrainClient(mTLS) → Decoder → Arbiter → 좌우 모터`를 연결했다.
제어기는 카메라 바이트와 사용자 명령만 받는다. Supervisor의 위치·충돌 정보는 결과 측정에만 사용한다.
mock 규칙이나 뇌 API 계약을 변경하지 않았으며, 가중치·실제 뇌 모델은 아직 사용하지 않는다.

## 자동 검증

기존 Phase 1의 로컬 인증서와 `.env`가 준비된 환경에서:

```bash
cd ~/work/reflexguard
scripts/check_pipeline.sh
```

로컬 mTLS mock 서버를 시작하고 복도 3종 10초 전진 및 3초 무입력을 실행한 뒤 서버를 종료한다.
충돌, 통신 실패, 뇌 호출 누락, 무입력 개입, 전진 무이동 중 하나라도 있으면 실패한다.
8443 포트에 이미 서버가 실행 중이라면 검증용 서버를 시작할 수 없으므로 해당 기존 서버를 먼저 종료한다.
특정 경우만 확인하려면 `scripts/check_pipeline.sh corridor_side 5 idle`처럼 실행한다.

이미 구동 중인 뇌 서버에 연결하려면 기존 `scripts/run_scenario.sh corridor_basic 10`을 사용한다.
이 명령은 시뮬레이터 실행 자체를 검사하고 JSON을 반환한다. 충돌 0회까지 검사하는 명령은 `check_pipeline.sh`다.
스크립트는 신뢰하는 로컬 `.env`를 읽으며 저장소에는 토큰·인증서를 넣지 않는다.

## 화면 조종

첫 번째 터미널에서:

```bash
cd ~/work/reflexguard
set -a
source .env
set +a
scripts/run_mock_brain.sh
```

두 번째 터미널(VMware 콘솔 또는 원격 데스크톱)에서:

```bash
cd ~/work/reflexguard
scripts/run_webots.sh corridor_basic
```

재생 후 3D 화면을 클릭하고 방향키로 조종한다. Space 또는 키를 놓으면 정지 입력이다.
위험 정지 후에는 방향키를 놓고 안전 신호 상태에서 0.5초 기다려야 다시 조종할 수 있다.
계속 전진을 누르고 있다고 자동 재출발하지 않는다. **통신/영상 오류 정지는 재시작 전까지 해제되지 않는다.**
서버 없이 화면만 열면 휠체어는 오류 정지 상태가 되므로 먼저 서버를 실행한다.
직접 `webots ...`를 실행한다면 환경변수가 해당 프로세스에 전달되어야 한다.

## 판단 규칙

- 위험이 없으면 사용자 명령을 그대로 전달한다.
- `turn_left - turn_right`가 임계값을 넘으면 사용자 회전에 좌/우 보정값을 더한다.
- escape가 정지 임계값 이상이면 조향보다 정지를 우선하고 이전 명령에서 감속한다.
- 모든 명령은 최고 바퀴 속도 제한을 거친다. 무입력일 때 회피 신호만으로 새 주행을 만들지 않는다.
- API 예외·200ms 요청 제한 초과·유효하지 않은 응답·카메라 오류는 정지를 고정한다. 자동 재시도나 mock 대체는 하지 않는다.

설정과 경계값은 `config/control.json`에서 검증해 읽는다. 잘못된 설정은 구동을 시작하지 않는다.
`REFLEXGUARD_DECISION` 로그에는 좌우 루밍, 면적, escape, 신호, 사용자 명령, 실제 명령, 개입 여부를 남긴다.
결과 JSON의 `brain_steps`, `brain_failures`, `interventions`, `stop_steps`, `final_forward`로 동작을 확인한다.
토큰·세션 ID·키는 기록하지 않는다. 판단 로그의 DB 저장·해시 체인은 Phase 4 작업이다.

## 검증 범위

합성 영상, 디코더 히스테리시스, 공유 제어 분기, 실제 mTLS 서버를 끊었을 때 감속 정지를 테스트한다.
기본 0.6m/s와 32ms 스텝에서 검증했으며, 최종 월드 결과는 [보정 기록](calibration.md)에 있다.
Webots 동기식 스텝에서는 API 대기 동안 시뮬레이션 시간이 진행하지 않는다.
따라서 이 결과를 실제 장비의 200ms 통신 지연 중 이동 거리나 하드 실시간 제동 성능으로 해석하면 안 된다.
물리 장비에는 독립 모터 watchdog, 별도 제동 검증과 추가 센서가 필요하다.
전면 카메라만 사용하므로 후진 시 후방 장애물까지 감지한다고 주장하지 않는다.
시야각이 확대되고 보정값이 바뀌었으므로 Phase 2와의 비교는 전체 시스템의 기준 비교다.
