"""Arc-length trail for bounded, independent simulated visitor walking."""
import math


class VisitorTrail:
    def __init__(self):
        self.points = []
        self.length = 0.0

    def append(self, x, y):
        if not all(math.isfinite(v) for v in (x, y)):
            raise ValueError('nonfinite robot pose')
        if self.points:
            distance = math.hypot(x-self.points[-1][1], y-self.points[-1][2])
            if distance < .03:
                return
            if distance > .8:
                raise ValueError('robot pose discontinuity')
            self.length += distance
        self.points.append((self.length, x, y))

    def sample(self, progress):
        if not self.points:
            raise ValueError('empty trail')
        progress = max(0.0, min(self.length, progress))
        for before, after in zip(self.points, self.points[1:]):
            if after[0] >= progress:
                ratio = (progress-before[0])/(after[0]-before[0])
                return (before[1]+ratio*(after[1]-before[1]),
                        before[2]+ratio*(after[2]-before[2]),
                        math.atan2(after[2]-before[2], after[1]-before[1]))
        return (*self.points[-1][1:], 0.0)


def advance(progress, target, speed, dt):
    if not all(math.isfinite(v) for v in (progress, target, speed, dt)) or speed < 0 or dt < 0:
        raise ValueError('invalid walking step')
    return min(max(progress, target), progress+speed*min(dt, .2))


def following_target(trail, progress, gap, robot, predecessor=None, others=()):
    target = trail.length-gap
    if predecessor is not None:
        target = min(target, predecessor-1.0)
    while target > progress:
        x, y, _ = trail.sample(target)
        if (math.hypot(x-robot['x'], y-robot['y']) >= 2.05 and
                all(p is not None and math.hypot(x-p['x'], y-p['y']) >= 1.15 for p in others)):
            break
        target -= .1
    return max(progress, target)
