"""Conservative 2-D envelope clearance, explicitly not mesh distance."""
import math

CHAIR_RADIUS = 0.68  # includes footrest, tires and caster sweep
PEDESTRIAN_RADIUS = 0.40


def circle_clearance(x, y, ox, oy, radius):
    return max(0.0, math.hypot(x - ox, y - oy) - CHAIR_RADIUS - radius)


def box_clearance(x, y, ox, oy, hx, hy):
    dx = max(abs(x - ox) - hx, 0.0)
    dy = max(abs(y - oy) - hy, 0.0)
    return max(0.0, math.hypot(dx, dy) - CHAIR_RADIUS)


def has_hazard_contact(chair_points, hazard_points):
    """Match both bodies' contact coordinates; node_id identifies own body."""
    return any(sum((a-b)**2 for a,b in zip(chair,hazard)) <= 1e-12
               for chair in chair_points for hazard in hazard_points)
