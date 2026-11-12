"""Windows system-wide hotkey registration, with events marshalled to Tk."""
import ctypes as ct
from ctypes import wintypes as wt
import queue
import threading
import sys

HOTKEYS = {'Ctrl+Alt+V': (3, 0x56), 'Ctrl+Alt+F8': (3, 0x77),
           'F8': (0, 0x77), 'F9': (0, 0x78), 'F10': (0, 0x79)}


class GlobalHotkey:
    def __init__(self, name):
        if name not in HOTKEYS:
            raise ValueError('Choose a supported shortcut.')
        if sys.platform != 'win32':
            raise RuntimeError('Global shortcuts require Windows.')
        self.name = name
        self.events = queue.Queue()
        self.ready = threading.Event()
        self.error = None
        self.thread_id = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        if not self.ready.wait(2):
            self.close()
            raise RuntimeError('Shortcut registration timed out.')
        if self.error:
            raise RuntimeError(self.error)

    def _run(self):
        user = ct.WinDLL('user32', use_last_error=True)
        kernel = ct.WinDLL('kernel32', use_last_error=True)
        user.RegisterHotKey.argtypes = [wt.HWND, ct.c_int, wt.UINT, wt.UINT]
        user.RegisterHotKey.restype = wt.BOOL
        user.GetMessageW.argtypes = [ct.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
        user.GetMessageW.restype = ct.c_int
        kernel.GetCurrentThreadId.restype = wt.DWORD
        self.thread_id = kernel.GetCurrentThreadId()
        message = wt.MSG()
        user.PeekMessageW(ct.byref(message), None, 0, 0, 0)
        modifiers, key = HOTKEYS[self.name]
        registered = False
        try:
            if not user.RegisterHotKey(None, 1, modifiers | 0x4000, key):
                self.error = f'{self.name} is unavailable or used by another application. Choose another shortcut.'
                return
            registered = True
            self.ready.set()
            while user.GetMessageW(ct.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312 and message.wParam == 1:
                    self.events.put('toggle')
        except Exception as exc:
            self.error = str(exc)
        finally:
            if registered:
                user.UnregisterHotKey(None, 1)
            self.ready.set()

    def close(self):
        if self.thread_id and self.thread.is_alive():
            ct.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
            self.thread.join(timeout=.5)
