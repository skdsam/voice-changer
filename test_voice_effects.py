"""Behavior checks for custom voice effects and backward-compatible settings."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import voices
from voice_effects import FormantShift, RingModulation


class VoiceEffectTests(unittest.TestCase):
    def test_ring_sidebands_and_phase_continuity(self):
        rate = 48000
        source = np.cos(2*np.pi*440*np.arange(rate)/rate).astype('float32')[None, :]
        effect = RingModulation(70, 1)
        streamed = np.concatenate([effect(source[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        expected = source * np.cos(2*np.pi*70*np.arange(rate)/rate)
        np.testing.assert_allclose(streamed, expected, atol=1e-6)
        spectrum = abs(np.fft.rfft(streamed[0]))
        self.assertEqual(set(np.argsort(spectrum)[-2:]), {370, 510})
        np.testing.assert_allclose(RingModulation(70, 0)(source, rate), source)

    def test_formant_envelope_moves_without_moving_harmonics(self):
        rate = 48000
        time = np.arange(rate*2)/rate
        source = np.zeros_like(time)
        for hz in range(120, 6000, 120):
            amplitude = np.exp(-.5*((hz-800)/180)**2) + .6*np.exp(-.5*((hz-2200)/280)**2)
            source += amplitude*np.sin(2*np.pi*hz*time)
        source = (source/max(abs(source))*.15).astype('float32')[None, :]
        peaks = []
        for shift in (-6, 0, 6):
            effect = FormantShift(shift)
            output = np.concatenate([effect(source[:, i:i+512], rate) for i in range(0, source.shape[1], 512)], axis=1)
            steady = output[0, rate//2:]
            spectrum = abs(np.fft.rfft(steady*np.hanning(len(steady))))
            frequency = np.fft.rfftfreq(len(steady), 1/rate)
            peak = frequency[np.argmax(spectrum*(frequency<1600))]
            peaks.append(peak)
            self.assertLess(abs(peak/120-round(peak/120)), .01)
            self.assertTrue(np.isfinite(output).all())
        self.assertLess(peaks[0], peaks[1])
        self.assertLess(peaks[1], peaks[2])

    def test_formant_chunk_invariance_and_dry_alignment(self):
        source = np.random.default_rng(12).normal(0,.04,(2,12000)).astype('float32')
        for mix in (0, .5, 1):
            whole = FormantShift(3, mix)(source, 44100)
            effect = FormantShift(3, mix)
            blocks = np.concatenate([effect(source[:, i:i+333], 44100) for i in range(0,12000,333)],axis=1)
            np.testing.assert_allclose(blocks,whole,atol=1e-6)
        # Zero blend reconstructs the delayed original, rather than comb filtering it.
        output = FormantShift(4, 0)(source,44100)
        np.testing.assert_allclose(output[:,1024:],source[:,:-1024],atol=1e-6)

    def test_combined_effects_stream(self):
        for rate in (44100, 48000):
            effect = voices.create_custom_voice(-2,.2,2,14,formant=3,warmth=2,presence=1,
                        brightness=-2,doubler_mix=.4,ring_hz=85,ring_mix=.25)
            source = np.random.default_rng(6).normal(0,.04,(2,rate*3)).astype('float32')
            output = np.concatenate([effect(source[:,i:i+512],rate,reset=False)
                                    for i in range(0,source.shape[1],512)],axis=1)
            self.assertEqual(output.shape,source.shape)
            self.assertTrue(np.isfinite(output).all())
            self.assertEqual(effect.underruns,0)
            self.assertGreater(np.sqrt(np.mean(output[:,rate:]**2)),.001)

    def test_old_and_new_preset_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'voices.json'
            path.write_text(json.dumps({'Legacy':dict(pitch=1,distortion=0,reverb=0,bitcrush=16)}))
            with patch.object(voices,'CUSTOM_PRESETS_FILE',str(path)):
                legacy = voices.load_user_presets()['Legacy']['params']
                self.assertTrue(all(legacy[k]==v for k,v in voices.EXTRA_DEFAULTS.items()))
                voices.save_user_preset('New',0,0,0,16,formant=3,ring_mix=.4,doubler_mix=.3,warmth=2)
                preset = voices.load_user_presets()['New']
                self.assertEqual(preset['params']['ring_mix'],.4)
                preset['builder']()
                for extras in ({'formant':7},{'ring_hz':0},{'ring_mix':float('nan')},{'warmth':10}):
                    with self.assertRaises(ValueError):
                        voices.save_user_preset('Invalid',0,0,0,16,**extras)
                self.assertIn('Legacy',voices.load_user_presets())

    def test_soft_ceiling_limiter_unity_below_threshold_and_bounds_peaks(self):
        from voice_effects import SoftCeilingLimiter
        lim = SoftCeilingLimiter(threshold=0.75, ceiling=0.97)
        quiet = (np.sin(2*np.pi*440*np.arange(1024)/48000) * 0.3).astype('float32')[None, :]
        np.testing.assert_allclose(lim(quiet, 48000), quiet, atol=1e-6)
        hot = np.full((2, 512), 2.5, dtype='float32')
        bounded = lim(hot, 48000)
        self.assertLessEqual(float(np.max(np.abs(bounded))), 0.97)
        self.assertGreater(float(np.min(bounded)), 0.75)

    def test_mic_conditioner_attenuates_idle_noise_and_sibilance(self):
        from voice_effects import MicConditioner
        cond = MicConditioner(gate_db=-52.0, deess_threshold_db=-24.0)
        zeros = np.zeros((1, 512), dtype='float32')
        np.testing.assert_allclose(cond(zeros, 48000), zeros)
        idle = np.random.default_rng(3).normal(0, 0.0005, (1, 16000)).astype('float32')
        out_idle = np.concatenate([cond(idle[:, i:i+512], 48000) for i in range(0, idle.shape[1], 512)], axis=1)
        self.assertLess(float(np.sqrt(np.mean(out_idle[:, 8000:]**2))), float(np.sqrt(np.mean(idle[:, 8000:]**2))) * 0.7)
        cond.reset()
        sib = (0.25 * np.sin(2*np.pi*7000*np.arange(9600)/48000)).astype('float32')[None, :]
        out_sib = np.concatenate([cond(sib[:, i:i+512], 48000) for i in range(0, sib.shape[1], 512)], axis=1)
        self.assertLess(float(np.sqrt(np.mean(out_sib[:, 4800:]**2))), float(np.sqrt(np.mean(sib[:, 4800:]**2))) * 0.7)

    def test_vocoder_sample_reduce_and_ducked_reverb(self):
        from voice_effects import Vocoder, SampleRateReduce, DuckedReverb, Harmony
        rate = 48000
        t = np.arange(rate) / rate
        speech = (0.15 * np.sin(2*np.pi*160*t) + 0.08 * np.sin(2*np.pi*640*t)).astype('float32')[None, :]
        voc = Vocoder(carrier_hz=115.0, bands=16, mix=0.92)
        out_voc = np.concatenate([voc(speech[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        self.assertEqual(out_voc.shape, speech.shape)
        self.assertTrue(np.isfinite(out_voc).all())
        self.assertGreater(float(np.sqrt(np.mean(out_voc[:, rate//2:]**2))), 0.02)

        sr_red = SampleRateReduce(8500.0, mix=1.0)
        out_sr = np.concatenate([sr_red(speech[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        self.assertEqual(out_sr.shape, speech.shape)
        self.assertTrue(np.isfinite(out_sr).all())

        rev = DuckedReverb(room_size=0.8, wet_level=0.35, predelay_ms=35.0, duck_amount=0.6)
        imp = np.zeros((1, 512), dtype='float32')
        imp[0, 0] = 0.4
        rev(imp, rate)
        tail = np.concatenate([rev(np.zeros_like(imp), rate) for _ in range(25)], axis=1)
        self.assertGreater(float(np.max(np.abs(tail))), 0.001)

        stereo = np.repeat(speech, 2, axis=0)
        harm = Harmony(-7, 0.5, 7, 0.5, 0.7, width=0.65)
        out_h = np.concatenate([harm(stereo[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        self.assertGreater(float(np.max(np.abs(out_h[0] - out_h[1]))), 0.005)
        harm.reset()

    def test_unique_dsp_effects_behaviors(self):
        from voice_effects import (
            EnvelopeTalkbox, Whisperizer, FrequencyShifter, SubharmonicTitan,
            ReverseGranulator, ShimmerReverb, TapeWowFlutter,
        )
        rate = 48000
        t = np.arange(rate, dtype=np.float32) / rate

        # 1. EnvelopeTalkbox: louder excitation sweeps spectral centroid higher
        tb = EnvelopeTalkbox(sensitivity=0.075, q=4.0, mix=1.0)
        saw = (sum(np.sin(2*np.pi*140*k*t)/k for k in range(1, 18))).astype('float32')
        pulse = (saw / float(np.max(np.abs(saw))))[None, :]
        out_low = np.concatenate([tb((pulse * 0.03)[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        tb.reset()
        out_hi = np.concatenate([tb((pulse * 0.25)[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        freqs = np.fft.rfftfreq(rate // 2, 1.0 / rate)
        def centroid(seg):
            mag = np.abs(np.fft.rfft(seg))
            return float(np.sum(freqs * mag) / np.maximum(np.sum(mag), 1e-8))
        self.assertGreater(centroid(out_hi[0, rate // 2:]), centroid(out_low[0, rate // 2:]) + 150.0)

        # 2. Whisperizer: removes periodic tonal dominance & stays deterministic on reset
        wh = Whisperizer(mix=1.0, seed=101)
        tone220 = (0.18 * np.sin(2*np.pi*220*t)).astype('float32')[None, :]
        out_w1 = np.concatenate([wh(tone220[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        wh.reset()
        out_w2 = np.concatenate([wh(tone220[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        np.testing.assert_allclose(out_w1, out_w2, atol=1e-6)
        mag_in = np.abs(np.fft.rfft(tone220[0, rate // 2:]))
        mag_out = np.abs(np.fft.rfft(out_w1[0, rate // 2:]))
        self.assertLess(float(np.max(mag_out) / (np.sum(mag_out) + 1e-8)),
                        float(np.max(mag_in) / (np.sum(mag_in) + 1e-8)) * 0.25)

        # 3. FrequencyShifter: linear SSB +62 Hz shift (200 -> ~262 Hz) with suppressed image (138 Hz)
        fs = FrequencyShifter(shift_hz=62.0, mix=1.0)
        tone200 = (0.18 * np.sin(2*np.pi*200*t)).astype('float32')[None, :]
        out_fs = np.concatenate([fs(tone200[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        seg = out_fs[0, rate // 2:] * np.hanning(rate // 2)
        spec = np.abs(np.fft.rfft(seg))
        pk_hz = float(freqs[int(np.argmax(spec))])
        self.assertAlmostEqual(pk_hz, 262.0, delta=3.0)
        img_energy = float(np.max(spec[(freqs >= 132) & (freqs <= 144)]))
        self.assertLess(img_energy, float(np.max(spec)) * 0.08)

        # 4. SubharmonicTitan: creates strong f0/2 (~90 Hz) under 180 Hz fundamental
        sub = SubharmonicTitan(sub_level=0.9, exciter_mix=0.2)
        tone180 = (0.15 * np.sin(2*np.pi*180*t)).astype('float32')[None, :]
        out_sub = np.concatenate([sub(tone180[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        sub_spec = np.abs(np.fft.rfft(out_sub[0, rate // 2:] * np.hanning(rate // 2)))
        e90 = float(np.max(sub_spec[(freqs >= 85) & (freqs <= 95)]))
        e180 = float(np.max(sub_spec[(freqs >= 175) & (freqs <= 185)]))
        self.assertGreater(e90, e180 * 0.20)

        # 5. ReverseGranulator: finite, unity latency contract and reverses transient slopes
        rg = ReverseGranulator(grain_ms=85.0, mix=1.0)
        self.assertGreater(rg.latency_frames(rate), 3000)
        out_rg = np.concatenate([rg(pulse[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        self.assertTrue(np.isfinite(out_rg).all())
        self.assertGreater(float(np.sqrt(np.mean(out_rg[:, rate // 2:]**2))), 0.02)

        # 6. ShimmerReverb: octave-up (~440 Hz) content appears in decaying tail after 220 Hz burst
        shm = ShimmerReverb(room_size=0.85, damping=0.4, wet_level=0.45, shimmer_feedback=0.35, duck_amount=0.3)
        burst = np.zeros((1, rate), dtype='float32')
        burst[0, :rate // 3] = (0.20 * np.sin(2*np.pi*220*t[:rate // 3])).astype('float32')
        out_shm = np.concatenate([shm(burst[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        tail_seg = out_shm[0, rate // 2:rate] * np.hanning(rate - rate // 2)
        t_freqs = np.fft.rfftfreq(len(tail_seg), 1.0 / rate)
        t_spec = np.abs(np.fft.rfft(tail_seg))
        e440 = float(np.max(t_spec[(t_freqs >= 425) & (t_freqs <= 455)]))
        self.assertGreater(e440, 1.0)

        # 7. TapeWowFlutter: continuous pitch wobble & deterministic reset
        tape = TapeWowFlutter(wow_hz=1.2, wow_ms=4.5, flutter_hz=6.0, flutter_ms=0.5, drive=1.6, hiss_level=0.005)
        tone1k = (0.15 * np.sin(2*np.pi*1000*t)).astype('float32')[None, :]
        out_t1 = np.concatenate([tape(tone1k[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        tape.reset()
        out_t2 = np.concatenate([tape(tone1k[:, i:i+512], rate) for i in range(0, rate, 512)], axis=1)
        np.testing.assert_allclose(out_t1, out_t2, atol=1e-6)
        side_spec = np.abs(np.fft.rfft(out_t1[0, rate // 2:] * np.hanning(rate // 2)))
        # Modulation spreads energy beyond pure 1000 Hz bin
        self.assertGreater(float(np.sum(side_spec[(freqs >= 940) & (freqs <= 1060)])), float(np.max(side_spec)) * 2.5)


if __name__=='__main__':
    unittest.main()
