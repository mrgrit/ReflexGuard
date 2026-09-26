"""Bounded local trajectory selection from onboard range scans, not world positions."""
import math
import logging
from typing import Annotated
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator
from reflexguard.control.arbiter import Command, Decision, approach_zero, DT, ESCAPE
from reflexguard.decoder.decoder import Signal

Range = Annotated[float, Field(strict=True, ge=0.02)]
BeamRow = Annotated[list[Range], Field(min_length=64, max_length=64)]
MOUNTS = ((0.62, 0.0, 0.0), (0.0, 0.43, math.pi / 2),
          (-0.46, 0.0, math.pi), (0.0, -0.43, -math.pi / 2))
LOGGER = logging.getLogger(__name__)


class Surroundings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")
    t_ms: int = Field(ge=0)
    forward_mps: float = Field(default=0.0, ge=-8.0, le=8.0, allow_inf_nan=False)
    turn_rad_s: float = Field(default=0.0, ge=-8.0, le=8.0, allow_inf_nan=False)
    travel_m: float = Field(default=0.0, ge=-.35, le=.35, allow_inf_nan=False)
    heading: float = Field(ge=-math.pi, le=math.pi, allow_inf_nan=False)
    ranges: list[BeamRow] = Field(min_length=4, max_length=4)

    @field_validator("ranges")
    @classmethod
    def bounded_ranges(cls, rows):
        if any(not (math.isfinite(v) and v <= 8.0 or v == math.inf) for row in rows for v in row):
            raise ValueError("Invalid range sample")
        return rows

    @classmethod
    def from_heights(cls, lower_ranges, upper_ranges, **motion):
        """Validate both sensors before merging; a faulty height must fail closed."""
        lower = cls(ranges=lower_ranges, **motion)
        upper = cls(ranges=upper_ranges, **motion)
        return cls(ranges=[[min(low, high) for low, high in zip(low_row, high_row)]
                          for low_row, high_row in zip(lower.ranges, upper.ranges)], **motion)

    def points(self):
        points = []
        # Webots range pixels run left-to-right; cylindrical 120-degree scans.
        angles = np.linspace(math.pi / 3, -math.pi / 3, 64)
        for (x, y, yaw), row in zip(MOUNTS, self.ranges):
            values = np.asarray(row)
            finite = np.isfinite(values)
            theta = angles[finite] + yaw
            points.extend(zip(x + values[finite] * np.cos(theta), y + values[finite] * np.sin(theta)))
        return np.asarray(points, dtype=float).reshape(-1, 2)


def wrapped(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


class LocalAvoidance:
    def __init__(self, config):
        self.config = config
        self.previous = Command(forward=0.0, turn=0.0)
        self.fault = False
        self.target_heading = None
        self.route_heading = None
        self.lateral_offset = 0.0
        self.last_ms = -1
        self.active = False
        self.side = 1
        self.detoured = False
        self.tracks = []
        self.track_ms = None
        self.track_heading = 0.0
        self.blocked_reported = False

    def motion(self, points, scan):
        """Track compact scan clusters after removing measured ego motion."""
        velocities = np.zeros_like(points)
        if not len(points):
            self.tracks = []
            self.track_ms, self.track_heading = scan.t_ms, scan.heading
            return velocities
        dt = .032 if self.track_ms is None else (scan.t_ms - self.track_ms) / 1000
        yaw = wrapped(scan.heading - self.track_heading)
        c, s = math.cos(yaw), math.sin(yaw)
        rotation = np.array([[c, s], [-s, c]])
        translation = np.array([scan.travel_m * math.cos(yaw / 2), -scan.travel_m * math.sin(yaw / 2)])
        old = [(rotation @ center - translation, rotation @ velocity, count)
               for center, velocity, count in self.tracks] if 0 < dt <= .1 else []
        links = np.sum((points[:, None] - points[None, :]) ** 2, axis=2) <= .5 ** 2
        unseen = set(range(len(points)))
        tracks, used = [], set()
        while unseen:
            group, pending = [], [unseen.pop()]
            while pending:
                index = pending.pop()
                group.append(index)
                neighbors = unseen.intersection(np.flatnonzero(links[index]).tolist())
                unseen.difference_update(neighbors)
                pending.extend(neighbors)
            cluster = points[group]
            # Long walls are static structure; isolated single rays are not tracks.
            if len(group) < 3 or np.linalg.norm(np.ptp(cluster, axis=0)) > 1.8:
                continue
            center = cluster.mean(axis=0)
            velocity, count = np.zeros(2), 0
            candidates = [(float(np.linalg.norm(center - item[0])), i) for i, item in enumerate(old) if i not in used]
            if candidates:
                distance, index = min(candidates)
                if distance < .8:
                    used.add(index)
                    previous, previous_velocity, previous_count = old[index]
                    observed = (center - previous) / dt
                    if np.linalg.norm(observed) <= 1.8:
                        velocity = .7 * previous_velocity + .3 * observed
                        count = previous_count + 1
            tracks.append((center, velocity, count))
            if count >= 3 and np.linalg.norm(velocity) > .12:
                velocities[group] = velocity
        self.tracks = tracks
        self.track_ms, self.track_heading = scan.t_ms, scan.heading
        return velocities

    def choose(self, user, signal, escape, scan):
        points = scan.points()
        motion = self.motion(points, scan)
        desired_heading = wrapped(self.target_heading - scan.heading)
        requested = abs(user.forward)
        direction = -1 if user.forward < 0 else 1
        horizon = 3.0
        # High demo speed is reserved for open space. Retain braking distance
        # before compact moving clusters can merge with other scan returns.
        nearby = len(points) and np.any((points[:, 0] * direction > -1.0) &
                                      (points[:, 0] * direction < 7.0) & (np.abs(points[:, 1]) < 3.0))
        nearby = nearby or any(np.linalg.norm(center) < 8.0 for center, _, _ in self.tracks)
        turning = self.active or abs(desired_heading) > .15 or abs(user.turn) > .15
        speed = min(requested, self.config.deceleration * 2, 2.0 if nearby or turning else 6.0)
        speed *= 0.75 if escape >= self.config.stop_on else 1.0
        turn_limit = min(1.2, self.config.max_turn)
        restore_turn = max(-turn_limit, min(turn_limit, desired_heading * 1.5)) if self.active or abs(self.lateral_offset) > .2 else user.turn
        candidates = [(direction * speed, restore_turn)]
        for v in (speed, min(speed, .65), min(speed, .3), 0.0):
            for w in (0.0, .4, -.4, .8, -.8, 1.2, -1.2):
                candidates.append((direction * v, max(-turn_limit, min(turn_limit, w))))
        # Pure steering input never creates forward motion.
        commands = np.asarray(candidates)
        v, w = commands[:, 0:1], commands[:, 1:2]
        times = np.linspace(0, horizon, 31)[None, :]
        sample_dt = horizon / 30
        velocity = scan.forward_mps + np.clip(v - scan.forward_mps,
                                               -self.config.deceleration * times, self.config.deceleration * times)
        rotation = scan.turn_rad_s + np.clip(w - scan.turn_rad_s, -4 * times, 4 * times)
        theta = np.cumsum(rotation * sample_dt, axis=1)
        theta -= theta[:, :1]
        x = np.cumsum(velocity * np.cos(theta) * sample_dt, axis=1)
        y = np.cumsum(velocity * np.sin(theta) * sample_dt, axis=1)
        x -= x[:, :1]
        y -= y[:, :1]
        clearance = np.full(len(commands), 8.0)
        clearance_by_time = None
        if len(points):
            dx = points[:, 0] + motion[:, 0] * times[:, :, None] - x[:, :, None]
            dy = points[:, 1] + motion[:, 1] * times[:, :, None] - y[:, :, None]
            c, s = np.cos(theta)[:, :, None], np.sin(theta)[:, :, None]
            local_x, local_y = c * dx + s * dy, -s * dx + c * dy
            # Footrest/casters/wheels enclosed by an oriented rectangle plus margin.
            raw_x = np.maximum(local_x - .65, -.45 - local_x)
            raw_y = np.abs(local_y) - .40
            bx = np.maximum(raw_x, 0)
            by = np.maximum(raw_y, 0)
            uncertainty = .1 * times[:, :, None] * (np.linalg.norm(motion, axis=1) > .12)
            signed_distance = np.sqrt(bx * bx + by * by) + np.minimum(np.maximum(raw_x, raw_y), 0)
            clearance_by_time = (signed_distance - uncertainty).min(axis=2)
            clearance = clearance_by_time.min(axis=1)
        valid = clearance >= .15 + np.abs(commands[:, 0]) * .12
        if np.any(valid):
            self.blocked_reported = False
        if valid[0] and not self.active:
            command = Command(forward=float(commands[0, 0]), turn=float(commands[0, 1]))
            return command, "control_recovering" if abs(self.lateral_offset) > .2 else "risk_monitoring" if speed < requested else "user"
        if self.active and abs(desired_heading) > .35:
            self.detoured = True
        if self.active and self.detoured and valid[0]:
            command = Command(forward=float(commands[0, 0]), turn=float(commands[0, 1]))
            if abs(desired_heading) < .10 and abs(self.lateral_offset) < .25:
                self.active = False
                self.detoured = False
                return command, "control_recovered"
            return command, "control_recovering"
        if not np.any(valid):
            if not self.blocked_reported and clearance_by_time is not None:
                LOGGER.warning("Local path blocked: current clearance %.3fm, measured speed %.3fm/s, heading %.3frad",
                               float(clearance_by_time[0, 0]), scan.forward_mps, scan.heading)
                self.blocked_reported = True
            if clearance_by_time is not None and abs(scan.forward_mps) < .4:
                # Inside the preferred buffer, allow only a slow trajectory that
                # never reduces current positive clearance and increases it.
                initial = clearance_by_time[:, 0]
                recovering = ((np.abs(commands[:, 0]) <= .3) & (np.abs(commands[:, 1]) <= .4)
                              & (initial > .02) & (clearance >= initial - .002)
                              & (clearance_by_time[:, -1] > initial + .05))
                if np.any(recovering):
                    scores = np.where(recovering, clearance_by_time[:, -1], -np.inf)
                    selected = commands[int(np.argmax(scores))]
                    return Command(forward=float(selected[0]), turn=float(selected[1])), "avoid_clearance_recovery"
            return Command(forward=0.0, turn=0.0), "path_blocked"
        preferred = 1 if signal == Signal.LEFT else -1 if signal == Signal.RIGHT else 0
        if not self.active:
            bearings = np.arctan2(points[:, 1], points[:, 0]) if len(points) else np.asarray([])
            distances = np.linalg.norm(points, axis=1) if len(points) else np.asarray([])
            left = distances[(bearings > .4) & (bearings < 1.2)]
            right = distances[(bearings < -.4) & (bearings > -1.2)]
            left_room = float(left.min()) if len(left) else 8.0
            right_room = float(right.min()) if len(right) else 8.0
            self.side = (preferred or 1) if abs(left_room - right_room) < .2 else (1 if left_room > right_room else -1)
            self.active = True
            self.detoured = False
        detour_heading = wrapped(desired_heading + self.side * .9)
        progress = direction * (x[:, -1] * math.cos(detour_heading) + y[:, -1] * math.sin(detour_heading))
        heading_error = np.abs(np.arctan2(np.sin(theta[:, -1] - detour_heading), np.cos(theta[:, -1] - detour_heading)))
        scores = (2 * progress / horizon - .15 * heading_error + .05 * np.minimum(clearance, 1.5)
                  - .05 * np.abs(commands[:, 1] - self.previous.turn))
        if requested:
            scores[np.abs(commands[:, 0]) < .01] -= .5
        scores[~valid] = -np.inf
        selected = commands[int(np.argmax(scores))]
        command = Command(forward=float(selected[0]), turn=float(selected[1]))
        if command.forward == 0 and command.turn == 0:
            return command, "path_blocked"
        return command, "avoid_left" if command.turn > .05 else "avoid_right" if command.turn < -.05 else "avoid_passing"

    def update(self, user, signal, escape, dt_ms, healthy, scan, now_ms):
        user = Command.model_validate(user)
        signal = Signal(signal)
        escape = ESCAPE.validate_python(escape)
        dt_ms = DT.validate_python(dt_ms)
        try:
            scan = Surroundings.model_validate(scan)
            if scan.t_ms != now_ms or scan.t_ms <= self.last_ms:
                raise ValueError("Stale range frame")
            self.last_ms = scan.t_ms
        except ValueError:
            self.fault = True
        self.fault = self.fault or not healthy
        if self.fault:
            command = Command(forward=approach_zero(self.previous.forward, self.config.deceleration * dt_ms / 1000),
                              turn=approach_zero(self.previous.turn, self.config.deceleration * 2 * dt_ms / 1000))
            reason = "brain_failure" if not healthy else "sensor_failure"
        elif user.forward == 0 and user.turn == 0:
            self.motion(scan.points(), scan)
            command, reason = user, "idle"
            self.active = False
            self.target_heading = scan.heading
            self.route_heading = scan.heading
            self.lateral_offset = 0.0
        else:
            if self.route_heading is None:
                self.route_heading = scan.heading
            self.lateral_offset += scan.travel_m * math.sin(wrapped(scan.heading - self.route_heading))
            if user.turn != 0:
                self.route_heading = wrapped(self.route_heading + user.turn * dt_ms / 1000)
                self.lateral_offset = 0.0
            self.target_heading = wrapped(self.route_heading + max(-.45, min(.45, -.35 * self.lateral_offset)))
            command, reason = self.choose(user, signal, escape, scan)
        self.previous = command
        return Decision(command, reason, command != user)
