"""Temporarily isolate Voice Studio from Voicemod's own audio feeds."""
import threading


def mute_voicemod_sessions(sessions, originals):
    """Mute only Voicemod-owned sessions; remember their original mute states."""
    for session in sessions:
        process=session.Process
        if process is None or process.name().lower()!='voicemod.exe':
            continue
        key=session.InstanceIdentifier
        volume=session.SimpleAudioVolume
        muted=bool(volume.GetMute())
        if key not in originals:
            originals[key]=(volume,muted)
        if not muted:
            volume.SetMute(True,None)


def restore_sessions(originals):
    for volume,muted in originals.values():
        try:
            volume.SetMute(muted,None)
        except Exception:
            pass  # An exited process no longer has a live session to restore.


class VoicemodSessionGuard:
    def __init__(self, device_names):
        self.device_names=set(device_names)
        self.ready=threading.Event()
        self.stopping=threading.Event()
        self.error=None
        self.muted_count=0
        self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self._run,daemon=True)
        self.thread.start()
        if not self.ready.wait(3):
            self.stop()
            raise RuntimeError('Audio-route isolation timed out.')
        if self.error:
            self.stop()
            raise RuntimeError(self.error)

    def _run(self):
        originals={}
        initialized=False
        try:
            import comtypes
            from pycaw.utils import AudioUtilities,AudioSession
            from pycaw.api.audiopolicy import IAudioSessionControl2
            comtypes.CoInitialize()
            initialized=True
            devices=[d for d in AudioUtilities.GetAllDevices() if d.FriendlyName in self.device_names
                     and AudioUtilities.GetEndpointDataFlow(d.id)=='eRender']
            if not devices:
                raise RuntimeError('The virtual output could not be isolated from Voicemod.')
            while not self.stopping.is_set():
                for device in devices:
                    enumerator=device.AudioSessionManager.GetSessionEnumerator()
                    sessions=[]
                    for index in range(enumerator.GetCount()):
                        try:
                            sessions.append(AudioSession(enumerator.GetSession(index).QueryInterface(IAudioSessionControl2)))
                        except Exception:
                            continue
                    mute_voicemod_sessions(sessions,originals)
                self.muted_count=len(originals)
                self.ready.set()
                self.stopping.wait(.75)
        except ImportError:
            self.error='Install requirements.txt to enable Voicemod audio isolation (pycaw is required).'
        except Exception as exc:
            self.error=f'Voicemod audio isolation failed: {exc}'
        finally:
            restore_sessions(originals)
            if initialized:
                comtypes.CoUninitialize()
            self.ready.set()

    def stop(self):
        self.stopping.set()
        if self.thread is not None:
            self.thread.join(timeout=3)
