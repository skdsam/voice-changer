import unittest
import numpy as np
from comparison import render_comparison,level_match
from voices import VOICE_PRESETS,create_custom_voice
from voice_effects import CommunicationChannel


class QualityTests(unittest.TestCase):
    def test_comparison_level_matches_and_limits_peaks(self):
        rate=48000;t=np.arange(rate)/rate
        source=(.1*np.sin(2*np.pi*220*t)).astype('float32')
        original,processed,note=level_match(source,source*.1,rate)
        np.testing.assert_allclose(original,processed,atol=1e-6)
        self.assertLessEqual(max(abs(original).max(),abs(processed).max()),.890001)
        self.assertIn('RMS',note)

    def test_comparison_preserves_duration_and_quiet_input(self):
        rate=44100
        source=np.zeros(rate,dtype='float32')
        for name in ('Telephone','Walkie-Talkie','Kid (DSP prototype)','Hive Mind'):
            original,processed,note=render_comparison(source,rate,VOICE_PRESETS[name]['builder'])
            self.assertEqual(original.shape,processed.shape)
            self.assertEqual(len(original),rate*3)
            self.assertTrue(np.isfinite(processed).all())
            self.assertIn('quiet',note)
        with self.assertRaises(ValueError):render_comparison(source[:10],rate,VOICE_PRESETS['Clean (Normal)']['builder'])

    def test_telephone_rejects_out_of_band_tones(self):
        rate=48000
        energies=[]
        for hz in (90,1400,9000):
            x=(.04*np.sin(2*np.pi*hz*np.arange(rate)/rate)).astype('float32')[None,:]
            effect=CommunicationChannel(1,drive=0)
            output=np.concatenate([effect(x[:,i:i+512],rate) for i in range(0,rate,512)],axis=1)
            energies.append(float(np.sqrt(np.mean(output[:,rate//4:]**2))))
        self.assertGreater(energies[1],energies[0]*5)
        self.assertGreater(energies[1],energies[2]*5)

    def test_radio_squelch_releases_and_texture_is_optional(self):
        rate=48000
        effect=CommunicationChannel(2,static=0,click=0)
        silence=np.zeros((1,512),dtype='float32')
        self.assertFalse(effect(silence,rate).any())
        tone=(.08*np.sin(2*np.pi*1000*np.arange(512)/rate)).astype('float32')[None,:]
        self.assertGreater(abs(effect(tone,rate)).max(),.001)
        for _ in range(100):out=effect(silence,rate)
        self.assertLess(float(abs(out).max()),1e-8)
        self.assertFalse(effect.open)

    def test_legacy_radio_variation_inherits_channel(self):
        import tempfile,json
        from unittest.mock import patch
        from pathlib import Path
        import voices
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'voices.json'
            legacy=dict(pitch=0,distortion=0,reverb=0,bitcrush=16,base_voice='Walkie-Talkie')
            path.write_text(json.dumps({'Legacy':legacy,'Bypassed':dict(legacy,comms_mode=0)}))
            with patch.object(voices,'CUSTOM_PRESETS_FILE',str(path)):
                presets=voices.load_user_presets()
                self.assertEqual(presets['Legacy']['params']['comms_mode'],2)
                self.assertEqual(presets['Bypassed']['params']['comms_mode'],0)

    def test_communications_parameters_round_trip(self):
        from voices import builtin_editor_params,EXTRA_DEFAULTS
        params=builtin_editor_params('Walkie-Talkie')
        self.assertEqual(params['comms_mode'],2)
        params['comms_static']=.25
        board=create_custom_voice(params['pitch'],params['reverb'],params['distortion'],params['bitcrush'],
              base_voice=params['base_voice'],**{key:params[key] for key in EXTRA_DEFAULTS})
        effects=[effect for effect in board.effects if isinstance(effect,CommunicationChannel)]
        self.assertEqual(len(effects),1)
        self.assertEqual(effects[0].static,.25)
        with self.assertRaises(ValueError):create_custom_voice(comms_mode=1.5)


if __name__=='__main__':unittest.main()
