# Phase 2 — Webots 휠체어와 복도

> 이 문서는 Phase 2 당시 기록입니다. 현재 제어기는 뇌 서버 연결이 필요하므로 실행은 [Phase 3 안내](phase3.md)를 따릅니다.

Webots R2025a, Python 3.10.12. 기본 속도 0.6 m/s, 바퀴 반경 0.24 m,
윤거 0.64 m, 두 뒷바퀴 모터와 두 앞바퀴 캐스터(자유 회전·조향), 카메라 160×120,
기본 스텝 32 ms. `Wheelchair.maxSpeed`는 0 초과 1.2 m/s 이하이며 좌우 바퀴 속도 모두 제한한다.
이 단계는 수동 주행·계측 기반이다. 뇌 API 및 자동 회피는 Phase 3에서 연결한다.

## 화면에서 조종

VMware 콘솔 또는 원격 데스크톱의 터미널에서:

```bash
cd ~/work/reflexguard
.venv/bin/python scripts/configure_webots.py
webots webots/worlds/corridor_basic.wbt
```

시뮬레이션 재생 버튼을 누르고 3D 화면을 클릭해 키보드 포커스를 준다.
↑/↓ 전진·후진, ←/→ 좌·우 회전, Space 정지. 키를 놓으면 다음 스텝에 정지 명령을 준다.
전진과 회전을 동시에 누를 수 있다. 물리 관성 때문에 실제 정지까지는 시간이 걸린다.
GUI 키보드 포커스와 조종감은 사람이 확인해야 하며, 배치 테스트로 완료했다고 간주하지 않는다.

`runtime.ini.in`을 바탕으로 실제 `.venv/bin/python`의 절대 경로를 `runtime.ini`에 생성한다.
생성 파일은 Git에서 제외한다. 상대 COMMAND는 R2025a에서 해석되지 않아 절대 경로를 사용한다.
부트스트랩과 배치 스크립트가 자동 생성하며, 저장소를 옮긴 경우 위 설정 명령을 다시 실행한다.

## SSH 배치 실행

```bash
scripts/run_scenario.sh corridor_basic 10
scripts/run_scenario.sh corridor_side 10
scripts/run_scenario.sh corridor_static 10
scripts/run_scenario.sh corridor_static 3 idle
scripts/run_scenario.sh corridor_static 2 left
```

인수는 월드 ID, 시뮬레이션 초(1..60), 조종 입력이다. 기본은 10초 전진이며
`forward`, `reverse`, `left`, `right`, `idle`만 허용한다. 배치 입력은 반복 가능한 가상 사용자 명령이다.
파일 경로를 입력받지 않고 고정 월드 ID만 허용한다. 그래픽 실행과 달리 환경변수로 배치 모드를 지정한다.
`REFLEXGUARD_SCENARIO`를 사용자가 직접 설정했다면 화면 조종 전에 해제한다.

표준 출력은 검증된 JSON 하나, 표준 오류는 Webots 로그다.
최대 벽시계 시간은 180초이며 타임아웃·컨트롤러 오류·결과 누락·검은 카메라 영상·전진/후진 무이동은 실패한다.
정상 완료에서는 관측 Supervisor가 Webots를 종료한다. `--no-rendering`에서도 로봇 카메라는 렌더링된다.
Xvfb의 Mesa 소프트웨어 렌더링 경고는 이 VM에서 예상되며, 실행 성공 여부와 별개다.

## 월드와 측정 의미

- `corridor_basic`: 전방에서 접근하는 기본 Pedestrian, 0.5 m/s.
- `corridor_side`: 옆 출입구에서 복도로 진입하는 기본 Pedestrian, 0.5 m/s.
- `corridor_static`: 복도 중앙 고정 박스.

보행자 이동은 Cyberbotics 기본 `pedestrian.py`의 `--trajectory` 경로와 `--speed`로 지정한다.
`enableBoundingObject TRUE`를 사용해 접촉을 활성화한다. 보행자는 키네마틱 모델이며
접촉 시 인간의 힘·균형을 재현하지 않는다. 최초 실행은 공식 PROTO 및 종속 모델 다운로드에 인터넷이 필요하다.
공식 URL은 R2025a로 고정하고 다운로드 자산은 Webots 캐시가 관리한다.

`collision_events`는 휠체어와 모든 자손 바퀴의 접촉점에서 바닥·자기 접촉을 제외한
접촉 시작 횟수다. 휠체어 접촉점과 장애물·벽 접촉점의 좌표가 1µm 이내에서 일치할 때만 집계한다.
Webots의 contact node_id는 상대 물체 ID가 아니므로 상대 ID로 해석하지 않는다. 떨어졌다 다시 접촉하면 추가 집계될 수 있다.
`collision`은 1회 이상 여부이며 충돌이 있어도 시뮬레이션 정상 실행이면 종료코드 0이다.
따라서 **종료코드 0이 충돌 회피 성공을 의미하지 않는다.**

`min_clearance_estimate_m`는 휠체어를 반경 0.68m 원으로 감싼 수평면 근사 여유 거리다.
보행자 반경 0.40m, 박스·벽은 직사각형을 사용하고 겹치면 0으로 표시한다.
이는 메시 사이의 정확한 3D 최소 거리가 아니다. 보행자 팔다리의 모든 자세를 보장하지 않으므로
충돌 판정은 별도의 물리 접촉값으로 확인한다. 시작과 끝의 이동량, 방향 변화, 카메라 프레임 수도 출력한다.

`FrameSink.consume(CameraFrame)`가 다음 단계의 인코더 연결 지점이다.
BGRA 바이트를 스텝마다 복사해 전달하며 프레임 이력을 쌓지 않는다.
관측 Supervisor의 위치·접촉값은 테스트 판정 전용으로, 조종 로직에 전달하지 않는다.

## 검증 기록

자동 검증 결과는 `docs/logs/phase2-*.log` 및 JSON에 기록한다.
화면 모드에서의 사람 키보드 조종 확인은 아직 미완료다.

## 공식 근거

- [Pedestrian PROTO와 필드](https://github.com/cyberbotics/webots/blob/R2025a/projects/humans/pedestrian/protos/Pedestrian.proto)
- [기본 보행자 경로 스크립트](https://github.com/cyberbotics/webots/blob/R2025a/projects/humans/pedestrian/controllers/pedestrian/pedestrian.py)
- [컨트롤러 runtime.ini](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/controller-programming.md)
- [Supervisor 접촉점·종료 API](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/supervisor.md)
- [Camera BGRA 포맷과 좌표](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/camera.md)

## 2026-09-24 VM 자동 실행 결과

| 월드 / 입력 | 시간(s) | 충돌 시작(회) | 최소 근사 거리(m) | 이동량(m) | 카메라 프레임 |
|---|---:|---:|---:|---:|---:|
| corridor_basic / forward | 10.016 | 1 | 0.000 | 3.685 | 313 |
| corridor_side / forward | 10.016 | 2 | 0.000 | 4.740 | 313 |
| corridor_static / forward | 10.016 | 1 | 0.000 | 3.157 | 312 |
| corridor_static / idle | 3.008 | 0 | 0.820 | 0.003 | 93 |
| corridor_static / left | 2.016 | 0 | 0.628 | 0.223 | 62 |
| corridor_static / reverse | 2.016 | 0 | 0.070 | 1.150 | 63 |

전진 3종의 충돌은 회피 미연결 상태의 기준 결과다. 정지 상태의 약 3mm 이동은 시작 시 물리 안착에 해당한다.
좌회전 방향과 후진 이동도 확인했다. 키보드 GUI 수동 확인은 별도로 남아 있다.
