# Phase 3 보정 기록

2026-09-24, Ubuntu 22.04 VM / Webots R2025a / mock-rules-v1.
현재 커넥톰 도입 기준은 MaleCNS v1.0이며 **이 검증에는 실제 MaleCNS 가중치를 사용하지 않았다.**
모든 전진 시험은 0.6m/s 사용자 명령을 유지하고 10.016초까지 진행했다.
API 통신은 mTLS + Bearer이며 fallback 없이 수행했다.

## 보정 과정

| 순서 | 카메라 FOV | 면적 분모 하한 | stop_on / turn_on / turn_gain | 관측 |
|---|---:|---:|---|---|
| 초기 | 1.2rad | 0.008 | 0.30 / 0.25 / 0.50 | 정면·박스 0회, 측면 접촉 시작 4회. 측면 물체가 늦게 들어옴. |
| 작은 물체 잡음 완화 | 1.2rad | 0.020 | 0.40 / 0.35 / 0.30 | 정면 0회. 보정 재검토. |
| 시야 확대 | 1.8rad | 0.020 | 0.40 / 0.35 / 0.30 | 측면 접촉 시작 2회. 회피 조향 후 물체가 시야에서 빠져 위험 신호가 약해짐. |
| 정지 민감도 증가 | 1.8rad | 0.020 | 0.25 / 0.35 / 0.30 | 측면·박스 0회, 정면 1회. 넓은 시야에서 먼 물체의 픽셀 면적 감소로 정면 정지가 늦어짐. |
| 최종 | 1.8rad | 0.008 | 0.25 / 0.35 / 0.30 | 세 월드 모두 0회, 뇌 통신 오류 0회. |

실패를 숨기지 않도록 중간 로그도 `docs/logs/phase3-calibration-*.log`에 남겼다.
카메라 캡처로 측면 물체의 진입·이탈을 확인했으며 임시 캡처 코드는 최종 코드에서 제거했다.
월드 장애물 위치·보행자 경로·속도·접촉 판정은 변경하지 않았다. FOV는 Wheelchair PROTO의 노출 파라미터다.

## 최종값

`config/control.json`: dark_threshold 140, area_floor 0.008, area_tau_s 0.12,
looming_tau_s 0.15, expansion_scale 1.0, stop_on 0.25, stop_off 0.12,
turn_on 0.35, turn_off 0.10, turn_gain 0.30rad/s, max_turn 1.2rad/s,
deceleration 2.0m/s², release_ms 500. 회전 감속은 4.0rad/s²다.
`Wheelchair.proto`: cameraFieldOfView 1.8rad(약 103°), maxSpeed 0.6m/s, 160×120 영상, 32ms 스텝.
0.6m/s 명령은 위험/통신 정지에서 약 0.32초 이내에 0 명령으로 내려간다. 물리적 정지 거리는 별도 관측 대상이다.

## 최종 관측값

| 월드 / 입력 | 시간(s) | 충돌 시작(회) | 최소 근사 거리(m) | 이동량(m) | 뇌 step | 개입 step |
|---|---:|---:|---:|---:|---:|---:|
| corridor_basic / forward | 10.016 | 0 | 0.272 | 1.656 | 312 | 228 |
| corridor_side / forward | 10.016 | 0 | 0.815 | 0.253 | 312 | 303 |
| corridor_static / forward | 10.016 | 0 | 0.820 | 0.484 | 312 | 289 |
| corridor_static / idle | 3.008 | 0 | 0.820 | 0.003 | 93 | 0 |
| corridor_side / idle | 5.024 | 0 | 0.820 | 0.003 | 156 | 0 |

최소 거리는 휠체어 외접원과 보행자·박스·벽의 평면 근사다. 0.82m 값은 벽과의 초기 여유가 최소인 경우이며
장애물까지의 정확한 메시 거리가 아니다. 판단은 물리 접촉점과 별도로 측정한다.
위 값은 각 조건 1회 최종 실행 기록이며 여러 임의 환경·장시간 무충돌 보장이 아니다.
측면과 박스에서는 보수적으로 일찍 정지한다. 충돌 회피와 주행 효율의 추가 균형 조정이 남아 있다.
정지한 휠체어에 보행자가 계속 접근하는 더 긴 시나리오는 별도 검증이 필요하다.

## 무입력 증거와 실패 안전

`phase3-idle-pedestrian.log`의 4640ms에서 escape 약 0.993, signal STOP인데도
user_forward=0, forward=0, turn=0, reason=idle, intervened=false다.
최종 개입은 0회이며 약 3mm의 이동은 초기 물리 안착이다.
`test_real_mtls_disconnect_causes_latched_gradual_stop`은 실제 mTLS 서버를 강제 종료하고
첫 제동 명령이 0과 0.6 사이로 줄어든 뒤 0을 유지하는지 검사한다.
초기 서버 단절 시험의 정상 종료 대기는 살아 있는 keep-alive 연결 때문에 지연되어,
의도한 갑작스러운 단절을 재현하도록 시험 소유 서버 프로세스 강제 종료로 수정했다.

코드 오류나 실패 시나리오를 통과로 간주하지 않도록 `simulation.verify`가
충돌·통신 오류·뇌 step 누락·무입력 개입·전진 무이동을 거부한다.

## 0.7.0 실제 MaleCNS LIF 보정 (2026-09-25)

기존 control.json의 stop_on=0.25, stop_off=0.12, turn_on=0.35, turn_off=0.10, deceleration=2.0, release_ms=500은 유지했다. 서명 manifest의 입력 gain을 10→2.5로 조정했다. 초기 gain=10은 t=64ms의 looming≈0.18에도 escape=0.46875를 내어 0.069m만 진행했고 유효 주행 기준에 실패했다. 원문은 logs/phase6-basic-initial.log다.

CPU 기준 고정 루밍 10회(dt=32ms) 평균 escape는 gain=2.5에서 looming0.3→0, 0.45→0.2031, 0.5→0.2656, 0.8→0.5469였다. 낮은 영상 변화에는 발화하지 않으면서 위협 증가에 정지 신호를 내도록 보정했다. 모든 파라미터는 서명 후 GPU에 재배포했다.

보정 첫 정면 시험은 1.656m 이동 후 후반에 VPN 응답 timeout이 한 번 발생해 통합 실패로 분류했다(logs/phase6-basic-timeout.log). 200ms 제한이나 오류 검사를 완화하지 않았다. 이후 전체 리허설에서 실제 모델 정면/옆문/고정 월드는 각각 1.656/0.235/0.484m, 충돌·뇌 실패 0회였다. 상세 비교와 무조작 결과는 test_report.md 및 logs/phase7-real.json에 있다.

세 시험은 정지 우선 동작이며 자유로운 경로 탐색/지속 회피를 검증하지 않는다. 다음 Jev 버전에서 안전 조건을 유지하면서 진행률과 불필요 정지를 비교한다.
