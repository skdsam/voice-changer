"""Stateful spectral-envelope formant shifting, vocoder, hygiene and character DSP effects."""
import math
import numpy as np


class StreamingEffect:
    pass


class SoftCeilingLimiter(StreamingEffect):
    """Zero-makeup-gain soft-knee peak limiter (1.0 unity gain below threshold)."""
    def __init__(self, threshold=0.75, ceiling=0.97):
        self.threshold = float(threshold)
        self.ceiling = float(ceiling)
        self.headroom = max(1e-4, self.ceiling - self.threshold)

    def reset(self):
        pass

    def __call__(self, audio, sample_rate=48000, **kwargs):
        mag = np.abs(audio)
        over = mag > self.threshold
        if not np.any(over):
            return audio
        out = audio.copy()
        excess = mag[over] - self.threshold
        shaped = self.threshold + self.headroom * np.tanh(excess / self.headroom)
        out[over] = np.sign(audio[over]) * shaped
        return out.astype(np.float32)


class MicConditioner(StreamingEffect):
    """Pre-DSP speech hygiene: gentle downward expander and dynamic 5.5 kHz+ de-esser."""
    def __init__(self, gate_db=-52.0, deess_threshold_db=-24.0):
        from pedalboard import HighpassFilter, HighShelfFilter
        self.gate_db = float(gate_db)
        self.deess_threshold_db = float(deess_threshold_db)
        self._sib_hpf = HighpassFilter(cutoff_frequency_hz=5500.0)
        self._deess_shelf = HighShelfFilter(cutoff_frequency_hz=5500.0, gain_db=0.0)
        self.reset()

    def reset(self):
        self._sib_hpf.reset()
        self._deess_shelf.reset()
        self._deess_shelf.gain_db = 0.0
        self._exp_gain = 1.0
        self._deess_db = 0.0

    def __call__(self, audio, sample_rate, **kwargs):
        frames = audio.shape[1]
        if frames == 0:
            return audio
        # Gentle 2.5:1 downward expander for idle room/fan noise without hard chopping.
        rms = float(np.sqrt(np.mean(audio ** 2)))
        thresh = 10.0 ** (self.gate_db / 20.0)
        if rms >= thresh or rms < 1e-8:
            target_exp = 1.0
        else:
            ratio_db = 20.0 * np.log10(max(rms, 1e-8) / thresh)
            atten_db = max(-24.0, ratio_db * 0.6)  # ~2.5:1 slope
            target_exp = 10.0 ** (atten_db / 20.0)
        alpha_exp = 0.45 if target_exp > self._exp_gain else 0.15
        exp_env = np.linspace(self._exp_gain, self._exp_gain + alpha_exp * (target_exp - self._exp_gain), frames, dtype=np.float32)
        self._exp_gain = float(exp_env[-1])
        cleaned = audio * exp_env

        # Dynamic split-band sidechain driving phase-coherent HighShelfFilter de-esser.
        sib = self._sib_hpf(cleaned, sample_rate, reset=False)
        sib_rms = float(np.sqrt(np.mean(sib ** 2)))
        sib_thresh = 10.0 ** (self.deess_threshold_db / 20.0)
        if sib_rms > sib_thresh:
            over_db = 20.0 * np.log10(sib_rms / max(sib_thresh, 1e-8))
            target_db = max(-10.0, -over_db * 0.85)
        else:
            target_db = 0.0
        alpha_d = 0.55 if target_db < self._deess_db else 0.18
        self._deess_db += alpha_d * (target_db - self._deess_db)
        self._deess_shelf.gain_db = float(self._deess_db)
        return self._deess_shelf(cleaned, sample_rate, reset=False).astype(np.float32)


class RingModulation(StreamingEffect):
    def __init__(self, frequency=70., mix=0.):
        self.frequency, self.mix = frequency, mix
        self.reset()

    def reset(self):
        self.position = 0

    def __call__(self, audio, sample_rate, **kwargs):
        phase = 2 * np.pi * self.frequency * (self.position + np.arange(audio.shape[1])) / sample_rate
        self.position += audio.shape[1]
        return (audio * ((1 - self.mix) + self.mix * np.cos(phase))).astype(np.float32)


class FormantShift(StreamingEffect):
    """Shift a smoothed spectral envelope, leaving harmonic bins and high-frequency consonants intact.

    1024-frame STFT, 256-frame hop, raised-cosine cepstral liftering, overlap-add and aligned dry/wet blending.
    """
    def __init__(self, semitones=0., mix=1.):
        self.semitones, self.mix = semitones, mix
        self.reset()

    def reset(self):
        self.format = None

    def latency_frames(self, rate):
        return 1024

    def __call__(self, audio, sample_rate, **kwargs):
        channels, frames = audio.shape
        n, hop = 1024, 256
        if self.format != (sample_rate, channels):
            self.format = (sample_rate, channels)
            self.input = np.zeros((channels, n - hop), dtype=np.float32)
            self.ola = np.zeros((channels, n), dtype=np.float64)
            self.output = np.zeros((channels, hop), dtype=np.float32)
            self.window = np.sqrt(np.hanning(n + 1)[:-1])
            # Raised-cosine cepstral lifter reduces Gibbs ringing on vowels.
            c_low = max(14, int(sample_rate * 0.00055))
            c_high = min(72, max(c_low + 8, int(sample_rate * 0.00105)))
            lifter = np.ones(n, dtype=np.float64)
            taper_idx = np.arange(c_low, c_high)
            taper = 0.5 * (1.0 + np.cos(np.pi * (taper_idx - c_low) / max(1, c_high - c_low)))
            lifter[c_low:c_high] = taper
            lifter[c_high:n - c_high + 1] = 0.0
            lifter[n - c_high + 1:n - c_low + 1] = taper[::-1]
            self._lifter = lifter
            # Taper formant warp back to 1.0 above 5.5 kHz to keep sibilants crisp.
            freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
            hf = np.ones_like(freqs)
            mask = freqs > 5500.0
            hf[mask] = np.clip(1.0 - (freqs[mask] - 5500.0) / 3500.0, 0.0, 1.0)
            self._hf_taper = hf
        self.input = np.concatenate((self.input, audio), axis=1)
        chunks = []
        bins = np.arange(n // 2 + 1)
        ratio = 2.0 ** (self.semitones / 12.0)
        while self.input.shape[1] >= n:
            spectrum = np.fft.rfft(self.input[:, :n] * self.window, axis=1)
            cepstrum = np.fft.irfft(np.log(np.maximum(abs(spectrum), 1e-7)), n=n, axis=1)
            cepstrum *= self._lifter
            envelope = np.fft.rfft(cepstrum, axis=1).real
            shifted = np.stack([np.interp(bins / ratio, bins, row) for row in envelope])
            raw_gain = np.exp(np.clip(shifted - envelope, -1.1, 1.1))
            # Preserve unvoiced high-frequency consonant balance.
            shaped_gain = 1.0 + self._hf_taper * (raw_gain - 1.0)
            gain = (1.0 - self.mix) + self.mix * shaped_gain
            rendered = np.fft.irfft(spectrum * gain, n=n, axis=1) * self.window / 2
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
    def __init__(self, pitch1=-7, level1=.35, pitch2=7, level2=.25, mix=.3, width=0.0):
        self.pitch1, self.level1, self.pitch2, self.level2, self.mix = pitch1, level1, pitch2, level2, mix
        self.width = float(width)
        self.processors = []
        self.format = None

    def reset(self):
        for processor in self.processors:
            if processor is not None:
                processor.close()
        self.processors = []
        self.format = None

    def latency_frames(self, rate):
        return int(rate * .075)

    def prepare(self, rate, channels):
        from streaming_dsp import SoundTouchPitch
        self.reset()
        self.format = (rate, channels)
        self.delay = np.zeros((channels, int(rate * .075)), dtype=np.float32)
        for pitch, level in ((self.pitch1, self.level1), (self.pitch2, self.level2)):
            self.processors.append(SoundTouchPitch(pitch, rate, channels) if level > 0 and abs(pitch) > .01 else None)

    @property
    def underruns(self):
        return sum(p.underruns for p in self.processors if p is not None)

    def __call__(self, audio, sample_rate, **kwargs):
        if self.format != (sample_rate, audio.shape[0]):
            self.prepare(sample_rate, audio.shape[0])
        pending = np.concatenate((self.delay, audio), axis=1)
        dry = pending[:, :audio.shape[1]].copy()
        self.delay = pending[:, audio.shape[1]:].copy()
        stacked = dry.copy()
        channels = audio.shape[0]
        pan_active = channels == 2 and self.width > 0.0 and any(p is not None for p in self.processors)
        pans = ((1.0 + 0.5 * self.width, 1.0 - 0.5 * self.width),
                (1.0 - 0.5 * self.width, 1.0 + 0.5 * self.width))
        for idx, (processor, level) in enumerate(zip(self.processors, (self.level1, self.level2))):
            if level > 0:
                layer = processor.process(audio) if processor is not None else dry
                if pan_active:
                    p_l, p_r = pans[idx]
                    stacked[0] += level * p_l * layer[0]
                    stacked[1] += level * p_r * layer[1]
                else:
                    stacked += level * layer
        stacked /= 1 + self.level1 + self.level2
        return ((1 - self.mix) * dry + self.mix * stacked).astype(np.float32)


class Resonator(StreamingEffect):
    """Damped short feedback delay for metallic/helmet resonances."""
    def __init__(self, frequency=180, decay=.55, mix=.2):
        from pedalboard import Pedalboard, Delay, LowpassFilter
        self.frequency, self.decay, self.mix = frequency, decay, mix
        self.board = Pedalboard([Delay(delay_seconds=1 / frequency, feedback=decay, mix=1),
                                 LowpassFilter(cutoff_frequency_hz=6500)])

    def reset(self):
        self.board.reset()

    def __call__(self, audio, sample_rate, **kwargs):
        wet = self.board(audio, sample_rate, reset=False) * np.sqrt(1 - self.decay ** 2)
        return ((1 - self.mix) * audio + self.mix * wet).astype(np.float32)


class ToneDelay(StreamingEffect):
    def __init__(self, time_ms=180, feedback=.25, tone_hz=4000, mix=.15):
        from pedalboard import Pedalboard, Delay, LowpassFilter, HighpassFilter
        self.time_ms, self.feedback, self.tone_hz, self.mix = time_ms, feedback, tone_hz, mix
        self.board = Pedalboard([Delay(delay_seconds=time_ms / 1000, feedback=feedback, mix=1),
                                 HighpassFilter(cutoff_frequency_hz=100), LowpassFilter(cutoff_frequency_hz=tone_hz)])

    def reset(self):
        self.board.reset()

    def __call__(self, audio, sample_rate, **kwargs):
        wet = self.board(audio, sample_rate, reset=False)
        return ((1 - self.mix) * audio + self.mix * wet).astype(np.float32)


class ParallelDistortion(StreamingEffect):
    """2x oversampled soft-clipping saturation blended in parallel to minimize aliasing."""
    def __init__(self, drive_db=12, mix=.2):
        self.drive_db, self.mix = drive_db, mix
        self.reset()

    def reset(self):
        self._last = None

    def __call__(self, audio, sample_rate, **kwargs):
        channels, frames = audio.shape
        if frames == 0:
            return audio
        if self._last is None or self._last.shape[0] != channels:
            self._last = np.zeros((channels, 1), dtype=np.float32)
        # 2x linear upsample + 3-tap anti-imaging filter + tanh waveshaper + 2x decimate
        up = np.empty((channels, frames * 2), dtype=np.float32)
        prev = np.concatenate((self._last, audio[:, :-1]), axis=1)
        up[:, 0::2] = 0.5 * (prev + audio)
        up[:, 1::2] = audio
        self._last = audio[:, -1:].copy()
        gain = 10 ** (self.drive_db / 20)
        shaped = np.tanh(up * gain) / np.sqrt(gain)
        # Half-band smoothing [0.25, 0.5, 0.25] before decimation
        padded = np.concatenate((shaped[:, :1], shaped, shaped[:, -1:]), axis=1)
        filtered = 0.25 * padded[:, :-2] + 0.5 * padded[:, 1:-1] + 0.25 * padded[:, 2:]
        wet = filtered[:, 1::2]
        return ((1 - self.mix) * audio + self.mix * wet).astype(np.float32)


class SampleRateReduce(StreamingEffect):
    """Stateful sample-and-hold decimation for authentic 8-bit/arcade digital crunch."""
    def __init__(self, target_rate=9000.0, mix=1.0):
        self.target_rate = float(target_rate)
        self.mix = float(mix)
        self.reset()

    def reset(self):
        self._phase = 0.0
        self._held = None

    def __call__(self, audio, sample_rate, **kwargs):
        channels, frames = audio.shape
        if frames == 0 or self.target_rate >= sample_rate:
            return audio
        if self._held is None or len(self._held) != channels:
            self._held = audio[:, 0].copy()
        step = max(1.0, float(sample_rate) / max(1000.0, self.target_rate))
        # Vectorized zero-order hold indices using continuous phase across blocks
        positions = self._phase + np.arange(frames, dtype=np.float64)
        sample_idx = (np.floor(positions / step) * step - self._phase).astype(np.int64)
        out = np.empty_like(audio)
        first_hold = sample_idx < 0
        if np.any(first_hold):
            out[:, first_hold] = self._held[:, None]
        if np.any(~first_hold):
            valid_idx = np.clip(sample_idx[~first_hold], 0, frames - 1)
            out[:, ~first_hold] = audio[:, valid_idx]
        self._held = out[:, -1].copy()
        self._phase = (self._phase + frames) % step
        return ((1.0 - self.mix) * audio + self.mix * out).astype(np.float32)


class Vocoder(StreamingEffect):
    """16-band STFT channel vocoder with harmonic saw carrier and consonant pass-through."""
    def __init__(self, carrier_hz=115.0, bands=16, mix=0.92):
        self.carrier_hz = float(carrier_hz)
        self.bands = int(bands)
        self.mix = float(mix)
        self.reset()

    def reset(self):
        self.format = None

    def latency_frames(self, rate):
        return 512

    def __call__(self, audio, sample_rate, **kwargs):
        channels, frames = audio.shape
        n, hop = 512, 128
        if self.format != (sample_rate, channels):
            self.format = (sample_rate, channels)
            self.input = np.zeros((channels, n - hop), dtype=np.float32)
            self.ola = np.zeros((channels, n), dtype=np.float64)
            self.output = np.zeros((channels, hop), dtype=np.float32)
            self.window = np.sqrt(np.hanning(n + 1)[:-1])
            self._phase = 0.0
            freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
            # Logarithmically spaced vocoder analysis bands (100 Hz - 4800 Hz)
            edges = np.geomspace(100.0, min(4800.0, sample_rate * 0.45), self.bands + 1)
            self._band_masks = [((freqs >= edges[i]) & (freqs < edges[i + 1])) for i in range(self.bands)]
            self._hf_mask = freqs >= 4500.0
            # Precompute rich harmonic saw/pulse spectrum weights (bandlimited)
            self._carrier_harmonics = np.arange(1, int(min(4500.0, sample_rate * 0.45) // self.carrier_hz) + 1)
        self.input = np.concatenate((self.input, audio), axis=1)
        chunks = []
        while self.input.shape[1] >= n:
            # Generate continuous phase-locked bandlimited carrier frame
            t_idx = self._phase + np.arange(n, dtype=np.float64)
            carrier = np.zeros(n, dtype=np.float64)
            for h in self._carrier_harmonics:
                carrier += np.sin(2.0 * np.pi * (self.carrier_hz * h) * t_idx / sample_rate) / (h ** 0.75)
            carrier /= max(1.0, np.sqrt(np.mean(carrier ** 2)) * 3.5)
            self._phase = (self._phase + hop) % (sample_rate / self.carrier_hz * 100.0)

            carrier_spec = np.fft.rfft(carrier * self.window)
            mod_spec = np.fft.rfft(self.input[:, :n] * self.window, axis=1)
            mod_mag = np.abs(mod_spec)
            car_mag = np.abs(carrier_spec)[None, :] + 1e-6

            synth_spec = np.zeros_like(mod_spec)
            for mask in self._band_masks:
                if not np.any(mask):
                    continue
                mod_e = np.sqrt(np.mean(mod_mag[:, mask] ** 2, axis=1, keepdims=True))
                car_e = np.sqrt(np.mean(car_mag[:, mask] ** 2, axis=1, keepdims=True))
                synth_spec[:, mask] = carrier_spec[None, mask] * (mod_e / car_e)
            # Blend unvoiced >4.5 kHz consonant air so speech remains sharp & intelligible
            synth_spec[:, self._hf_mask] = 0.55 * mod_spec[:, self._hf_mask]

            rendered = np.fft.irfft(synth_spec, n=n, axis=1) * self.window / 2.0
            dry_frame = self.input[:, :n] * (self.window ** 2) / 2.0
            blended = (1.0 - self.mix) * dry_frame + self.mix * rendered
            self.ola += blended
            chunks.append(self.ola[:, :hop].astype(np.float32).copy())
            self.ola[:, :-hop] = self.ola[:, hop:]
            self.ola[:, -hop:] = 0
            self.input = self.input[:, hop:]
        if chunks:
            self.output = np.concatenate((self.output, *chunks), axis=1)
        result = self.output[:, :frames].copy()
        self.output = self.output[:, frames:]
        return result


class DuckedReverb(StreamingEffect):
    """Pre-delayed reverb that gently ducks during active speech and blooms in pauses."""
    def __init__(self, room_size=0.78, damping=0.55, wet_level=0.28, predelay_ms=35.0, duck_amount=0.55):
        from pedalboard import Reverb, HighpassFilter
        self.room_size = float(room_size)
        self.damping = float(damping)
        self.wet_level = float(wet_level)
        self.predelay_ms = float(predelay_ms)
        self.duck_amount = float(duck_amount)
        self._reverb = Reverb(room_size=self.room_size, damping=self.damping, wet_level=1.0, dry_level=0.0)
        self._wet_hpf = HighpassFilter(cutoff_frequency_hz=180.0)
        self.reset()

    def reset(self):
        self._reverb.reset()
        self._wet_hpf.reset()
        self._predelay_buf = None
        self._env = 1.0

    def __call__(self, audio, sample_rate, **kwargs):
        channels, frames = audio.shape
        if frames == 0:
            return audio
        delay_len = max(1, int(sample_rate * self.predelay_ms / 1000.0))
        if self._predelay_buf is None or self._predelay_buf.shape != (channels, delay_len):
            self._predelay_buf = np.zeros((channels, delay_len), dtype=np.float32)
        combined = np.concatenate((self._predelay_buf, audio), axis=1)
        delayed = combined[:, :frames]
        self._predelay_buf = combined[:, frames:].copy()

        wet = self._wet_hpf(self._reverb(delayed, sample_rate, reset=False), sample_rate, reset=False)
        rms = float(np.sqrt(np.mean(audio ** 2)))
        speech_norm = min(1.0, rms / 0.06)
        target_gain = self.wet_level * (1.0 - self.duck_amount * speech_norm)
        alpha = 0.25 if target_gain < self._env else 0.08
        env_curve = np.linspace(self._env, self._env + alpha * (target_gain - self._env), frames, dtype=np.float32)
        self._env = float(env_curve[-1])
        return (audio * 0.95 + wet * env_curve).astype(np.float32)


class CommunicationChannel(StreamingEffect):
    """Handset/radio coloration; radio squelch uses hysteresis and a release hold."""
    def __init__(self, mode=1, drive=3, static=0, click=0, mix=1, gate_db=-44):
        from pedalboard import Pedalboard, HighpassFilter, LowpassFilter, PeakFilter, Compressor, Gain
        self.mode, self.drive, self.static, self.click, self.mix = int(mode), drive, static, click, mix
        self.gate_db = gate_db
        radio = self.mode == 2
        low, high = (380, 2900) if radio else (300, 3400)
        self.board = Pedalboard([HighpassFilter(cutoff_frequency_hz=low), HighpassFilter(cutoff_frequency_hz=low),
            LowpassFilter(cutoff_frequency_hz=high), LowpassFilter(cutoff_frequency_hz=high),
            PeakFilter(cutoff_frequency_hz=1450 if radio else 1800, gain_db=3 if radio else 2),
            Compressor(threshold_db=-28 if radio else -24, ratio=6 if radio else 3.5, attack_ms=3, release_ms=90),
            Gain(gain_db=7.5 if radio else 4.5)])
        self.reset()

    def reset(self):
        self.board.reset()
        self.hold = 0
        self.gain = 0.
        self.open = False
        self.click_remaining = 0
        self.rng = np.random.default_rng(42)

    def __call__(self, audio, sample_rate, **kwargs):
        wet = self.board(audio, sample_rate, reset=False)
        gain = 10 ** (self.drive / 20)
        wet = np.tanh(wet * gain) / gain
        if self.mode == 2:
            frames = audio.shape[1]
            rms = float(np.max(np.sqrt(np.mean(audio ** 2, axis=1))))
            if rms > (10 ** ((self.gate_db - 6) / 20) if self.open else 10 ** (self.gate_db / 20)):
                self.hold = int(sample_rate * .16)
                self.open = True
            else:
                self.hold = max(0, self.hold - frames)
                if self.hold == 0 and self.open:
                    self.open = False
                    self.click_remaining = int(sample_rate * .012)
            target = 1. if self.open else 0.
            ramp = np.clip(self.gain + (target - self.gain) * np.arange(1, frames + 1) / max(1, int(sample_rate * .012)), 0, 1)
            self.gain = float(ramp[-1])
            wet *= ramp
            if self.static:
                wet += self.rng.normal(0, .006 * self.static, wet.shape).astype(np.float32) * ramp
            if self.click and self.click_remaining:
                count = min(frames, self.click_remaining)
                wet[:, :count] += self.rng.normal(0, .045 * self.click, (audio.shape[0], count)).astype(np.float32) * np.linspace(1, 0, count)
                self.click_remaining -= count
        return ((1 - self.mix) * audio + self.mix * wet).astype(np.float32)


class _OverlapAddEffect(StreamingEffect):
    """Shared arbitrary-chunk overlap-add scaffold for STFT and granular effects."""
    def __init__(self, mix=1.0):
        self.mix = float(mix)
        self.format = None

    def reset(self):
        self.format = None
        self._reset_extra()

    def _reset_extra(self):
        pass

    def _window_spec(self, sample_rate):
        raise NotImplementedError

    def _init_format(self, sample_rate, channels, n, hop, freqs):
        pass

    def _render_hop(self, frame, sample_rate):
        raise NotImplementedError

    def __call__(self, audio, sample_rate, **kwargs):
        channels, frames = audio.shape
        if frames == 0:
            return audio
        n, hop, use_sqrt = self._window_spec(sample_rate)
        if self.format != (sample_rate, channels, n, hop):
            self.format = (sample_rate, channels, n, hop)
            self._n, self._hop = n, hop
            self.input = np.zeros((channels, n - hop), dtype=np.float32)
            self.ola = np.zeros((channels, n), dtype=np.float64)
            self.output = np.zeros((channels, hop), dtype=np.float32)
            hann = np.hanning(n + 1)[:-1]
            self.window = np.sqrt(hann) if use_sqrt else hann
            scale = float(n) / (2.0 * hop)
            self._ola_scale = scale if use_sqrt else 1.0
            self._dry_window = (self.window ** 2) / scale if use_sqrt else self.window
            freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
            self._init_format(sample_rate, channels, n, hop, freqs)
        self.input = np.concatenate((self.input, audio), axis=1)
        chunks = []
        while self.input.shape[1] >= self._n:
            frame = self.input[:, :self._n]
            wet_frame = self._render_hop(frame, sample_rate)
            dry_frame = frame * self._dry_window
            self.ola += (1.0 - self.mix) * dry_frame + self.mix * wet_frame
            chunks.append(self.ola[:, :self._hop].astype(np.float32).copy())
            self.ola[:, :-self._hop] = self.ola[:, self._hop:]
            self.ola[:, -self._hop:] = 0
            self.input = self.input[:, self._hop:]
        if chunks:
            self.output = np.concatenate((self.output, *chunks), axis=1)
        result = self.output[:, :frames].copy()
        self.output = self.output[:, frames:]
        return result


class EnvelopeTalkbox(StreamingEffect):
    """Syllable-amplitude-driven dual resonant SVF formant filter (vowel talkbox wah)."""
    def __init__(self, sensitivity=0.075, q=3.8, mix=0.88):
        self.sensitivity = float(sensitivity)
        self.q = float(q)
        self.mix = float(mix)
        self.reset()

    def reset(self):
        self._env = 0.0
        self._states = None

    def __call__(self, audio, sample_rate, **kwargs):
        channels, frames = audio.shape
        if frames == 0:
            return audio
        if self._states is None or len(self._states) != channels:
            self._states = [[0.0, 0.0, 0.0, 0.0] for _ in range(channels)]
        # Pre-saturation supplies warm vowel harmonics for the sweeping resonant filters.
        excited = (np.tanh(audio * 2.1) / 1.7).astype(np.float32)
        k1 = 1.0 / self.q
        k2 = 1.0 / (self.q + 0.4)
        nyq = sample_rate * 0.42
        sub = 16
        exc_lists = excited.tolist()
        raw_lists = audio.tolist()
        out_lists = [[0.0] * frames for _ in range(channels)]
        for start in range(0, frames, sub):
            end = min(frames, start + sub)
            seg = audio[:, start:end]
            rms = float(np.sqrt(np.mean(seg * seg)))
            alpha = 0.32 if rms > self._env else 0.055
            self._env += alpha * (rms - self._env)
            mod = min(1.0, max(0.0, (self._env - 0.004) / max(1e-4, self.sensitivity)) ** 0.72)
            f1 = min(nyq, 285.0 + 575.0 * mod)
            f2 = min(nyq, 900.0 + 1350.0 * mod)
            g1 = math.tan(math.pi * f1 / sample_rate)
            a1_1 = 1.0 / (1.0 + g1 * (g1 + k1))
            a2_1, a3_1 = g1 * a1_1, g1 * g1 * a1_1
            g2 = math.tan(math.pi * f2 / sample_rate)
            a1_2 = 1.0 / (1.0 + g2 * (g2 + k2))
            a2_2, a3_2 = g2 * a1_2, g2 * g2 * a1_2
            for ch in range(channels):
                s1_1, s2_1, s1_2, s2_2 = self._states[ch]
                src = exc_lists[ch]
                dry = raw_lists[ch]
                dst = out_lists[ch]
                for i in range(start, end):
                    v0 = src[i]
                    v3 = v0 - s2_1
                    v1 = a1_1 * s1_1 + a2_1 * v3
                    v2 = s2_1 + a2_1 * s1_1 + a3_1 * v3
                    s1_1, s2_1 = 2.0 * v1 - s1_1, 2.0 * v2 - s2_1
                    u3 = v0 - s2_2
                    u1 = a1_2 * s1_2 + a2_2 * u3
                    u2 = s2_2 + a2_2 * s1_2 + a3_2 * u3
                    s1_2, s2_2 = 2.0 * u1 - s1_2, 2.0 * u2 - s2_2
                    dst[i] = 0.90 * (k1 * v1) + 0.85 * (k2 * u1) + 0.15 * dry[i]
                self._states[ch] = [s1_1, s2_1, s1_2, s2_2]
        wet = np.asarray(out_lists, dtype=np.float32)
        return ((1.0 - self.mix) * audio + self.mix * wet).astype(np.float32)


class Whisperizer(_OverlapAddEffect):
    """STFT spectral-envelope de-voicing with continuous noise excitation (pitchless whisper)."""
    def __init__(self, mix=0.92, seed=101):
        self.seed = int(seed)
        super().__init__(mix=mix)
        self.reset()

    def _reset_extra(self):
        self._rng = np.random.default_rng(self.seed)

    def latency_frames(self, rate):
        return 512

    def _window_spec(self, sample_rate):
        return 512, 128, True

    def _init_format(self, sample_rate, channels, n, hop, freqs):
        self._noise_buf = self._rng.standard_normal((channels, n)).astype(np.float64)
        self._prev_mag = None
        tilt = np.clip((freqs - 160.0) / 650.0, 0.12, 1.0)
        tilt *= 1.0 + 0.32 * np.clip((freqs - 1800.0) / 3000.0, 0.0, 1.0)
        self._tilt = tilt[None, :]
        self._hf_mask = freqs >= 4600.0

    def _render_hop(self, frame, sample_rate):
        n, hop = self._n, self._hop
        self._noise_buf[:, :-hop] = self._noise_buf[:, hop:]
        self._noise_buf[:, -hop:] = self._rng.standard_normal((frame.shape[0], hop))
        noise_spec = np.fft.rfft(self._noise_buf * self.window, axis=1)
        noise_unit = noise_spec / np.maximum(np.abs(noise_spec), 1e-6)
        mod_spec = np.fft.rfft(frame * self.window, axis=1)
        mod_mag = np.abs(mod_spec)
        if self._prev_mag is None or self._prev_mag.shape != mod_mag.shape:
            self._prev_mag = mod_mag.copy()
        else:
            self._prev_mag = 0.4 * self._prev_mag + 0.6 * mod_mag
        synth = noise_unit * self._prev_mag * self._tilt
        synth[:, self._hf_mask] = 0.35 * mod_spec[:, self._hf_mask] + 0.65 * synth[:, self._hf_mask]
        return np.fft.irfft(synth, n=n, axis=1) * self.window / self._ola_scale


class FrequencyShifter(_OverlapAddEffect):
    """Analytic Hilbert STFT Single-Sideband (SSB) linear frequency shifter (f -> f + shift_hz)."""
    def __init__(self, shift_hz=62.0, mix=0.78):
        self.shift_hz = float(shift_hz)
        super().__init__(mix=mix)
        self.reset()

    def _reset_extra(self):
        self._phase = 0.0

    def latency_frames(self, rate):
        return 512

    def _window_spec(self, sample_rate):
        return 512, 128, True

    def _init_format(self, sample_rate, channels, n, hop, freqs):
        self._phase = 0.0

    def _render_hop(self, frame, sample_rate):
        n, hop = self._n, self._hop
        mod_spec = np.fft.rfft(frame * self.window, axis=1)
        analytic = np.zeros((frame.shape[0], n), dtype=np.complex128)
        analytic[:, 0] = mod_spec[:, 0]
        analytic[:, 1:n // 2] = 2.0 * mod_spec[:, 1:n // 2]
        analytic[:, n // 2] = mod_spec[:, n // 2]
        z = np.fft.ifft(analytic, n=n, axis=1)
        t_phase = self._phase + 2.0 * np.pi * self.shift_hz * np.arange(n) / sample_rate
        self._phase = (self._phase + 2.0 * np.pi * self.shift_hz * hop / sample_rate) % (2.0 * np.pi)
        shifted = (z * np.exp(1j * t_phase)[None, :]).real
        return shifted * self.window / self._ola_scale


class SubharmonicTitan(StreamingEffect):
    """Zero-latency divide-by-2 vocal fundamental sub-octave generator with HF air exciter."""
    def __init__(self, sub_level=0.75, exciter_mix=0.22):
        from pedalboard import HighpassFilter, LowpassFilter
        self.sub_level = float(sub_level)
        self.exciter_mix = float(exciter_mix)
        self._bp_hpf = HighpassFilter(cutoff_frequency_hz=75.0)
        self._bp_lpf = LowpassFilter(cutoff_frequency_hz=235.0)
        self._sub_lpf1 = LowpassFilter(cutoff_frequency_hz=150.0)
        self._sub_lpf2 = LowpassFilter(cutoff_frequency_hz=150.0)
        self._exc_hpf = HighpassFilter(cutoff_frequency_hz=4200.0)
        self.reset()

    def reset(self):
        for flt in (self._bp_hpf, self._bp_lpf, self._sub_lpf1, self._sub_lpf2, self._exc_hpf):
            flt.reset()
        self._prev_sample = 0.0
        self._parity = 0
        self._env = 0.0

    def __call__(self, audio, sample_rate, **kwargs):
        frames = audio.shape[1]
        if frames == 0:
            return audio
        mono = np.mean(audio, axis=0, keepdims=True)
        fund = self._bp_lpf(self._bp_hpf(mono, sample_rate, reset=False), sample_rate, reset=False)[0]
        combined = np.concatenate((np.array([self._prev_sample], dtype=np.float32), fund))
        self._prev_sample = float(fund[-1])
        edges = ((combined[:-1] <= 0.0) & (combined[1:] > 0.0)).astype(np.int64)
        parity = (np.cumsum(edges) + self._parity) & 1
        self._parity = int(parity[-1])
        sub_sq = np.where(parity == 0, 1.0, -1.0).astype(np.float32)

        rms = float(np.sqrt(np.mean(fund * fund)))
        gate = min(1.0, rms / 0.004)
        target_gain = min(0.45, rms * 1.55) * gate * self.sub_level
        alpha = 0.45 if target_gain > self._env else 0.14
        env_curve = np.linspace(self._env, self._env + alpha * (target_gain - self._env), frames, dtype=np.float32)
        self._env = float(env_curve[-1])

        sub = self._sub_lpf1(sub_sq[None, :] * env_curve[None, :], sample_rate, reset=False)
        sub = self._sub_lpf2(sub, sample_rate, reset=False)
        hf = self._exc_hpf(audio, sample_rate, reset=False)
        exciter = (np.tanh(hf * 2.8) * self.exciter_mix).astype(np.float32)
        return (audio * 0.92 + sub + exciter).astype(np.float32)


class ReverseGranulator(_OverlapAddEffect):
    """Overlapping dual-head Hann-windowed granular time-reversal processor."""
    def __init__(self, grain_ms=85.0, mix=0.88):
        self.grain_ms = float(grain_ms)
        super().__init__(mix=mix)
        self.reset()

    def latency_frames(self, rate):
        return max(256, int(round(rate * self.grain_ms / 1000.0)) // 2 * 2)

    def _window_spec(self, sample_rate):
        n = self.latency_frames(sample_rate)
        return n, n // 2, False

    def _render_hop(self, frame, sample_rate):
        return frame[:, ::-1] * self.window


class ShimmerReverb(StreamingEffect):
    """Granular +12 st octave-up feedback reverb cloud layered under clean dry speech."""
    def __init__(self, room_size=0.86, damping=0.42, wet_level=0.35, shimmer_feedback=0.32, duck_amount=0.45):
        from pedalboard import Reverb, HighpassFilter
        self.room_size = float(room_size)
        self.damping = float(damping)
        self.wet_level = float(wet_level)
        self.shimmer_feedback = float(shimmer_feedback)
        self.duck_amount = float(duck_amount)
        self._reverb = Reverb(room_size=self.room_size, damping=self.damping, wet_level=1.0, dry_level=0.0)
        self._wet_hpf = HighpassFilter(cutoff_frequency_hz=380.0)
        self.reset()

    def reset(self):
        self._reverb.reset()
        self._wet_hpf.reset()
        self._format = None
        self._fb = None
        self._env = 1.0

    def _octave_up(self, signal):
        n, hop = 2048, 1024
        channels, frames = signal.shape
        if self._format != channels:
            self._format = channels
            self._in = np.zeros((channels, n - hop), dtype=np.float32)
            self._ola = np.zeros((channels, n), dtype=np.float64)
            self._out = np.zeros((channels, hop), dtype=np.float32)
            self._win = np.hanning(n + 1)[:-1]
            self._x_idx = np.linspace(0.0, n - 1.0, hop, dtype=np.float64)
            self._x_full = np.arange(n, dtype=np.float64)
        self._in = np.concatenate((self._in, signal), axis=1)
        chunks = []
        while self._in.shape[1] >= n:
            frame = self._in[:, :n]
            up = np.empty_like(frame)
            for ch in range(channels):
                half = np.interp(self._x_idx, self._x_full, frame[ch])
                up[ch, :hop] = half
                up[ch, hop:] = half
            self._ola += up * self._win
            chunks.append(self._ola[:, :hop].astype(np.float32).copy())
            self._ola[:, :-hop] = self._ola[:, hop:]
            self._ola[:, -hop:] = 0
            self._in = self._in[:, hop:]
        if chunks:
            self._out = np.concatenate((self._out, *chunks), axis=1)
        result = self._out[:, :frames].copy()
        self._out = self._out[:, frames:]
        return result

    def __call__(self, audio, sample_rate, **kwargs):
        channels, frames = audio.shape
        if frames == 0:
            return audio
        if self._fb is None or self._fb.shape != (channels, frames):
            fb = np.zeros((channels, frames), dtype=np.float32)
        else:
            fb = self._fb
        drive = audio * 0.65 + np.tanh(fb * 0.8) * self.shimmer_feedback
        shimmered = self._octave_up(drive)
        wet = self._wet_hpf(self._reverb(shimmered, sample_rate, reset=False), sample_rate, reset=False)
        self._fb = wet.copy()

        rms = float(np.sqrt(np.mean(audio * audio)))
        speech_norm = min(1.0, rms / 0.06)
        target_gain = self.wet_level * (1.0 - self.duck_amount * speech_norm)
        alpha = 0.25 if target_gain < self._env else 0.08
        env_curve = np.linspace(self._env, self._env + alpha * (target_gain - self._env), frames, dtype=np.float32)
        self._env = float(env_curve[-1])
        return (audio * 0.92 + wet * env_curve).astype(np.float32)


class TapeWowFlutter(StreamingEffect):
    """Dual-LFO fractional delay tape pitch warble with asymmetric magnetic hysteresis."""
    def __init__(self, wow_hz=0.85, wow_ms=4.2, flutter_hz=5.9, flutter_ms=0.45,
                 drive=1.8, hiss_level=0.006, seed=202):
        self.wow_hz = float(wow_hz)
        self.wow_ms = float(wow_ms)
        self.flutter_hz = float(flutter_hz)
        self.flutter_ms = float(flutter_ms)
        self.drive = float(drive)
        self.hiss_level = float(hiss_level)
        self.seed = int(seed)
        self.reset()

    def reset(self):
        self._buf = None
        self._rate = None
        self._wow_phase = 0.0
        self._flt_phase = 0.0
        self._drift = 0.0
        self._rng = np.random.default_rng(self.seed)

    def latency_frames(self, rate):
        return int(round(rate * 0.008))

    def __call__(self, audio, sample_rate, **kwargs):
        channels, frames = audio.shape
        if frames == 0:
            return audio
        hist_len = max(128, int(round(sample_rate * 0.022)))
        if self._buf is None or self._buf.shape != (channels, hist_len) or self._rate != sample_rate:
            self._buf = np.zeros((channels, hist_len), dtype=np.float32)
            self._rate = sample_rate
        combined = np.concatenate((self._buf, audio), axis=1)
        t = np.arange(frames, dtype=np.float64) / sample_rate
        wow_p = self._wow_phase + 2.0 * np.pi * self.wow_hz * t
        flt_p = self._flt_phase + 2.0 * np.pi * self.flutter_hz * t
        self._wow_phase = (self._wow_phase + 2.0 * np.pi * self.wow_hz * frames / sample_rate) % (2.0 * np.pi)
        self._flt_phase = (self._flt_phase + 2.0 * np.pi * self.flutter_hz * frames / sample_rate) % (2.0 * np.pi)

        target_drift = float(self._rng.uniform(-1.0, 1.0)) * (0.0012 * sample_rate)
        drift_curve = np.linspace(self._drift, self._drift + 0.12 * (target_drift - self._drift), frames, dtype=np.float64)
        self._drift = float(drift_curve[-1])

        center = self.latency_frames(sample_rate)
        delay_samples = np.clip(
            center
            + (self.wow_ms * 0.001 * sample_rate) * np.sin(wow_p)
            + (self.flutter_ms * 0.001 * sample_rate) * np.sin(flt_p)
            + drift_curve,
            1.0,
            float(hist_len - 2),
        )
        read_pos = hist_len + np.arange(frames, dtype=np.float64) - delay_samples
        idx0 = np.floor(read_pos).astype(np.int64)
        frac = (read_pos - idx0).astype(np.float32)
        warped = combined[:, idx0] * (1.0 - frac[None, :]) + combined[:, idx0 + 1] * frac[None, :]
        self._buf = combined[:, -hist_len:].copy()

        x = warped * self.drive
        sat = (np.tanh(x + 0.14 * np.clip(x * x, 0.0, 2.0)) / np.sqrt(self.drive)).astype(np.float32)
        if self.hiss_level > 0.0:
            rms = float(np.sqrt(np.mean(audio * audio)))
            hiss_scale = self.hiss_level * min(1.0, rms / 0.025)
            sat = sat + self._rng.normal(0.0, hiss_scale, sat.shape).astype(np.float32)
        return sat

