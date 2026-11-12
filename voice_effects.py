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

class Harmony(StreamingEffect):
    """Two native pitch layers and a latency-aligned lead, normalized before blending."""
    def __init__(self, pitch1=-7, level1=.35, pitch2=7, level2=.25, mix=.3):
        self.pitch1,self.level1,self.pitch2,self.level2,self.mix=pitch1,level1,pitch2,level2,mix
        self.processors=[]
        self.format=None

    def reset(self):
        for processor in self.processors:
            if processor is not None:
                processor.close()
        self.processors=[]
        self.format=None

    def prepare(self, rate, channels):
        from streaming_dsp import SoundTouchPitch
        self.reset()
        self.format=(rate,channels)
        self.delay=np.zeros((channels,int(rate*.12)),dtype=np.float32)
        for pitch,level in ((self.pitch1,self.level1),(self.pitch2,self.level2)):
            self.processors.append(SoundTouchPitch(pitch,rate,channels) if level>0 and abs(pitch)>.01 else None)

    @property
    def underruns(self):
        return sum(p.underruns for p in self.processors if p is not None)

    def __call__(self,audio,sample_rate,**kwargs):
        if self.format!=(sample_rate,audio.shape[0]):
            self.prepare(sample_rate,audio.shape[0])
        pending=np.concatenate((self.delay,audio),axis=1)
        dry=pending[:,:audio.shape[1]].copy()
        self.delay=pending[:,audio.shape[1]:].copy()
        stacked=dry.copy()
        for processor,level in zip(self.processors,(self.level1,self.level2)):
            if level>0:
                stacked+=level*(processor.process(audio) if processor is not None else dry)
        stacked/=1+self.level1+self.level2
        return ((1-self.mix)*dry+self.mix*stacked).astype(np.float32)


class Resonator(StreamingEffect):
    """Damped short feedback delay for metallic/helmet resonances."""
    def __init__(self,frequency=180,decay=.55,mix=.2):
        from pedalboard import Pedalboard,Delay,LowpassFilter
        self.frequency,self.decay,self.mix=frequency,decay,mix
        self.board=Pedalboard([Delay(delay_seconds=1/frequency,feedback=decay,mix=1),
                               LowpassFilter(cutoff_frequency_hz=6500)])

    def reset(self):
        self.board.reset()

    def __call__(self,audio,sample_rate,**kwargs):
        wet=self.board(audio,sample_rate,reset=False)*(1-self.decay)
        return ((1-self.mix)*audio+self.mix*wet).astype(np.float32)


class ToneDelay(StreamingEffect):
    def __init__(self,time_ms=180,feedback=.25,tone_hz=4000,mix=.15):
        from pedalboard import Pedalboard,Delay,LowpassFilter,HighpassFilter
        self.time_ms,self.feedback,self.tone_hz,self.mix=time_ms,feedback,tone_hz,mix
        self.board=Pedalboard([Delay(delay_seconds=time_ms/1000,feedback=feedback,mix=1),
                               HighpassFilter(cutoff_frequency_hz=100),LowpassFilter(cutoff_frequency_hz=tone_hz)])

    def reset(self):
        self.board.reset()

    def __call__(self,audio,sample_rate,**kwargs):
        wet=self.board(audio,sample_rate,reset=False)
        return ((1-self.mix)*audio+self.mix*wet).astype(np.float32)


class ParallelDistortion(StreamingEffect):
    def __init__(self,drive_db=12,mix=.2):
        self.drive_db,self.mix=drive_db,mix

    def reset(self):
        pass

    def __call__(self,audio,sample_rate,**kwargs):
        gain=10**(self.drive_db/20)
        wet=np.tanh(audio*gain)/np.sqrt(gain)
        return ((1-self.mix)*audio+self.mix*wet).astype(np.float32)
