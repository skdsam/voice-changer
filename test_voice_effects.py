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


if __name__=='__main__':
    unittest.main()
