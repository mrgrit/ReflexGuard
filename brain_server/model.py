"""Reduced, deterministic 1 ms LIF circuit; physiological parameters are assumptions."""
from dataclasses import dataclass
import time
import numpy as np

from reflexguard.common.schemas import StepRequest, StepResponse, NeuronActivity


@dataclass
class LIFState:
    voltage: object
    refractory: object
    spikes: object


class Circuit:
    def __init__(self, assets, backend="numpy"):
        self.manifest, self.allowed, pre, post, counts = assets
        self.neurons = self.manifest.neurons
        self.parameters = self.manifest.parameters
        self.backend = backend
        self.torch = None
        if backend == "cuda":
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is unavailable")
            torch.set_num_threads(2)
            self.torch = torch
        elif backend != "numpy":
            raise ValueError("Unsupported model backend")
        self.size = len(self.neurons)
        weights = np.zeros((self.size, self.size), dtype=np.float32)
        weights[post, pre] = counts
        totals = weights.sum(axis=1, keepdims=True)
        weights /= np.maximum(totals, 1.)
        self.weights = self.array(weights * self.parameters.synaptic_gain)
        self.left = self.array([float(n.cell_type == "LPLC2" and n.side == "L") for n in self.neurons])
        self.right = self.array([float(n.cell_type == "LPLC2" and n.side == "R") for n in self.neurons])
        self.outputs = {n.side: i for i, n in enumerate(self.neurons) if n.cell_type == "DNp01"}

    def array(self, value):
        return self.torch.tensor(value, dtype=self.torch.float32, device="cuda") if self.torch else np.asarray(value, dtype=np.float32)

    def zeros(self):
        return self.array(np.zeros(self.size, dtype=np.float32))

    def state(self):
        return LIFState(self.zeros(), self.zeros(), self.zeros())

    def synchronize(self):
        if self.torch:
            self.torch.cuda.synchronize()

    def step(self, original, request: StepRequest, silenced, deadline):
        # Stage state privately. Failed/expired requests never commit partial evolution.
        clone = lambda value: value.clone() if self.torch else value.copy()
        state = LIFState(clone(original.voltage), clone(original.refractory), clone(original.spikes))
        enabled = self.array([float(n.id not in silenced) for n in self.neurons])
        state.voltage *= enabled
        state.spikes *= enabled
        drive = self.parameters.input_gain * (self.left * request.left_looming + self.right * request.right_looming)
        counts = self.zeros()
        for index in range(request.dt_ms):
            if index % 5 == 0:
                self.synchronize()
                if time.monotonic() >= deadline:
                    raise TimeoutError("Simulation deadline exceeded")
            current = drive + self.weights @ state.spikes
            voltage = state.voltage + (current - state.voltage) / self.parameters.tau_ms
            active = (state.refractory <= 0) * enabled
            voltage *= active
            if self.torch:
                spike = (voltage >= 1.).to(self.torch.float32) * enabled
                refractory = self.torch.clamp(state.refractory - 1., min=0.)
            else:
                spike = (voltage >= 1.).astype(np.float32) * enabled
                refractory = np.maximum(state.refractory - 1., 0.)
            state.voltage = voltage * (1. - spike)
            state.refractory = refractory * (1. - spike) + self.parameters.refractory_ms * spike
            state.spikes = spike
            counts += spike
        self.synchronize()
        if time.monotonic() >= deadline:
            raise TimeoutError("Simulation deadline exceeded")
        rates = (counts.cpu().numpy() if self.torch else counts) * (1000. / request.dt_ms)
        left = min(1., float(rates[self.outputs['L']]) / self.parameters.output_rate_hz)
        right = min(1., float(rates[self.outputs['R']]) / self.parameters.output_rate_hz)
        top = sorted(range(self.size), key=lambda i: (-float(rates[i]), i))[:10]
        response = StepResponse(
            escape=max(left, right), turn_left=right, turn_right=left,
            top_neurons=[NeuronActivity(id=self.neurons[i].id, type=self.neurons[i].cell_type, rate_hz=float(rates[i])) for i in top],
            model_version=self.manifest.model_version,
        )
        return state, response
