import unittest
from unittest.mock import MagicMock,patch
import numpy as np
from route_isolation import mute_voicemod_sessions,restore_sessions
from engine import AudioEngine


def session(name,identity,muted=False):
    obj=MagicMock()
    obj.Process.name.return_value=name
    obj.InstanceIdentifier=identity
    obj.SimpleAudioVolume.GetMute.return_value=muted
    return obj


class RouteIsolationTests(unittest.TestCase):
    def test_only_voicemod_sessions_are_muted_and_original_states_restored(self):
        vm=session('Voicemod.exe','vm')
        already_muted=session('Voicemod.exe','muted',True)
        studio=session('python.exe','studio')
        recorder=session('VoiceRecorder.exe','recorder')
        originals={}
        mute_voicemod_sessions([vm,already_muted,studio,recorder],originals)
        vm.SimpleAudioVolume.SetMute.assert_called_once_with(True,None)
        already_muted.SimpleAudioVolume.SetMute.assert_not_called()
        studio.SimpleAudioVolume.SetMute.assert_not_called()
        recorder.SimpleAudioVolume.SetMute.assert_not_called()
        restore_sessions(originals)
        vm.SimpleAudioVolume.SetMute.assert_called_with(False,None)
        already_muted.SimpleAudioVolume.SetMute.assert_called_with(True,None)

    def test_rechecking_does_not_overwrite_original_mute_state(self):
        vm=session('Voicemod.exe','vm')
        originals={}
        mute_voicemod_sessions([vm],originals)
        vm.SimpleAudioVolume.GetMute.return_value=True
        mute_voicemod_sessions([vm],originals)
        self.assertFalse(originals['vm'][1])
        restore_sessions(originals)
        vm.SimpleAudioVolume.SetMute.assert_called_with(False,None)

    def test_no_raw_microphone_is_added_to_processed_output(self):
        class SilentEffect:
            def __len__(self):return 1
            def __call__(self,audio,**kwargs):return np.zeros_like(audio)
        engine=AudioEngine(sample_rate=48000)
        engine.current_board=SilentEffect()
        engine.set_monitor(True,3)
        source=np.full((512,1),.1,dtype='float32')
        out=np.ones((512,2),dtype='float32')
        engine._audio_callback(source,out,512,None,None)
        self.assertIsNone(engine.last_error)
        self.assertFalse(out.any())
        monitor=np.ones_like(out)
        engine._monitor_callback(monitor,512,None,None)
        self.assertFalse(monitor.any())

    def test_guard_is_restored_if_stream_start_fails(self):
        engine=AudioEngine()
        info=dict(name='Dummy Output (Voicemod)',max_input_channels=1,max_output_channels=2,default_samplerate=48000)
        stream=MagicMock();stream.start.side_effect=RuntimeError('Cannot start')
        guard=MagicMock()
        with patch('engine.sd.query_devices',return_value=info),patch('engine.sd.Stream',return_value=stream), \
             patch('engine.VoicemodSessionGuard',return_value=guard):
            with self.assertRaises(RuntimeError):engine.start(2,7)
        guard.start.assert_called_once()
        guard.stop.assert_called_once()
        stream.close.assert_called_once()
        self.assertIsNone(engine._route_guard)
        self.assertFalse(engine.is_running)


if __name__=='__main__':unittest.main()
