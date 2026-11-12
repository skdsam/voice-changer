"""Tests for editable built-in variations and saved base chains."""
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
import numpy as np
import voices


class VoiceEditingTests(unittest.TestCase):
    def build(self, params):
        return voices.create_custom_voice(params['pitch'],params['reverb'],params['distortion'],params['bitcrush'],
                    base_voice=params.get('base_voice'),**{k:params[k] for k in voices.EXTRA_DEFAULTS})

    def test_recalling_every_builtin_preserves_its_sound(self):
        rng=np.random.default_rng(17)
        blocks=[rng.normal(0,.04,(1,512)).astype('float32') for _ in range(75)]
        for name,preset in voices.VOICE_PRESETS.items():
            original=preset['builder']()
            recalled=self.build(voices.builtin_editor_params(name))
            for block in blocks:
                np.testing.assert_allclose(original(block,48000,reset=False),recalled(block,48000,reset=False),atol=1e-6,err_msg=name)

    def test_primary_pitch_changes_without_discarding_other_filters(self):
        params=voices.builtin_editor_params('Cyborg Robot')
        params['pitch']=-4
        varied=self.build(params)
        from pedalboard import PitchShift,Chorus,Bitcrush
        pitch=[x for x in varied.effects if isinstance(x,PitchShift)]
        self.assertEqual(len(pitch),1)
        self.assertEqual(pitch[0].semitones,-4)
        self.assertTrue(any(isinstance(x,Chorus) for x in varied.effects))
        self.assertTrue(any(isinstance(x,Bitcrush) for x in varied.effects))

    def test_saved_variation_retains_base(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(voices,'CUSTOM_PRESETS_FILE',str(Path(folder)/'voices.json')):
                params=voices.builtin_editor_params('Astronaut')
                voices.save_user_preset('My astronaut',params['pitch'],params['distortion'],params['reverb'],params['bitcrush'],
                            base_voice=params['base_voice'],**{k:params[k] for k in voices.EXTRA_DEFAULTS})
                preset=voices.load_user_presets()['My astronaut']
                self.assertEqual(preset['params']['base_voice'],'Astronaut')
                self.assertEqual(len(preset['builder']().effects),len(voices.VOICE_PRESETS['Astronaut']['builder']().effects))
                with self.assertRaises(ValueError):
                    voices.save_user_preset('Bad base',0,0,0,base_voice='Missing voice')


if __name__=='__main__':unittest.main()
