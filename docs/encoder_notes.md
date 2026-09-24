# 입력 인코더 비교

160×120 BGRA 영상의 좌우 절반에서 어두운 영역의 상대 면적 확장률을 계산한다.
상하 10%를 제외하고 회색조 140 미만을 선택한 뒤 3×3 morphology opening으로 작은 잡음을 제거한다.
면적 비율에는 시정수 0.12초, 최종 루밍에는 0.15초 지수이동평균을 적용한다.
스텝 간격에 맞춰 `alpha = 1 - exp(-dt/tau)`를 사용한다.

`growth = max(0, smooth_area - previous_area) / (max(previous_area, 0.008) * dt_seconds)`이며
이를 `expansion_scale=1.0`으로 나누고 0..1로 제한한다. 첫 프레임은 움직임 근거가 없어 0을 반환한다.
시간 역행·중복·100ms 초과 공백, 버퍼 길이 불일치, 해상도 변경은 오류로 처리해 안전 정지시킨다.
외부 프레임 메타데이터는 Pydantic으로 검증한다. 학습 모델·가중치 파일을 사용하지 않는다.

## 재현 실험

```bash
PYTHONPATH=src .venv/bin/python scripts/compare_encoders.py
```

동일한 80프레임 합성 영상 4종을 면적 방식과 Farneback 광류 발산 방식에 입력했다.
광류 비교 구현은 기본적인 3레벨, window 15, iteration 3, poly_n 5, poly_sigma 1.2 설정이며
발산의 95백분위값을 32ms로 나누고 0..1로 제한했다. 광류의 최적 성능을 주장하는 비교가 아니다.
실행 환경은 이 VM의 Python 3.10.12, NumPy 2.2.6, OpenCV 5.0.0이다.
원자료는 `docs/logs/phase3-encoder-comparison.json`이다.

| 합성 영상 | 면적 방식 최대 루밍 | 광류 방식 최대값 |
|---|---:|---:|
| 정지 | 0.000 | 0.000 |
| 확장 | 0.959 | 0.023 |
| 좌우 이동(중앙 경계 통과) | 0.722 | 0.004 |
| 급격한 조도 감소 | 0.850 | 1.000 |

이 측정에서 면적 방식은 평균 약 0.08–0.13ms/프레임, 광류 비교 구현은 약 3.38–4.16ms/프레임이었다.
단색 물체와 밝은 복도라는 현재 월드에서는 면적 방식이 저렴하고 확장에 잘 반응해 선택했다.

## 해석과 한계

좌우 경계를 통과하는 물체는 한쪽 면적이 커지므로 접근과 횡이동을 구분하지 못한다.
카메라 회전, 보행자의 팔다리 움직임, 어두운 출입구, 조도 변화도 위험 신호를 만들 수 있다.
밝은 장애물이나 배경과 비슷한 물체는 놓칠 수 있다. 이 값은 보정된 충돌까지 남은 시간(TTC)이 아니다.
정지 후 확장이 사라져도 장애물이 없어졌다는 증거가 아니므로 공유 제어기가 정지를 유지한다.
현재 결과는 고정 복도 3종의 시뮬레이션 검증이며 일반 환경이나 실제 전동휠체어 안전성의 증명이 아니다.

## 근거

- [OpenCV 공식 Farneback 예제](https://github.com/opencv/opencv/blob/4.x/samples/python/tutorial_code/video/optical_flow/optical_flow_dense.py)
- [OpenCV 광류 API](https://docs.opencv.org/4.13.0/dc/d6b/group__video__track.html)
- [Webots Camera BGRA 형식](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/camera.md)

예제를 복사하지 않고 API 사용법을 참고해 비교 코드를 작성했다.
