import tempfile
import unittest
from pathlib import Path
import numpy as np
import voices
from engine import AudioEngine


class AudioTests(unittest.TestCase):
    def test_continuous_presets(self):
        for rate in (44100, 48000):
            signal = (.12 * np.sin(2*np.pi*180*np.arange(rate)/rate)).astype(np.float32)
            for name, preset in voices.VOICE_PRESETS.items():
                engine = AudioEngine(sample_rate=rate, blocksize=512)
                engine.set_voice(preset['builder']())
                blocks = []
                for offset in range(0, len(signal)-512, 512):
                    output = np.zeros((512, 2), dtype=np.float32)
                    engine._audio_callback(signal[offset:offset+512, None], output, 512, None, None)
                    self.assertIsNone(engine.last_error, name)
                    self.assertTrue(np.isfinite(output).all(), name)
                    self.assertLessEqual(float(np.max(np.abs(output))), 1, name)
                    blocks.append(output.copy())
                self.assertGreater(np.sqrt(np.mean(np.concatenate(blocks)[rate//4:]**2)), .001, name)

    def test_native_pitch_accuracy_and_continuity(self):
        from streaming_dsp import SoundTouchPitch
        for rate in (44100, 48000):
            for shift in (-12, -6, -2, 2, 5, 12):
                processor = SoundTouchPitch(shift, rate, 2)
                try:
                    timeline = np.arange(rate * 3) / rate
                    tone = (.15 * np.sin(2 * np.pi * 220 * timeline)).astype(np.float32)
                    chunks = []
                    for offset in range(0, len(tone)-512, 512):
                        block = np.stack([tone[offset:offset+512]] * 2)
                        chunks.append(processor.process(block))
                    result = np.concatenate(chunks, axis=1)
                    self.assertEqual(processor.underruns, 0)
                    np.testing.assert_allclose(result[0], result[1], atol=1e-6)
                    steady = result[0, rate:]
                    peak = np.argmax(abs(np.fft.rfft(steady * np.hanning(len(steady))))) * rate / len(steady)
                    self.assertAlmostEqual(peak, 220 * 2 ** (shift / 12), delta=1)
                    # Continuous tone must not acquire silent callback-sized gaps.
                    for offset in range(rate, result.shape[1]-512, 512):
                        self.assertGreater(np.sqrt(np.mean(result[:, offset:offset+512]**2)), .02)
                finally:
                    processor.close()

    def test_effect_order_is_preserved(self):
        from pedalboard import Pedalboard, PitchShift, Gain
        from streaming_dsp import VoiceChain
        chain = VoiceChain([Gain(gain_db=-2), PitchShift(semitones=2), Gain(gain_db=2)], Pedalboard, PitchShift)
        self.assertEqual(len(chain.stages), 3)
        self.assertEqual(chain.stages[1], 2.)

    def test_reverb_tail_survives_blocks(self):
        board = voices.create_cathedral_voice()
        impulse = np.zeros((1, 512), dtype=np.float32)
        impulse[0, 0] = .5
        board(impulse, 48000, reset=False)
        tail = [board(np.zeros_like(impulse), 48000, reset=False) for _ in range(30)]
        self.assertGreater(np.max(np.abs(np.concatenate(tail, axis=1))), .00001)

    def test_preset_round_trip_and_validation(self):
        original = voices.CUSTOM_PRESETS_FILE
        try:
            with tempfile.TemporaryDirectory() as folder:
                voices.CUSTOM_PRESETS_FILE = str(Path(folder)/'voices.json')
                voices.save_user_preset('My voice', -3, 2, .2, 12)
                self.assertEqual(voices.load_user_presets()['My voice']['params']['pitch'], -3)
                with self.assertRaises(ValueError):
                    voices.save_user_preset('Broken', float('nan'), 0, 0)
                self.assertIn('My voice', voices.load_user_presets())
                voices.delete_user_preset('My voice')
                self.assertEqual(voices.load_user_presets(), {})
        finally:
            voices.CUSTOM_PRESETS_FILE = original


if __name__ == '__main__':
    unittest.main()
