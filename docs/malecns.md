# MaleCNS 데이터 기준

2026-09-24 사용자 결정에 따라 ReflexGuard의 커넥톰 기준을 MaleCNS로 변경했다.
0.7.0에서 실제 원본을 검증·변환하고 서명된 축소 LIF를 Thor에 배포했다. [선정 근거](neurons.md), [자산 잠금](../brain_server/assets.lock), [시험](test_report.md)을 참조한다.
현재 `mock-rules-v1` 응답은 여전히 규칙 기반이며 MaleCNS 시뮬레이션 결과가 아니다.

## 확인한 공식 출처

[공식 릴리스 안내](https://male-cns.janelia.org/release/)에 따르면 v1.0은 2026-06-08 공개되었다.
[공식 다운로드 안내](https://male-cns.janelia.org/download/)의 neuPrint 대상은
`https://neuprint.janelia.org`, 데이터셋은 `male-cns:v1.0`이다.
원본 flat-connectome 버킷과 필요한 3개 Feather 파일명을 `config/malecns.json`에 기록했다.
주석에는 유형·분류·좌우 정보가 포함되고, 전달물질 예측은 별도 파일이다.
공식 페이지가 연결하는 라이선스는 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)이다.

이 설정은 최초 **다운로드 계획**이며 런타임 설치 상태가 아니다. `planned_not_downloaded`는 계획 스키마의 식별값으로 유지한다. 실제 다운로드/배포 상태는 `brain_server/assets.lock`, 변환 기록, GPU provenance에서 확인한다.
계획 검증 모델은 잘못된 릴리스, 다른 서버·버킷, 서로 바뀐 파일 역할, 근거 없는 상태 필드를 거부한다.

## 데이터 처리 기준 (0.7.0 구현)

1. 외부 GPU 장비에서 공식 파일을 내려받고 크기·SHA-256·출처·가져온 시각을 기록한다.
2. Arrow/Feather의 실제 스키마를 먼저 확인한다. ID·유형·좌우·연결의 pre/post·가중치·전달물질 열을 기록한 다음 명시적 매핑을 만든다. 열 이름은 미리 추측하지 않는다.
3. ID 유일성, 연결 양끝의 존재, 결측·중복, 유한한 비음수 시냅스 개수, 좌우 주석, 전달물질 예측 불확실성을 검사한다. 결측을 임의의 흥분/억제로 치환하지 않는다.
4. 루밍 관련 유형과 하강뉴런 후보는 실제 주석과 문헌을 대조한다. LPLC2 같은 명칭은 검색 후보이며, 이 릴리스에서의 존재·동일한 생리 기능을 미리 단정하지 않는다. 공식 예제의 뉴런 ID도 회피 회로 ID로 가져오지 않는다.
5. 연결 수와 전달물질 예측을 LIF 시뮬레이션 가중치로 변환하는 방식은 별도 모델링 가정이다. 필터·정규화·단위·난수 시드(과학 실험용)·선택한 부분 회로를 기록한다.
6. 검토한 변환 결과는 safetensors 또는 숫자 배열 npz로 저장한다. object 배열·pickle은 금지한다. 원본/가중치/허용목록 해시, 뉴런 목록, 파라미터, 모델 버전을 자산 잠금에 남긴다. 변환/배포 코드 해시는 gpu_provenance.json과 Git 변경 이력으로 추적한다.
7. 배포자가 검토한 자산 manifest와 뉴런 침묵 허용목록을 서명한다. 서버는 고정된 신뢰 공개키로 서명과 파일 해시를 검증한 뒤 로드한다. 원본 공급자가 서명을 제공한다고 가정하지 않는다.

neuPrint 토큰이 필요한 경우 `REFLEXGUARD_NEUPRINT_TOKEN` 환경변수를 사용한다.
뇌 API의 mTLS 인증서·Bearer 토큰과 용도를 구분하고 로그·저장소에 기록하지 않는다.
0.5.1부터 외부 GPU에서 공식 원본 다운로드·Arrow 스키마 점검과 PyTorch 환경을 준비한다. 증거는 [GPU 환경](gpu_environment.md)에 기록한다. mock 기반 기능과 실제 모델 구현 상태는 계속 구분한다.

## 버전과 API

API의 `top_neurons[].id`는 문자열이므로 MaleCNS 식별자를 그대로 문자열로 전달할 수 있다.
실제 서버의 자산 manifest와 `model_version`에 데이터셋·릴리스·변환 버전을 연결해 식별자 혼동을 방지한다.
기존 API의 mTLS, 요청 범위, 200ms 클라이언트 제한과 실패 시 정지 원칙은 계속 적용한다.
실제 데이터셋 전환 검증은 후보 회로·가중치 로딩·GPU 실행·월드 테스트까지 완료해야 한다.

[공식 보조 분석 저장소](https://github.com/flyconnectome/2025malecns)는 연구 근거를 확인하는 참고 자료다.
다른 데이터셋과의 비교용 파생 표는 이 프로젝트의 원본 연결 가중치로 사용하지 않는다.
