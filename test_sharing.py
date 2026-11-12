"""Tests for sharing voice presets (.vmvoice/.json) and soundboard clip import/export."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from pedalboard.io import AudioFile
import soundboard
import voices
from engine import AudioEngine


class SharingTests(unittest.TestCase):
    def test_builtin_and_pack_preset_export_import_round_trip(self):
        orig_file = voices.CUSTOM_PRESETS_FILE
        try:
            with tempfile.TemporaryDirectory() as folder:
                folder_p = Path(folder)
                voices.CUSTOM_PRESETS_FILE = str(folder_p / "custom_presets.json")

                # Export a built-in voice to portable .vmvoice bundle
                bundle_path = folder_p / "cyber.vmvoice"
                voices.export_voice_preset("Cyber Shifter", str(bundle_path))
                data = json.loads(bundle_path.read_text(encoding="utf-8"))
                self.assertEqual(data["format"], voices.PRESET_BUNDLE_FORMAT)
                self.assertIn("Cyber Shifter", data["voices"])

                # Importing a built-in name safely appends (Imported), then (2) on duplicate
                imp1 = voices.import_voice_presets(str(bundle_path))
                self.assertEqual(imp1, ["Cyber Shifter (Imported)"])
                imp2 = voices.import_voice_presets(str(bundle_path))
                self.assertEqual(imp2, ["Cyber Shifter (Imported) (2)"])

                # Export and re-import a custom voice pack
                voices.save_user_preset("Custom Titan", -2.0, 4.0, 0.2, 16, formant=-1.5)
                pack_path = folder_p / "pack.json"
                exported_names = voices.export_voice_pack(str(pack_path))
                self.assertIn("Custom Titan", exported_names)

                voices.CUSTOM_PRESETS_FILE = str(folder_p / "fresh_custom.json")
                imp_pack = voices.import_voice_presets(str(pack_path))
                self.assertIn("Custom Titan", imp_pack)
                loaded = voices.load_user_presets()["Custom Titan"]
                self.assertEqual(loaded["params"]["pitch"], -2.0)
                self.assertEqual(loaded["params"]["formant"], -1.5)

                # Graceful fallback when imported bundle cites an unknown base_voice
                unknown_base = folder_p / "future.vmvoice"
                unknown_base.write_text(
                    json.dumps({"format": voices.PRESET_BUNDLE_FORMAT, "version": 1,
                                "voices": {"FutureVoice": {"pitch": 1.5, "distortion": 0, "reverb": 0.1, "bitcrush": 16, "base_voice": "NonexistentBase"}}}),
                    encoding="utf-8",
                )
                self.assertEqual(voices.import_voice_presets(str(unknown_base)), ["FutureVoice"])
                self.assertIsNone(voices.load_user_presets()["FutureVoice"]["params"]["base_voice"])
        finally:
            voices.CUSTOM_PRESETS_FILE = orig_file

    def test_soundboard_clip_import_export_and_processed_render(self):
        with tempfile.TemporaryDirectory() as folder:
            folder_p = Path(folder)
            sounds_dir = folder_p / "sounds"
            src_wav = folder_p / "source_clip.wav"
            rate = 44100
            t = np.arange(rate // 2, dtype=np.float32) / rate
            tone = (0.18 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)[None, :]
            with AudioFile(str(src_wav), "w", samplerate=rate, num_channels=1) as w:
                w.write(tone)

            # Empty directory starts cleanly
            self.assertEqual(soundboard.list_sound_clips(str(sounds_dir)), [])

            # Import validates and copies into managed directory; duplicates rename cleanly
            c1 = soundboard.import_sound_clip(str(src_wav), directory=str(sounds_dir))
            c2 = soundboard.import_sound_clip(str(src_wav), directory=str(sounds_dir))
            self.assertEqual(c1["name"], "source_clip")
            self.assertEqual(c2["name"], "source_clip (2)")
            self.assertEqual(len(soundboard.list_sound_clips(str(sounds_dir))), 2)

            # Share/export clip copies cleanly
            shared_wav = folder_p / "shared" / "out_clip.wav"
            soundboard.export_sound_clip(c1["path"], str(shared_wav))
            self.assertTrue(shared_wav.exists())
            meta = soundboard.inspect_audio_file(str(shared_wav))
            self.assertAlmostEqual(meta["duration_sec"], 0.5, delta=0.02)

            # Render processed WAV through Cyber Shifter preset
            processed_wav = folder_p / "processed.wav"
            soundboard.export_processed_audio(
                str(src_wav), voices.VOICE_PRESETS["Cyber Shifter"]["builder"], str(processed_wav), sample_rate=44100
            )
            with AudioFile(str(processed_wav)) as r:
                out_audio = r.read(r.frames)
            self.assertGreater(float(np.sqrt(np.mean(out_audio ** 2))), 0.01)

            # Reject corrupt or unsupported clips and prevent deleting outside sounds folder
            bad_file = folder_p / "bad.txt"
            bad_file.write_text("not audio", encoding="utf-8")
            with self.assertRaises(ValueError):
                soundboard.import_sound_clip(str(bad_file), directory=str(sounds_dir))
            with self.assertRaises(ValueError):
                soundboard.delete_sound_clip(str(shared_wav), directory=str(sounds_dir))

            soundboard.delete_sound_clip(c2["path"], directory=str(sounds_dir))
            self.assertEqual(len(soundboard.list_sound_clips(str(sounds_dir))), 1)

    def test_engine_sound_playing_property(self):
        engine = AudioEngine(sample_rate=44100, blocksize=512)
        self.assertFalse(engine.is_sound_playing)
        with tempfile.TemporaryDirectory() as folder:
            wav = Path(folder) / "ping.wav"
            tone = (0.1 * np.sin(2 * np.pi * 440 * np.arange(4410) / 44100)).astype(np.float32)[None, :]
            with AudioFile(str(wav), "w", samplerate=44100, num_channels=1) as w:
                w.write(tone)
            self.assertTrue(engine.play_sound(str(wav)))
            self.assertTrue(engine.is_sound_playing)
            engine.stop_sound()
            self.assertFalse(engine.is_sound_playing)


if __name__ == "__main__":
    unittest.main()

