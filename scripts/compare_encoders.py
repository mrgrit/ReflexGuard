"""Reproducible synthetic comparison; no production choice or unsafe mode flag."""
import json
import time
import cv2
import numpy as np
from reflexguard.control.config import Calibration
from reflexguard.encoder.looming import LoomingEncoder
from reflexguard.simulation.drive import CameraFrame


def sequence(kind):
    for i in range(80):
        image = np.full((120, 160, 4), 220, np.uint8)
        image[:, :, 3] = 255
        radius = 8 + i // 4 if kind == "expansion" else 14
        x = 30 + i // 2 if kind == "translation" else 40
        image[60-radius:60+radius, x-radius:x+radius, :3] = 40
        if kind == "illumination" and i >= 20:
            image[:, :, :3] = np.maximum(image[:, :, :3].astype(int)-100, 0).astype(np.uint8)
        yield image


def measure():
    output = {"opencv": cv2.__version__, "numpy": np.__version__, "scenarios": {}}
    for kind in ("stationary", "expansion", "translation", "illumination"):
        encoder = LoomingEncoder(Calibration.load())
        previous = None
        area_scores, flow_scores, area_times, flow_times = [], [], [], []
        for i, image in enumerate(sequence(kind)):
            start = time.perf_counter()
            value = encoder.update(CameraFrame(i*32, 160, 120, image.tobytes()))
            area_times.append((time.perf_counter()-start)*1000)
            area_scores.append(max(value.left, value.right))
            gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
            if previous is not None:
                start = time.perf_counter()
                flow = cv2.calcOpticalFlowFarneback(previous, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                divergence = (np.gradient(flow[:, :, 0], axis=1) + np.gradient(flow[:, :, 1], axis=0))/0.032
                flow_scores.append(float(np.clip(np.percentile(divergence, 95), 0, 1)))
                flow_times.append((time.perf_counter()-start)*1000)
            previous = gray
        output["scenarios"][kind] = {
            "area_peak": max(area_scores), "flow_peak": max(flow_scores),
            "area_mean_ms": float(np.mean(area_times)), "flow_mean_ms": float(np.mean(flow_times))}
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    measure()
