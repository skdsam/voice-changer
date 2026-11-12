"""Stateful spectral-envelope formant shifting and ring modulation."""
import numpy as np


class StreamingEffect:
    pass


class RingModulation(StreamingEffect):
    def __init__(self, frequency=70., mix=0.):
        self.frequency, self.mix = frequency, mix
        self.reset()

    def reset(self):
        self.position = 0

    def __call__(self, audio, sample_rate, **kwargs):
        phase = 2 * np.pi * self.frequency * (self.position + np.arange(audio.shape[1])) / sample_rate
        self.position += audio.shape[1]
        return (audio * ((1-self.mix) + self.mix * np.cos(phase))).astype(np.float32)


class FormantShift(StreamingEffect):
    """Shift a cepstrally smoothed spectral envelope, leaving harmonic bins in place.

    A lightweight approximation, not vocal-tract modeling. 1024-frame STFT,
    256-frame hop, overlap-add and aligned dry/wet blending.
    """
    def __init__(self, semitones=0., mix=1.):
        self.semitones, self.mix = semitones, mix
        self.reset()

    def reset(self):
        self.format = None

    def __call__(self, audio, sample_rate, **kwargs):
        channels, frames = audio.shape
        n, hop = 1024, 256
        if self.format != (sample_rate, channels):
            self.format = (sample_rate, channels)
            self.input = np.zeros((channels, n-hop), dtype=np.float32)
            self.ola = np.zeros((channels, n), dtype=np.float64)
            self.output = np.zeros((channels, hop), dtype=np.float32)
            self.window = np.sqrt(np.hanning(n+1)[:-1])
        self.input = np.concatenate((self.input, audio), axis=1)
        chunks = []
        while self.input.shape[1] >= n:
            spectrum = np.fft.rfft(self.input[:, :n] * self.window, axis=1)
            cepstrum = np.fft.irfft(np.log(np.maximum(abs(spectrum), 1e-7)), n=n, axis=1)
            cutoff = min(80, max(16, int(sample_rate * .001)))
            cepstrum[:, cutoff:n-cutoff+1] = 0
            envelope = np.fft.rfft(cepstrum, axis=1).real
            bins = np.arange(n//2+1)
            shifted = np.stack([np.interp(bins / (2**(self.semitones/12)), bins, row) for row in envelope])
            gain = np.exp(np.clip(shifted-envelope, -1.1, 1.1))
            gain = (1-self.mix) + self.mix * gain
            rendered = np.fft.irfft(spectrum*gain, n=n, axis=1) * self.window / 2
            self.ola += rendered
            chunks.append(self.ola[:, :hop].astype(np.float32).copy())
            self.ola[:, :-hop] = self.ola[:, hop:]
            self.ola[:, -hop:] = 0
            self.input = self.input[:, hop:]
        if chunks:
            self.output = np.concatenate((self.output, *chunks), axis=1)
        result = self.output[:, :frames].copy()
        self.output = self.output[:, frames:]
        return result
