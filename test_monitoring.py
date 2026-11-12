import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from engine import AudioEngine


class MonitorTests(unittest.TestCase):
    def test_monitor_off_keeps_main_output_live(self):
        engine = AudioEngine(sample_rate=48000)
        output = np.zeros((512,2),dtype='float32')
        engine._audio_callback(np.full((512,1),.05,dtype='float32'),output,512,None,None)
        self.assertGreater(abs(output).max(),0)
        monitor = np.ones_like(output)
        engine._monitor_callback(monitor,512,None,None)
        self.assertEqual(abs(monitor).max(),0)

    def test_monitor_gets_same_processed_audio_and_toggle_clears(self):
        engine = AudioEngine(sample_rate=48000)
        engine.set_monitor(True,2)
        output = np.zeros((512,2),dtype='float32')
        engine._audio_callback(np.full((512,1),.05,dtype='float32'),output,512,None,None)
        monitor = np.zeros_like(output)
        engine._monitor_callback(monitor,512,None,None)
        np.testing.assert_allclose(monitor,output)
        engine._publish_monitor(output)
        engine.set_monitor(False)
        self.assertEqual(engine._monitor_frames,0)
        engine._monitor_callback(monitor,512,None,None)
        self.assertFalse(monitor.any())
        engine._audio_callback(np.full((512,1),.05,dtype='float32'),output,512,None,None)
        self.assertTrue(output.any())
        engine.set_monitor(True)
        engine._monitor_callback(monitor,512,None,None)
        self.assertFalse(monitor.any())

    def test_monitor_queue_is_bounded_and_handles_partial_blocks(self):
        engine = AudioEngine(sample_rate=48000,blocksize=512)
        engine.set_monitor(True,2)
        for _ in range(100):engine._publish_monitor(np.ones((512,1),dtype='float32')*.1)
        self.assertLessEqual(engine._monitor_frames,4800)
        output = np.zeros((333,2),dtype='float32')
        engine._monitor_callback(output,333,None,None)
        np.testing.assert_allclose(output,.1)
        engine.set_monitor(False)
        engine.set_monitor(True)
        engine._monitor_callback(output,333,None,None)
        self.assertFalse(output.any())

    def test_monitor_failure_does_not_stop_main_stream(self):
        engine=AudioEngine()
        info=dict(name='Cable',max_input_channels=1,max_output_channels=2,default_samplerate=48000)
        main=MagicMock()
        engine.set_monitor(True,3)
        with patch('engine.sd.query_devices',return_value=info), patch('engine.sd.Stream',return_value=main), \
             patch.object(engine,'_start_monitor',side_effect=RuntimeError('Unsupported headphone rate')):
            engine.start(1,2,3)
        self.assertTrue(engine.is_running)
        self.assertFalse(engine.monitor_enabled)
        self.assertIn('Unsupported',engine.monitor_error)
        main.start.assert_called_once()
        engine.stop()
        main.close.assert_called_once()

    def test_resampling_preserves_timing_pitch_and_chunk_boundaries(self):
        from monitor_resampler import MonitorResampler
        for source_rate,target_rate in ((44100,48000),(48000,44100)):
            timeline=np.arange(source_rate*2)/source_rate
            source=np.sin(2*np.pi*440*timeline).astype('float32')[:,None]
            converter=MonitorResampler(source_rate,target_rate)
            output=np.concatenate([converter.process(source[i:i+512]) for i in range(0,len(source),512)])
            whole=MonitorResampler(source_rate,target_rate).process(source)
            self.assertEqual(output.shape,whole.shape)
            np.testing.assert_allclose(output,whole,atol=1e-6)
            self.assertLessEqual(abs(len(output)-target_rate*2),2)
            spectrum=abs(np.fft.rfft(output[:,0]*np.hanning(len(output))))
            peak=np.argmax(spectrum)*target_rate/len(output)
            self.assertAlmostEqual(peak,440,delta=1)

    def test_headphones_fall_back_to_native_rate(self):
        engine=AudioEngine(sample_rate=44100)
        engine.monitor_device=20
        engine.output_device=7
        stream=MagicMock()
        def query(device, **kwargs):
            return dict(name='Headphones' if device==20 else 'Virtual cable',max_output_channels=2,default_samplerate=48000)
        def check(**kwargs):
            if kwargs['samplerate']==44100:
                raise RuntimeError('Invalid sample rate')
        with patch('engine.sd.query_devices',side_effect=query), \
             patch('engine.sd.check_output_settings',side_effect=check), \
             patch('engine.sd.OutputStream',return_value=stream):
            engine._start_monitor()
        self.assertEqual(engine.sample_rate,44100)
        self.assertEqual(engine.monitor_sample_rate,48000)
        self.assertIsNotNone(engine._monitor_resampler)
        stream.start.assert_called_once()
        engine.stop()

    def test_same_headset_is_checkbox_controlled_preview(self):
        engine=AudioEngine(sample_rate=48000)
        engine.is_running=True
        engine.output_device=2
        with patch('engine.sd.query_devices',return_value={'name':'Headphones','max_output_channels':2}), \
             patch('engine.sd.OutputStream') as monitor_stream:
            engine.set_monitor(True,2)
            self.assertTrue(engine.preview_only)
            monitor_stream.assert_not_called()
        output=np.zeros((512,2),dtype='float32')
        source=np.full((512,1),.05,dtype='float32')
        engine._audio_callback(source,output,512,None,None)
        self.assertTrue(output.any())
        engine.set_monitor(False)
        engine._audio_callback(source,output,512,None,None)
        self.assertFalse(output.any())
        self.assertTrue(engine.is_running)
        engine.set_monitor(True)
        engine._audio_callback(source,output,512,None,None)
        self.assertTrue(output.any())


if __name__=='__main__':unittest.main()
