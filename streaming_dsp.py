"""Native SoundTouch streaming pitch processing with a fixed output reservoir."""
import ctypes as ct
from pathlib import Path
import numpy as np
from voice_effects import StreamingEffect


def _load_library():
    path = Path(__file__).parent / 'vendor' / 'soundtouch' / 'SoundTouchDLL_x64.dll'
    lib = ct.CDLL(str(path.resolve()))
    signatures = {
        'createInstance': (ct.c_void_p, []),
        'destroyInstance': (None, [ct.c_void_p]),
        'setSampleRate': (ct.c_int, [ct.c_void_p, ct.c_uint]),
        'setChannels': (ct.c_int, [ct.c_void_p, ct.c_uint]),
        'setPitchSemiTones': (None, [ct.c_void_p, ct.c_float]),
        'setSetting': (ct.c_int, [ct.c_void_p, ct.c_int, ct.c_int]),
        'putSamples': (ct.c_int, [ct.c_void_p, ct.POINTER(ct.c_float), ct.c_uint]),
        'receiveSamples': (ct.c_uint, [ct.c_void_p, ct.POINTER(ct.c_float), ct.c_uint]),
        'numSamples': (ct.c_uint, [ct.c_void_p]),
        'clear': (None, [ct.c_void_p]),
    }
    for name, (restype, args) in signatures.items():
        function = getattr(lib, 'soundtouch_' + name)
        function.restype, function.argtypes = restype, args
    return lib


_LIB = _load_library()


class SoundTouchPitch:
    def __init__(self, semitones, rate, channels):
        self.handle = _LIB.soundtouch_createInstance()
        if not self.handle:
            raise RuntimeError('SoundTouch could not allocate a processor.')
        self.channels = channels
        self.underruns = 0
        if not _LIB.soundtouch_setSampleRate(self.handle, int(rate)):
            raise ValueError('Unsupported sample rate')
        if not _LIB.soundtouch_setChannels(self.handle, channels):
            raise ValueError('Unsupported channel count')
        _LIB.soundtouch_setPitchSemiTones(self.handle, float(semitones))
        # Full overlap search and anti-alias filtering, speech-sized windows.
        for setting, value in ((0, 1), (1, 32), (2, 0), (3, 40), (4, 15), (5, 8)):
            if not _LIB.soundtouch_setSetting(self.handle, setting, value):
                raise RuntimeError(f'SoundTouch rejected setting {setting}')
        self.startup_frames = int(rate * .12)
        self.pending = np.zeros((self.startup_frames, channels), dtype=np.float32)

    def close(self):
        if getattr(self, "handle", None):
            _LIB.soundtouch_destroyInstance(self.handle)
            self.handle = None

    def __del__(self):
        self.close()

    def process(self, audio):
        data = np.ascontiguousarray(audio.T, dtype=np.float32)
        frames = data.shape[0]
        if not _LIB.soundtouch_putSamples(self.handle, data.ctypes.data_as(ct.POINTER(ct.c_float)), frames):
            raise RuntimeError('SoundTouch failed to process audio')
        available = _LIB.soundtouch_numSamples(self.handle)
        if available:
            received = np.empty((available, self.channels), dtype=np.float32)
            count = _LIB.soundtouch_receiveSamples(self.handle, received.ctypes.data_as(ct.POINTER(ct.c_float)), available)
            self.pending = np.concatenate((self.pending, received[:count]))
        out = np.zeros((frames, self.channels), dtype=np.float32)
        count = min(frames, len(self.pending))
        out[:count] = self.pending[:count]
        self.pending = self.pending[count:].copy()
        if count < frames:
            self.underruns += 1
        return out.T.copy()


class VoiceChain:
    def __init__(self, effects, board_type, pitch_type):
        self.effects = effects
        self.stages = []
        batch = []
        for effect in effects:
            if isinstance(effect, pitch_type):
                if batch:
                    self.stages.append(board_type(batch))
                    batch = []
                self.stages.append(float(effect.semitones))
            elif isinstance(effect, StreamingEffect):
                if batch:
                    self.stages.append(board_type(batch))
                    batch = []
                self.stages.append(effect)
            else:
                batch.append(effect)
        if batch:
            self.stages.append(board_type(batch))
        self._processors = {}
        self._format = None

    def __len__(self):
        return len(self.effects)

    @property
    def underruns(self):
        return sum(p.underruns for p in self._processors.values()) + sum(getattr(stage, "underruns", 0) for stage in self.stages)

    def reset(self):
        for processor in self._processors.values():
            processor.close()
        self._processors.clear()
        self._format = None
        for stage in self.stages:
            if not isinstance(stage, float):
                stage.reset()

    def prepare(self, rate, channels):
        self.reset()
        self._format = (rate, channels)
        for index, stage in enumerate(self.stages):
            if isinstance(stage, float) and abs(stage) > .05:
                self._processors[index] = SoundTouchPitch(stage, rate, channels)
            elif isinstance(stage, StreamingEffect) and hasattr(stage, 'prepare'):
                stage.prepare(rate, channels)

    def __call__(self, audio, sample_rate, reset=True, **kwargs):
        if reset or self._format != (sample_rate, audio.shape[0]):
            self.prepare(sample_rate, audio.shape[0])
        audio = np.asarray(audio, dtype=np.float32)
        for index, stage in enumerate(self.stages):
            if isinstance(stage, float):
                if index in self._processors:
                    audio = self._processors[index].process(audio)
            else:
                audio = stage(audio, sample_rate, reset=False, **kwargs)
        return audio
