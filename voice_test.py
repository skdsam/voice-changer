"""Tk local recording and same-sample voice comparison window."""
import queue
import threading
import wave
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog
import numpy as np
import sounddevice as sd
from comparison import render_comparison
from monitor_resampler import MonitorResampler


class VoiceTestWindow:
    def __init__(self,app,builders,selected,mic,headphones):
        self.app,self.builders,self.mic,self.headphones=app,builders,mic,headphones
        self.window=tk.Toplevel(app.root)
        self.window.title('Voice Studio / Record and compare')
        self.window.geometry('680x520')
        self.window.minsize(640,500)
        self.window.configure(bg=app.c['panel'])
        self.window.transient(app.root)
        self.window.grab_set()
        self.closed=False
        self.events=queue.Queue()
        self.cancel=threading.Event()
        self.raw=None
        self.original=self.processed=None
        self.busy=False
        self.recording=False
        self.poll_job=None
        self.play_stream=None
        self.route_guard=None
        content=tk.Frame(self.window,bg=app.c['panel'],padx=24,pady=20)
        content.pack(fill='both',expand=True)
        app._label(content,'Record once. Compare every voice.',17,bold=True).pack(anchor='w')
        app._label(content,'Live output is paused. Samples stay in memory until you export them.',10,'muted',
                   wraplength=570,justify='left').pack(anchor='w',pady=(8,16))
        self.choice=tk.StringVar(value=selected)
        app._label(content,'Voice to compare',10).pack(anchor='w')
        self.combo=ttk.Combobox(content,textvariable=self.choice,values=list(builders),state='readonly')
        self.combo.pack(fill='x',pady=(6,16))
        self.combo.bind('<<ComboboxSelected>>',lambda _:self.render())
        row=tk.Frame(content,bg=app.c['panel']);row.pack(fill='x')
        self.record=app._button(row,'Record 8 seconds',self.capture,True);self.record.pack(side='left')
        self.stop_button=app._button(row,'Stop recording',self.cancel.set);self.stop_button.pack(side='left',padx=8)
        self.stop_button.configure(state='disabled')
        play=tk.Frame(content,bg=app.c['panel']);play.pack(fill='x',pady=16)
        self.buttons=[]
        for label,callback in (('Play original',lambda:self.play(False)),('Play processed',lambda:self.play(True)),
                               ('Export pair',self.export)):
            button=app._button(play,label,callback);button.pack(side='left',padx=(0,8))
            button.configure(state='disabled');self.buttons.append(button)
        self.status=app._label(content,'Say the same short phrase naturally, quietly and loudly. Include a sustained vowel.',10,
                              'muted',wraplength=570,justify='left')
        self.status.pack(anchor='w',pady=(4,12))
        app._label(content,'Playback uses your selected headphones. Matching is by active-speech RMS, with peak protection.',9,
                   'muted',wraplength=570,justify='left').pack(anchor='w')
        output_index=app.out_combo.current()
        if 0<=output_index<len(app.device_outputs) and 'voicemod' in app.device_outputs[output_index]['raw']['name'].lower():
            try:
                from route_isolation import VoicemodSessionGuard
                self.route_guard=VoicemodSessionGuard([app.device_outputs[output_index]['raw']['name'],sd.query_devices(headphones)['name']])
                self.route_guard.start()
            except Exception as exc:
                self.status.configure(text='Test input is local, but other-app monitoring could not be isolated: '+str(exc))
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.poll()

    def emit(self,event):
        events=self.events
        if not self.closed and events is not None:
            events.put(event)

    def set_busy(self,value,recording=False):
        self.busy,self.recording=value,recording
        self.record.configure(state='disabled' if value else 'normal')
        self.combo.configure(state='disabled' if value else 'readonly')
        self.stop_button.configure(state='normal' if recording else 'disabled')
        for button in self.buttons:
            button.configure(state='normal' if self.processed is not None and not value else 'disabled')

    def capture(self):
        self.stop_playback()
        self.cancel.clear()
        self.raw=None
        self.set_busy(True,True)
        self.original=self.processed=None
        self.status.configure(text='Recording from your selected microphone (maximum 8 seconds)…')
        threading.Thread(target=self._capture,daemon=True).start()

    def _capture(self):
        try:
            info=sd.query_devices(self.mic)
            rate=int(info['default_samplerate'])
            chunks=[];remaining=rate*8
            with sd.InputStream(device=self.mic,samplerate=rate,channels=1,blocksize=512,dtype='float32') as stream:
                while remaining>0 and not self.cancel.is_set():
                    block,overflow=stream.read(min(512,remaining))
                    if overflow:
                        raise RuntimeError('Microphone input overflowed. Please record again.')
                    chunks.append(block[:,0].copy());remaining-=len(block)
            if not chunks:
                raise ValueError('No audio captured.')
            self.emit(('captured',(np.concatenate(chunks),rate)))
        except Exception as exc:self.emit(('error',str(exc)))

    def render(self):
        if self.raw is None or self.busy:return
        self.stop_playback()
        self.original=self.processed=None
        self.set_busy(True)
        self.status.configure(text='Processing the same recording through '+self.choice.get()+'…')
        builder=self.builders[self.choice.get()]
        raw,rate=self.raw.copy(),self.rate
        def work():
            try:self.emit(('rendered',render_comparison(raw,rate,builder)))
            except Exception as exc:self.emit(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        if self.closed:return
        try:
            while True:
                kind,data=self.events.get_nowait()
                if kind=='captured':
                    self.raw,self.rate=data
                    self.set_busy(False)
                    self.render()
                elif kind=='rendered':
                    self.original,self.processed,note=data
                    self.set_busy(False)
                    peak=float(np.max(abs(self.raw)))
                    self.status.configure(text=note+(' Input was clipped; lower your microphone level and record again.' if peak>=.999 else ''))
                else:
                    self.set_busy(False)
                    self.status.configure(text='Could not complete test: '+str(data))
        except queue.Empty:pass
        self.poll_job=self.window.after(60,self.poll)

    def stop_playback(self):
        if self.play_stream is not None:
            try:
                self.play_stream.abort()
            except Exception:
                pass
            try:
                self.play_stream.close()
            except Exception:
                pass
            self.play_stream=None

    def play(self,processed):
        self.stop_playback()
        try:
            info=sd.query_devices(self.headphones)
            rate=int(info['default_samplerate'])
            audio=self.processed if processed else self.original
            if rate!=self.rate:
                audio=MonitorResampler(self.rate,rate).process(audio[:,None])[:,0]
            position=0
            channels=min(2,info['max_output_channels'])
            def callback(outdata,frames,time,status):
                nonlocal position
                outdata.fill(0)
                count=min(frames,len(audio)-position)
                outdata[:count]=audio[position:position+count,None]
                position+=count
                if position>=len(audio):raise sd.CallbackStop
            self.play_stream=sd.OutputStream(device=self.headphones,samplerate=rate,channels=channels,
                                            dtype='float32',callback=callback)
            self.play_stream.start()
            self.status.configure(text='Playing '+('processed' if processed else 'original')+' / '+self.choice.get())
        except Exception as exc:self.status.configure(text='Playback failed: '+str(exc))

    def export(self):
        directory=filedialog.askdirectory(title='Export the original and processed test',parent=self.window)
        if not directory:return
        try:
            for name,audio in (('original.wav',self.original),('processed.wav',self.processed)):
                path=Path(directory)/name
                if path.exists():
                    from tkinter import messagebox
                    if not messagebox.askyesno('Replace test files','Replace existing original.wav / processed.wav?',parent=self.window):return
                    break
            for name,audio in (('original.wav',self.original),('processed.wav',self.processed)):
                with wave.open(str(Path(directory)/name),'wb') as target:
                    target.setnchannels(1);target.setsampwidth(2);target.setframerate(self.rate)
                    target.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())
            self.status.configure(text='Exported original.wav and processed.wav to your selected folder.')
        except Exception as exc:self.status.configure(text='Export failed: '+str(exc))

    def close(self):
        self.closed=True
        self.cancel.set()
        self.events=None
        self.raw=self.original=self.processed=None
        self.stop_playback()
        if self.route_guard is not None:self.route_guard.stop()
        if self.poll_job:self.window.after_cancel(self.poll_job)
        self.window.destroy()
