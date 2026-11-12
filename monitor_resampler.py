"""Continuous linear resampling for the independent headphone preview only."""
import numpy as np


class MonitorResampler:
    def __init__(self, input_rate, output_rate):
        self.step = float(input_rate) / float(output_rate)
        self.reset()

    def reset(self):
        self.buffer = None
        self.position = 0.

    def process(self, audio):
        if self.buffer is None:
            self.buffer = np.empty((0, audio.shape[1]), dtype=np.float32)
        self.buffer = np.concatenate((self.buffer, audio), axis=0)
        count = max(0, int(np.ceil((len(self.buffer)-1-self.position)/self.step)))
        positions = self.position + np.arange(count)*self.step
        indices = np.floor(positions).astype(np.int64)
        fraction = (positions-indices)[:, None]
        output = (self.buffer[indices]*(1-fraction) + self.buffer[indices+1]*fraction).astype(np.float32)
        self.position += count*self.step
        consumed = max(0, min(int(self.position), len(self.buffer)-1))
        self.buffer = self.buffer[consumed:].copy()
        self.position -= consumed
        return output
