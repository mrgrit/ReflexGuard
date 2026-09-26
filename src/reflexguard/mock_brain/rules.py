"""Small reproducible rule set with explicitly virtual neuron identifiers."""

import hashlib
import json

from reflexguard.common.schemas import NeuronActivity, StepRequest, StepResponse

MODEL_VERSION = "mock-rules-v1"
THRESHOLD = 0.35
NEURON_IDS = ("mock-escape", "mock-turn-left", "mock-turn-right")
RULES_SHA256 = hashlib.sha256(json.dumps({
    "model_version": MODEL_VERSION,
    "threshold": THRESHOLD,
    "neurons": NEURON_IDS,
    "escape": "clip((max(left,right)-threshold)/(1-threshold),0,1)",
    "turn": "positive opposite-side looming difference above threshold",
    "rate_hz_scale": 100.0,
}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def evaluate(request: StepRequest, silenced: set[str]) -> StepResponse:
    peak = max(request.left_looming, request.right_looming)
    active = peak > THRESHOLD
    values = [
        max(0.0, (peak - THRESHOLD) / (1.0 - THRESHOLD)),
        max(0.0, request.right_looming - request.left_looming) if active else 0.0,
        max(0.0, request.left_looming - request.right_looming) if active else 0.0,
    ]
    values = [0.0 if neuron in silenced else min(1.0, rate)
              for neuron, rate in zip(NEURON_IDS, values)]
    return StepResponse(
        escape=values[0], turn_left=values[1], turn_right=values[2],
        top_neurons=[NeuronActivity(id=neuron, type="mock", rate_hz=rate * 100.0)
                     for neuron, rate in zip(NEURON_IDS, values)],
        neuron_activity=[NeuronActivity(id=neuron, type="mock", rate_hz=rate * 100.0) for neuron, rate in zip(NEURON_IDS, values)],
        model_version=MODEL_VERSION,
    )
