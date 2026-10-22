"""Vectorized Hermite sampling for character phases."""
import numpy as np


class CurveSampler:
    def __init__(self, curve):
        self.times = np.asarray([key.time for key in curve.keys], dtype=np.float64)
        self.values = np.asarray([key.value for key in curve.keys], dtype=np.float64)
        self.pre_wrap, self.post_wrap = curve.pre_wrap, curve.post_wrap
        spans = np.diff(self.times)
        outgoing = np.asarray([key.out_tangent for key in curve.keys[:-1]])*spans
        incoming = np.asarray([key.in_tangent for key in curve.keys[1:]])*spans
        a, b = self.values[:-1], self.values[1:]
        self.coefficients = (2*a-2*b+outgoing+incoming, -3*a+3*b-2*outgoing-incoming, outgoing, a)

    def __call__(self, times):
        if len(self.times) == 1:
            return np.full_like(times, self.values[0])
        start, end = self.times[0], self.times[-1]
        normalized = times.copy()
        for selected, mode in ((times < start, self.pre_wrap), (times > end, self.post_wrap)):
            if mode == "clamp":
                normalized[selected] = np.clip(times[selected], start, end)
            else:
                width = end-start
                phase = (times[selected]-start) % (width if mode == "repeat" else width*2)
                normalized[selected] = start+(phase if mode == "repeat" else width-np.abs(phase-width))
        indices = np.clip(np.searchsorted(self.times, normalized, side="right")-1, 0, len(self.times)-2)
        t = (normalized-self.times[indices])/(self.times[indices+1]-self.times[indices])
        a, b, c, d = (values[indices] for values in self.coefficients)
        return ((a*t+b)*t+c)*t+d
