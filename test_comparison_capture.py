import unittest,threading,queue
from unittest.mock import patch
import numpy as np
from voice_test import VoiceTestWindow


class TestCaptureTests(unittest.TestCase):
    def make_window(self):
        obj=object.__new__(VoiceTestWindow)
        obj.mic=1;obj.events=queue.Queue();obj.cancel=threading.Event();obj.closed=False
        return obj

    def test_local_capture_is_bounded_and_does_not_write_files(self):
        window=self.make_window()
        class Stream:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,frames):return np.full((frames,1),.02,dtype='float32'),False
        with patch('voice_test.sd.query_devices',return_value={'default_samplerate':44100}), \
             patch('voice_test.sd.InputStream',return_value=Stream()):
            window._capture()
        kind,(audio,rate)=window.events.get_nowait()
        self.assertEqual(kind,'captured');self.assertEqual(rate,44100)
        self.assertEqual(len(audio),rate*8)

    def test_overflow_is_reported(self):
        window=self.make_window()
        class Stream:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,frames):return np.zeros((frames,1),dtype='float32'),True
        with patch('voice_test.sd.query_devices',return_value={'default_samplerate':48000}), \
             patch('voice_test.sd.InputStream',return_value=Stream()):window._capture()
        kind,message=window.events.get_nowait()
        self.assertEqual(kind,'error');self.assertIn('overflow',message)

    def test_closed_window_discards_worker_results(self):
        window=self.make_window();window.closed=True
        window.emit(('captured',np.ones(100)))
        self.assertTrue(window.events.empty())


if __name__=='__main__':unittest.main()
