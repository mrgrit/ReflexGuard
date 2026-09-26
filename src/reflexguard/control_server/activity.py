"""Bounded, read-only telemetry; visual state never controls the wheelchair."""
from collections import deque
from copy import deepcopy
import json
from pathlib import Path
from threading import RLock
import time


class ActivityMonitor:
    def __init__(self, chair_ids):
        self.graph = json.loads((Path(__file__).parent / "static/malecns-circuit.json").read_text())
        self.expected = {node["id"]: node["cell_type"] for node in self.graph["nodes"]}
        self.lock = RLock()
        self.frames = {chair: None for chair in chair_ids}
        self.history = {chair: deque(maxlen=60) for chair in chair_ids}

    def clear(self, chair):
        with self.lock:
            self.frames[chair] = None
            self.history[chair].clear()

    def record(self, chair, body):
        with self.lock:
            frame = body.model_dump(exclude={"boot_id"})
            frame["received_at"] = time.monotonic()
            self.frames[chair] = frame
            self.history[chair].append({key: frame[key] for key in
                ("sequence", "t_ms", "left_looming", "right_looming", "escape", "reason", "model_version")})

    def snapshot(self, chair):
        with self.lock:
            frame = deepcopy(self.frames[chair])
            history = list(self.history[chair])
        if frame is None:
            return {"state": "waiting", "age_ms": None, "frame": None, "history": []}
        age_ms = max(0, int((time.monotonic() - frame.pop("received_at")) * 1000))
        neurons = frame["neuron_activity"]
        matched = (frame["model_version"] == self.graph["model_version"]
                   and frame["weights_sha256"] == self.graph["weights_sha256"]
                   and len(neurons) == len(self.expected)
                   and {n["id"]: n["type"] for n in neurons} == self.expected)
        if age_ms > 2000:
            state = "stale"
        elif frame["model_version"].startswith("mock-"):
            state = "mock"
        elif matched:
            state = "malecns"
        else:
            state = "unverified"
        # Missing, stale or mismatched samples must never illuminate real neurons.
        if state != "malecns":
            frame["neuron_activity"] = []
        return {"state": state, "age_ms": age_ms, "frame": frame, "history": history}
