import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import voices
from voice_effects import Harmony,Resonator,ToneDelay,ParallelDistortion


class CharacterEffectsTests(unittest.TestCase):
    def test_harmony_contains_both_shifted_layers(self):
        rate=48000
        source=(.15*np.sin(2*np.pi*220*np.arange(rate*3)/rate)).astype('float32')[None,:]
        effect=Harmony(-7,.7,7,.7,1)
        output=np.concatenate([effect(source[:,i:i+512],rate) for i in range(0,source.shape[1],512)],axis=1)[0,rate:]
        spectrum=abs(np.fft.rfft(output*np.hanning(len(output))))
        frequencies=np.fft.rfftfreq(len(output),1/rate)
        for expected in (220,220*2**(-7/12),220*2**(7/12)):
            region=abs(frequencies-expected)<2
            self.assertGreater(spectrum[region].max(),50)
        self.assertEqual(effect.underruns,0)
        effect.reset()

    def test_harmony_lead_and_unshifted_layers_are_aligned(self):
        source=np.random.default_rng(4).normal(0,.03,(2,12000)).astype('float32')
        effect=Harmony(0,.4,0,.3,.7)
        output=np.concatenate([effect(source[:,i:i+333],48000) for i in range(0,12000,333)],axis=1)
        delay=effect.latency_frames(48000)
        np.testing.assert_allclose(output[:,delay:],source[:,:-delay],atol=1e-6)
        effect.reset()

    def test_delay_and_resonator_emit_stable_tails(self):
        for effect in (ToneDelay(100,.4,3000,1),Resonator(200,.7,1)):
            source=np.zeros((1,48000),dtype='float32');source[0,0]=.5
            output=np.concatenate([effect(source[:,i:i+512],48000) for i in range(0,48000,512)],axis=1)
            self.assertTrue(np.isfinite(output).all())
            self.assertGreater(abs(output[:,240:]).max(),.001)
            self.assertLess(abs(output[:,-512:]).max(),.001)
            self.assertLess(abs(output).max(),.5)
        delay=ToneDelay(100,0,5000,1)
        impulse=np.zeros((1,6000),dtype='float32');impulse[0,0]=1
        output=delay(impulse,48000)
        self.assertLess(abs(int(np.argmax(abs(output[0])))-4800),20)

    def test_bypass_and_parameter_validation(self):
        original=voices.create_custom_voice()
        bypass=voices.create_custom_voice(harmony_enabled=0,harmony_mix=.8,resonator_enabled=0,resonator_mix=.8,
                         delay_enabled=0,delay_mix=.8,parallel_enabled=0,parallel_mix=.8)
        source=np.random.default_rng(2).normal(0,.03,(1,48000)).astype('float32')
        np.testing.assert_allclose(original(source,48000),bypass(source,48000),atol=1e-6)
        for extras in ({'delay_feedback':.9},{'resonator_decay':1},{'harmony_pitch1':20},{'parallel_enabled':.5}):
            with self.assertRaises(ValueError):voices.create_custom_voice(**extras)
        distortion=ParallelDistortion(20,.3)
        self.assertTrue(np.isfinite(distortion(source,48000)).all())

    def test_new_settings_round_trip(self):
        settings=dict(harmony_pitch1=-5,harmony_mix=.5,resonator_hz=220,resonator_mix=.2,
                      delay_ms=250,delay_mix=.3,parallel_drive=18,parallel_mix=.2,delay_enabled=0)
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(voices,'CUSTOM_PRESETS_FILE',str(Path(folder)/'voices.json')):
                voices.save_user_preset('Layers',0,0,0,16,**settings)
                preset=voices.load_user_presets()['Layers']
                for k,v in settings.items():self.assertEqual(preset['params'][k],v)
                self.assertTrue(preset['builder']())
        for name in ('Space Marine','Ghost','Goblin','Hive Mind'):
            self.assertIn(name,voices.VOICE_PRESETS)


if __name__=='__main__':unittest.main()
