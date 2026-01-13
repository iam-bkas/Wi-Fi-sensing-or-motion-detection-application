from collections import deque
from statistics import mean, median
import math
from typing import Tuple


class MotionDetector:
    def __init__(self, window_size: int = 30, threshold: float = 8.0, ema_alpha: float = 0.3, long_window: int = 120, dev_factor: float = 3.0, down_ratio: float = 0.6):
        self.window_size = window_size
        self.threshold = threshold
        self.short = deque(maxlen=window_size)
        self.long = deque(maxlen=max(long_window, window_size * 4))
        self.ema_alpha = ema_alpha
        self.ema = None
        self.dev_factor = dev_factor
        self.down_ratio = down_ratio
        self.active = False

    def update(self, value: float) -> Tuple[bool, float, float]:
        if self.ema is None:
            self.ema = float(value)
        else:
            self.ema = self.ema_alpha * float(value) + (1.0 - self.ema_alpha) * self.ema
        v = self.ema
        self.short.append(v)
        self.long.append(v)
        if len(self.short) < 5:
            return False, 0.0, 0.0, 0
        avg = mean(self.short)
        var = mean([(x - avg) ** 2 for x in self.short])
        std = math.sqrt(var)
        if len(self.long) < 10:
            trig = std > self.threshold
        else:
            med = median(self.long)
            mad = median([abs(x - med) for x in self.long])
            rs = mad * 1.4826 if mad > 1e-9 else 0.0
            dev = abs(v - med) / rs if rs > 1e-9 else 0.0
            trig = dev > self.dev_factor or std > self.threshold
        if self.active:
            if std < self.threshold * self.down_ratio:
                self.active = False
        else:
            if trig:
                self.active = True
        
        # Crowd/Intensity Estimation
        level = 0
        if self.active:
            if std < self.threshold * 2.0:
                level = 1
            elif std < self.threshold * 4.0:
                level = 2
            else:
                level = 3
        
        return self.active, avg, std, level
