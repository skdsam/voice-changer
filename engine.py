"""
engine.py - Real-Time Audio Streaming Engine using sounddevice & pedalboard
-------------------------------------------------------------------------
Captures audio from the input device (Mic), applies the active DSP chain,
and streams it directly to the output device (Headphones / Virtual Cable).
"""

import threading
from collections import deque
import numpy as np
import sounddevice as sd
from pedalboard.io import AudioFile
from pedalboard import Resample, Limiter
from voices import create_clean_voice
from monitor_resampler import MonitorResampler
from route_isolation import VoicemodSessionGuard


class AudioEngine:
    def __init__(self, sample_rate=44100, blocksize=1024):
        self.sample_rate = sample_rate
        self.blocksize = blocksize  # 1024 samples (~23ms) provides smooth pitch shifting

        self.stream = None
        self._route_guard = None
        self.is_running = False

        # Audio processing
        self._lock = threading.Lock()
        self.current_board = create_clean_voice()
        self.monitor_enabled = False  # Independent headphone monitoring.
        self.monitor_stream = None
        self.monitor_device = None
        self.preview_only = False
        self.monitor_error = None
        self._monitor_resampler = None
        self.monitor_sample_rate = sample_rate
        self._monitor_lock = threading.Lock()
        self._monitor_queue = deque()
        self._monitor_frames = 0
        self.monitor_status_count = 0
        self.mute_mic = False        # Mute microphone input
        self.output_gain = 1.0       # Master volume

        # Soundboard playback buffer
        self._sfx_lock = threading.Lock()
        self.sfx_buffer = None  # shape: (channels, frames)
        self.sfx_pos = 0

        # Audio metering for UI
        self.current_rms_level = 0.0

        # Devices
        self.last_error = None
        self.callback_status_count = 0
        self._limiter = Limiter(threshold_db=-1.0, release_ms=80.0)
        self.input_device = None
        self.output_device = None

    @staticmethod
    def get_devices():
        """Returns sorted lists of input and output audio devices."""
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()

        inputs = []
        outputs = []

        for idx, dev in enumerate(devices):
            hostapi_name = hostapis[dev['hostapi']]['name']
            label = f"[{idx}] {dev['name']} ({hostapi_name})"

            if dev['max_input_channels'] > 0:
                inputs.append({"index": idx, "name": label, "channels": dev['max_input_channels'], "raw": dev})
            if dev['max_output_channels'] > 0:
                outputs.append({"index": idx, "name": label, "channels": dev['max_output_channels'], "raw": dev})

        return inputs, outputs

    def set_voice(self, pedalboard_instance):
        """Thread-safely swap the active audio DSP chain."""
        # Allocate native state outside the real-time callback.
        channels = getattr(self, '_input_channels', 1)
        if hasattr(pedalboard_instance, 'prepare'):
            pedalboard_instance.prepare(self.sample_rate, channels)
        with self._lock:
            self.current_board = pedalboard_instance

    def set_monitor(self, enabled: bool, device_id=None):
        """Toggle headphone monitoring without affecting the main application output."""
        if device_id is not None:
            if self.monitor_stream is not None and device_id != self.monitor_device:
                raise ValueError('Stop audio before changing the headphone device.')
            self.monitor_device = device_id
        with self._monitor_lock:
            self.monitor_enabled = False
            self._monitor_queue.clear()
            self._monitor_frames = 0
            if self._monitor_resampler is not None:
                self._monitor_resampler.reset()
        if enabled:
            if self.is_running and self.monitor_stream is None:
                self._start_monitor()
            self.monitor_enabled = True
        self.monitor_error = None

    def _start_monitor(self):
        if self.preview_only:
            return  # Main stream is the checkbox-controlled headset preview.
        if self.monitor_device is None:
            raise ValueError('Choose a headphone device for Hear myself.')
        info = sd.query_devices(self.monitor_device)
        main = sd.query_devices(self.output_device, kind='output')
        if self.monitor_device == self.output_device or info['name'] == main['name']:
            self.preview_only = True
            return
        channels = min(2, info['max_output_channels'])
        rates = list(dict.fromkeys((self.sample_rate, int(info.get('default_samplerate', 48000)), 48000, 44100)))
        failures = []
        for rate in rates:
            stream = None
            try:
                sd.check_output_settings(device=self.monitor_device, channels=channels,
                                         dtype='float32', samplerate=rate)
                with self._monitor_lock:
                    self.monitor_sample_rate = rate
                    self._monitor_resampler = MonitorResampler(self.sample_rate, rate) if rate != self.sample_rate else None
                    self._monitor_queue.clear()
                    self._monitor_frames = 0
                stream = sd.OutputStream(device=self.monitor_device, channels=channels, samplerate=rate,
                    blocksize=self.blocksize, dtype='float32', latency='low', callback=self._monitor_callback)
                stream.start()
                self.monitor_stream = stream
                return
            except Exception as exc:
                failures.append(f'{rate} Hz: {exc}')
                if stream is not None:
                    stream.close()
        raise RuntimeError('Could not open headphones. ' + '; '.join(failures))

    def _publish_monitor(self, audio):
        # Bounded queue: independent device clocks must never grow monitoring delay.
        with self._monitor_lock:
            if not self.monitor_enabled:
                return
            block = self._monitor_resampler.process(audio) if self._monitor_resampler is not None else audio.copy()
            if not len(block):
                return
            self._monitor_queue.append(block)
            self._monitor_frames += len(block)
            maximum = max(self.blocksize * 3, int(self.monitor_sample_rate * .1))
            while self._monitor_frames > maximum and self._monitor_queue:
                self._monitor_frames -= len(self._monitor_queue.popleft())

    def _monitor_callback(self, outdata, frames, time_info, status):
        outdata.fill(0)
        if status:
            self.monitor_status_count += 1
        with self._monitor_lock:
            if not self.monitor_enabled:
                self._monitor_queue.clear()
                self._monitor_frames = 0
                return
            position = 0
            while position < frames and self._monitor_queue:
                block = self._monitor_queue[0]
                count = min(frames-position, len(block))
                if block.shape[1] == outdata.shape[1]:
                    outdata[position:position+count] = block[:count]
                elif outdata.shape[1] == 1:
                    outdata[position:position+count, 0] = block[:count].mean(axis=1)
                else:
                    outdata[position:position+count] = block[:count, :1]
                position += count
                self._monitor_frames -= count
                if count == len(block):
                    self._monitor_queue.popleft()
                else:
                    self._monitor_queue[0] = block[count:]

    def play_sound(self, file_path: str):
        """Loads and plays an audio file (MP3/WAV) mixed into the live stream."""
        try:
            with AudioFile(file_path) as f:
                sr = f.samplerate
                audio = f.read(f.frames)

            if audio.shape[0] == 1:
                audio = np.repeat(audio, 2, axis=0)

            if sr != self.sample_rate:
                resampler = Resample(target_sample_rate=self.sample_rate)
                audio = resampler(audio, sample_rate=sr)

            with self._sfx_lock:
                self.sfx_buffer = audio.astype(np.float32)
                self.sfx_pos = 0
            return True
        except Exception as e:
            print(f"Error loading sound file {file_path}: {e}")
            return False

    def stop_sound(self):
        """Stops any currently playing soundboard sound."""
        with self._sfx_lock:
            self.sfx_buffer = None
            self.sfx_pos = 0

    def _audio_callback(self, indata, outdata, frames, time_info, status):
        """High-priority audio callback called by PortAudio for each block."""
        if status:
            self.callback_status_count += 1

        # Calculate RMS level for UI level meter
        rms = np.sqrt(np.mean(indata ** 2)) if indata.size > 0 else 0.0
        self.current_rms_level = float(rms)

        try:
            if self.mute_mic:
                processed = np.zeros((indata.shape[1], frames), dtype=np.float32)
            else:
                audio_in = indata.T
                with self._lock:
                    board = self.current_board

                if board is not None and len(board) > 0:
                    processed = board(audio_in, sample_rate=self.sample_rate, reset=False)
                else:
                    processed = audio_in

            # Adapt channels if input and output channel counts differ
            out_channels = outdata.shape[1]
            in_channels = processed.shape[0]

            if out_channels == in_channels:
                final_audio = processed
            elif out_channels == 2 and in_channels == 1:
                final_audio = np.repeat(processed, 2, axis=0)
            elif out_channels == 1 and in_channels > 1:
                final_audio = np.mean(processed, axis=0, keepdims=True)
            else:
                final_audio = np.zeros((out_channels, frames), dtype=np.float32)

            # Ensure final_audio matches exact frame length
            curr_frames = final_audio.shape[1]
            if curr_frames < frames:
                pad = np.zeros((final_audio.shape[0], frames - curr_frames), dtype=np.float32)
                final_audio = np.hstack([final_audio, pad])
            elif curr_frames > frames:
                final_audio = final_audio[:, :frames]

            # Mix in soundboard audio if currently playing
            with self._sfx_lock:
                if self.sfx_buffer is not None:
                    remaining = self.sfx_buffer.shape[1] - self.sfx_pos
                    chunk_len = min(frames, remaining)
                    sfx_chunk = self.sfx_buffer[:, self.sfx_pos:self.sfx_pos + chunk_len]

                    if final_audio.shape[0] == sfx_chunk.shape[0]:
                        final_audio[:, :chunk_len] += sfx_chunk
                    elif final_audio.shape[0] == 2 and sfx_chunk.shape[0] == 1:
                        final_audio[:, :chunk_len] += np.repeat(sfx_chunk, 2, axis=0)
                    elif final_audio.shape[0] == 1 and sfx_chunk.shape[0] == 2:
                        final_audio[:, :chunk_len] += np.mean(sfx_chunk, axis=0, keepdims=True)

                    self.sfx_pos += chunk_len
                    if self.sfx_pos >= self.sfx_buffer.shape[1]:
                        self.sfx_buffer = None
                        self.sfx_pos = 0

            # Apply master gain
            if self.output_gain != 1.0:
                final_audio = final_audio * self.output_gain

            final_audio = self._limiter(final_audio, self.sample_rate, reset=False)
            np.nan_to_num(final_audio, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
            # Final safety ceiling after the limiter.
            np.clip(final_audio, -1.0, 1.0, out=final_audio)
            outdata[:] = final_audio.T
            if self.preview_only:
                if not self.monitor_enabled:
                    outdata.fill(0)
            elif self.monitor_enabled:
                self._publish_monitor(outdata)

        except Exception as e:
            self.last_error = str(e)
            outdata.fill(0)

    def start(self, input_device_id=None, output_device_id=None, monitor_device_id=None, preview_only=False):
        """Starts real-time full-duplex audio stream."""
        if self.is_running:
            self.stop()

        self.input_device = input_device_id
        self.output_device = output_device_id
        self.preview_only = preview_only
        if monitor_device_id is not None:
            self.monitor_device = monitor_device_id

        in_info = sd.query_devices(self.input_device) if self.input_device is not None else sd.query_devices(kind='input')
        out_info = sd.query_devices(self.output_device) if self.output_device is not None else sd.query_devices(kind='output')

        if self.monitor_device is not None:
            monitor_info = sd.query_devices(self.monitor_device)
            if self.monitor_device == self.output_device or monitor_info['name'] == out_info['name']:
                self.preview_only = True
        in_channels = min(2, in_info['max_input_channels'])
        self._input_channels = in_channels
        out_channels = min(2, out_info['max_output_channels'])

        sample_rate = int(in_info.get('default_samplerate', self.sample_rate))
        self.sample_rate = sample_rate

        self.stream = sd.Stream(
            device=(self.input_device, self.output_device),
            channels=(in_channels, out_channels),
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype='float32',
            latency='low',
            callback=self._audio_callback
        )
        try:
            if not self.preview_only and 'voicemod' in out_info['name'].lower():
                names=[out_info['name']]
                if self.monitor_device is not None:
                    names.append(sd.query_devices(self.monitor_device)['name'])
                self._route_guard=VoicemodSessionGuard(names)
                self._route_guard.start()
            self.current_board.prepare(self.sample_rate, in_channels)
            self._limiter.reset()
            self.last_error = None
            self.callback_status_count = 0
            self.stream.start()
            self.is_running = True
            if self.monitor_enabled:
                try:
                    self._start_monitor()
                    self.monitor_error = None
                except Exception as exc:
                    self.monitor_enabled = False
                    self.monitor_error = str(exc)
        except Exception:
            self.stream.close()
            self.stream = None
            if self._route_guard is not None:
                self._route_guard.stop()
                self._route_guard=None
            raise

    def stop(self):
        """Stops the audio stream."""
        if self.monitor_stream is not None:
            try:
                self.monitor_stream.stop()
            except Exception:
                pass
            try:
                self.monitor_stream.close()
            except Exception:
                pass
            self.monitor_stream = None
        with self._monitor_lock:
            self._monitor_queue.clear()
            self._monitor_frames = 0
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            finally:
                self.stream = None
        if self._route_guard is not None:
            self._route_guard.stop()
            self._route_guard=None
        self.is_running = False
        self.current_rms_level = 0.0
