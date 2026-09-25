import numpy as np


class Resampler:
    """Streaming linear-interpolation resampler for the monitoring-only live
    stream: the artist's device rate → the 44.1 kHz wire format, and back to
    the engineer's device rate. (Recordings are never resampled.)"""

    def __init__(self, src_rate, dst_rate):
        self.step = src_rate / dst_rate
        self.buf = np.zeros(0, dtype=np.float32)
        self.t = 0.0

    def process(self, x):
        self.buf = np.concatenate([self.buf, x])
        if len(self.buf) < 2:
            return np.zeros(0, dtype=np.float32)
        n = int((len(self.buf) - 1 - self.t) / self.step) + 1
        idx = self.t + np.arange(n) * self.step
        i0 = idx.astype(np.int64)
        frac = (idx - i0).astype(np.float32)
        i1 = np.minimum(i0 + 1, len(self.buf) - 1)
        out = self.buf[i0] * (1.0 - frac) + self.buf[i1] * frac
        nxt = self.t + n * self.step
        drop = int(nxt)
        self.buf, self.t = self.buf[drop:], nxt - drop
        return out
