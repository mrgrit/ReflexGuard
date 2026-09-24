"""Stop priority and hysteresis for normalized brain outputs."""
from enum import Enum
from reflexguard.common.schemas import StepResponse
from reflexguard.control.config import Calibration


class Signal(str, Enum):
    STOP = "STOP"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    NONE = "NONE"


class Decoder:
    def __init__(self, config: Calibration):
        self.config = config
        self.signal = Signal.NONE

    def update(self, response: StepResponse) -> Signal:
        response = StepResponse.model_validate(response)
        c = self.config
        if response.escape >= c.stop_on or (self.signal == Signal.STOP and response.escape > c.stop_off):
            self.signal = Signal.STOP
            return self.signal
        difference = response.turn_left - response.turn_right
        if difference >= c.turn_on:
            self.signal = Signal.LEFT
        elif difference <= -c.turn_on:
            self.signal = Signal.RIGHT
        elif self.signal == Signal.LEFT and difference > c.turn_off:
            pass
        elif self.signal == Signal.RIGHT and difference < -c.turn_off:
            pass
        else:
            self.signal = Signal.NONE
        return self.signal
