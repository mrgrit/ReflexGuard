# MaleCNS 회로 선택과 모델링 근거

2026-09-25, 앱 0.7.0. 원본은 [MaleCNS 공식 배포](https://male-cns.janelia.org/download/)의 v1.0 Feather 3종이다. 파일별 실제 SHA-256은 `brain_server/assets.lock`과 `logs/malecns-source-inspection.json`에 기록했다. 배포자 서명은 우리 변환 산출물을 인증하며 원본 공급자의 서명을 뜻하지 않는다.

| 자료 | 확인한 열 | 선택/검사 |
|---|---|---|
| body-annotations | bodyId, type, somaSide | type이 정확히 LPLC2 또는 DNp01, 양측 somaSide, ID 유일성 |
| body-neurotransmitters | body, consensus_nt, predicted_nt, predicted_nt_confidence | 선택 ID 전부 존재, 두 전달물질 값 acetylcholine, confidence ≥ 0.5 |
| connectome-weights | body_pre, body_post, weight | int64·양수·결측 없음, 선택 간선 중복/참조 검사 |

LPLC2 185개(L 94, R 91), DNp01 2개를 선택했다. DNp01은 bodyId **10010 = DNp01(GF)_L**, **10001 = DNp01(GF)_R**로 실제 주석에서 확인했다. 모든 선택 뉴런의 전달물질 예측 최소 confidence는 0.5004955542656235였다. 확률적 예측을 실험으로 확정한 전달물질이라고 해석하지 않는다.

LPLC2→DNp01의 직접 연결만 사용한다. 총 **187개 뉴런, 185개 간선, 4,862개 시냅스**다. 좌측 출력에는 2,642개, 우측에는 2,220개 시냅스가 들어오며 선택된 간선은 같은 somaSide를 연결한다. 같은 187개 뉴런 사이의 전체 유도 그래프(13,629간선, 51,050시냅스)에서 재귀/측면 연결을 제외한 축소 회로다. `assets.lock`의 neurons에 전체 선택 ID를 남겼다.

원본 151,856,684간선의 값/결측 검사를 수행했다. 이 중 125,828,298간선은 양끝 중 하나 이상이 curated 주석 목록 밖이다. 공식 연결 파일은 모든 segment를 포함하므로 이를 기록하고 선정 회로에서는 제외했다. 전체 원본 그래프의 주석 참조 무결성이 완벽하다고 주장하지 않는다. 변환 결과는 `logs/malecns-conversion.json`에 있다.

## 문헌과 구현 가정

[Klapoetke et al., 2017](https://www.nature.com/articles/nature24626)은 LPLC2의 looming 선택성과 giant fiber 연결 근거다. [Namiki et al., 2018](https://elifesciences.org/articles/34272)은 DNp01/giant fiber가 빠른 탈출 경로에 속함을 설명한다. 이 문헌은 이 구현의 막전위 상수·휠체어 조향 정책을 실증한 자료가 아니다.

`brain_server/model.py`는 1ms Euler LIF를 새로 구현했다. 좌/우 영상 루밍을 해당 somaSide의 LPLC2 모두에 같은 강도로 주입한다. 개별 수용장·망막 위치 매핑은 하지 않는다. 연결 수를 출력별 총 입력 시냅스 수로 나누고 synaptic_gain을 곱한다. 연결의 상대적 비율은 실제 데이터지만 정규화와 막전위 상수는 공학적 가정이다. 전체 뇌 모델이나 학습된 생물학적 파라미터가 아니다.

| 파라미터 | 최종 값 |
|---|---:|
| input_gain | 2.5 |
| synaptic_gain | 25 |
| tau_ms | 10 |
| refractory_ms | 2 |
| 발화 임계값 / reset | 1 / 0 |
| 출력 정규화 기준 | 200 Hz |

좌 GF 발화율은 우회피 값, 우 GF는 좌회피 값으로 변환하고 두 값의 최댓값을 escape로 쓴다. 이 좌우 회피 매핑은 생물의 실제 좌우 조향을 증명하는 주장이 아니다. 현재 공유 제어에서는 정지가 우선하며 이번 3개 월드의 실제 모델 결과는 정지로 충돌을 피했다. 다음 버전의 Jev 행동 선택은 별도 계획이다.

침묵 허용목록은 이 187개 ID로 한정하고 요청은 최대 10개다. 운영자 실험 기능으로 출력 뉴런을 침묵시키면 안전 보조 신호도 약해진다. 실물 운행용 기능으로 검증하지 않았으며 연구 시뮬레이션에서만 사용한다.
