"""Korean parameter labels, with bounds derived from the controller schema."""
from reflexguard.control.config import Calibration

LABELS = {
    "drive_speed": ("주행 요청 속도 (m/s)", "시뮬레이션 기본값 2.0m/s, 상한 3.0m/s입니다. 월드의 모터 상한과 원격 속도 제한을 함께 적용합니다."),
    "stop_on": ("정지 진입", "뇌의 escape 출력 기준입니다. 높이면 정지가 늦어질 수 있습니다. 거리(m)가 아닙니다."),
    "stop_off": ("정지 해제", "정지 진입보다 낮아야 합니다. 위험이 사라진 뒤 키를 놓아야 다시 움직입니다."),
    "turn_on": ("회피 조향 진입", "뇌의 좌우 회피 출력 기준입니다. 정지와 함께 주행 검증해야 합니다."),
    "turn_off": ("회피 조향 해제", "회피 조향 진입보다 낮아야 합니다."),
    "expansion_scale": ("루밍 확장 배율", "높이면 같은 영상 확장에 더 민감하게 반응합니다."),
    "dark_threshold": ("어두운 물체 기준 (0–255)", "높이면 더 밝은 픽셀까지 물체 면적으로 계산합니다."),
    "area_floor": ("최소 면적 비율", "작은 영상 영역의 확장 잡음을 억제합니다."),
    "area_tau_s": ("면적 평활 시간 (초)", "높이면 흔들림은 줄지만 반응이 느려질 수 있습니다."),
    "looming_tau_s": ("루밍 평활 시간 (초)", "높이면 루밍 변화를 더 천천히 반영합니다."),
    "turn_gain": ("회피 조향 강도", "사용자 조향에 더하는 회피량입니다."),
    "max_turn": ("최대 회전 속도 (rad/s)", "공유 제어기의 조향 출력을 제한합니다."),
    "deceleration": ("장애 시 감속도 (m/s²)", "뇌 통신 장애 시 정지까지 감속하는 강도입니다."),
    "release_ms": ("중립 유지 시간 (ms)", "위험 해제 후 방향키를 놓고 유지해야 하는 시간입니다."),
}


def fields_for(calibration, defaults):
    properties = Calibration.model_json_schema()["properties"]
    result = []
    for name, (label, help_text) in LABELS.items():
        schema = properties[name]
        step = 1 if schema["type"] == "integer" else 0.0001
        result.append({"name": name, "label": label, "help": help_text, "step": step,
                       "minimum": schema.get("minimum", schema.get("exclusiveMinimum", 0) + step),
                       "maximum": schema.get("maximum", schema.get("exclusiveMaximum", 1) - step),
                       "value": getattr(calibration, name), "default": getattr(defaults, name)})
    return result
