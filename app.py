"""Voice Studio desktop interface. Run with python app.py."""
import math
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from engine import AudioEngine
from voices import VOICE_PRESETS, create_custom_voice, load_user_presets, save_user_preset, delete_user_preset, EXTRA_DEFAULTS, EXTRA_LIMITS


class VoiceModApp:
    def __init__(self, root):
        self.root = root
        root.title('Voice Studio')
        root.geometry('1180x840')
        root.minsize(980, 740)
        self.c = dict(bg='#111418', panel='#191E24', raised='#222A33', border='#35414E',
                      text='#F0F4F8', muted='#AAB6C4', accent='#79E0C0', ink='#10251F',
                      selected='#233D37', danger='#FFACAC')
        root.configure(bg=self.c['bg'])
        root.option_add('*Font', ('Segoe UI', 10))
        self.engine = AudioEngine(sample_rate=44100, blocksize=512)
        self.selected_preset_name = 'Clean (Normal)'
        self._slider_job = None
        self._syncing = True
        self._meter_job = None
        self.preset_buttons = {}
        self._audio_settings_path = Path(__file__).with_name('audio_settings.json')
        try:
            self._saved_audio = json.loads(self._audio_settings_path.read_text(encoding='utf-8'))
            if not isinstance(self._saved_audio, dict):
                self._saved_audio = {}
        except (OSError, ValueError):
            self._saved_audio = {}
        self.category = tk.StringVar(value='All voices')
        self.search = tk.StringVar()
        self._styles()
        self._header()
        self._audio_panel()
        self._workspace()
        self.root.update()
        self._syncing = False
        self._refresh_devices()
        self.search.trace_add('write', lambda *_: self._render_presets_grid())
        root.bind('<Control-f>', lambda _: self.search_entry.focus_set())
        root.protocol('WM_DELETE_WINDOW', self.on_closing)
        self._update_meter()

    def _styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground=self.c['raised'], background=self.c['border'],
                        foreground=self.c['text'], arrowcolor=self.c['accent'], padding=8,
                        bordercolor=self.c['border'], lightcolor=self.c['border'], darkcolor=self.c['border'])
        style.map('TCombobox', fieldbackground=[('readonly', self.c['raised'])],
                  foreground=[('readonly', self.c['text']), ('disabled', self.c['muted'])])
        style.configure('Vertical.TScrollbar', background=self.c['border'], troughcolor=self.c['panel'],
                        borderwidth=0, arrowsize=12)
        self.root.option_add('*TCombobox*Listbox.background', self.c['raised'])
        self.root.option_add('*TCombobox*Listbox.foreground', self.c['text'])
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.c['selected'])

    def _label(self, parent, text, size=10, color='text', bold=False, **kwargs):
        return tk.Label(parent, text=text, font=('Segoe UI', size, 'bold' if bold else 'normal'),
                        bg=parent.cget('bg'), fg=self.c[color], **kwargs)

    def _button(self, parent, text, command, primary=False, **kwargs):
        return tk.Button(parent, text=text, command=command, font=('Segoe UI', 10, 'bold'),
                         bg=self.c['accent'] if primary else self.c['raised'],
                         fg=self.c['ink'] if primary else self.c['text'],
                         activebackground=self.c['accent'], activeforeground=self.c['ink'],
                         relief='flat', bd=0, padx=16, pady=10, cursor='hand2',
                         highlightthickness=1, highlightbackground=self.c['border'],
                         highlightcolor=self.c['accent'], **kwargs)

    def _header(self):
        header = tk.Frame(self.root, bg=self.c['bg'], padx=28, pady=20)
        header.pack(fill='x')
        brand = tk.Canvas(header, width=36, height=38, bg=self.c['bg'], highlightthickness=0)
        brand.pack(side='left', padx=(0, 12))
        for x, height in ((6, 12), (14, 26), (22, 34), (30, 18)):
            brand.create_line(x, 19-height/2, x, 19+height/2, fill=self.c['accent'], width=4, capstyle='round')
        self._label(header, 'Voice Studio', 22, bold=True).pack(side='left')
        self._label(header, 'Make it sound like you imagined.', 10, 'muted').pack(side='left', padx=24)
        self.live_badge = self._label(header, 'STOPPED', 9, 'muted', bold=True, padx=12, pady=7)
        self.live_badge.configure(bg=self.c['raised'])
        self.live_badge.pack(side='right')
        self.setup_btn = self._button(header, 'Audio setup', self._toggle_audio_setup)
        self.setup_btn.pack(side='right', padx=12)

    def _audio_panel(self):
        border = tk.Frame(self.root, bg=self.c['border'])
        border.pack(side='bottom', fill='x', padx=24, pady=(0, 20))
        panel = tk.Frame(border, bg=self.c['panel'], padx=20, pady=16)
        panel.pack(fill='both', padx=1, pady=1)
        devices = tk.Frame(panel, bg=self.c['panel'])
        self.devices_panel = devices  # Collapsed outside one-time setup.
        devices.columnconfigure(0, weight=1)
        devices.columnconfigure(1, weight=1)
        devices.columnconfigure(2, weight=1)
        for col, text, attr in ((0, 'MICROPHONE', 'in_combo'), (1, 'APP OUTPUT (OPTIONAL)', 'out_combo'),
                                (2, 'HEADPHONES / MONITOR', 'monitor_combo')):
            field = tk.Frame(devices, bg=self.c['panel'])
            field.grid(row=0, column=col, sticky='ew', padx=(0, 16))
            self._label(field, text, 9, 'muted', True).pack(anchor='w', pady=(0, 6))
            combo = ttk.Combobox(field, state='readonly', width=16)
            combo.pack(fill='x')
            setattr(self, attr, combo)
        self.refresh_btn = self._button(devices, 'Refresh', self._refresh_devices)
        self.refresh_btn.grid(row=0, column=3, sticky='s')
        controls = tk.Frame(panel, bg=self.c['panel'])
        self.audio_controls = controls
        controls.pack(fill='x', pady=(16, 0))
        self.toggle_btn = self._button(controls, 'Start voice changer', self._toggle_stream, True, width=19)
        self.toggle_btn.pack(side='left', padx=(0, 16))
        self.hear_var, self.mute_var = tk.BooleanVar(value=False), tk.BooleanVar(value=False)
        for text, var, command in (('Hear myself', self.hear_var, self._on_hear_myself_change),
                                   ('Mute microphone', self.mute_var, self._on_mute_change)):
            tk.Checkbutton(controls, text=text, variable=var, command=command, bg=self.c['panel'],
                           fg=self.c['text'], selectcolor=self.c['raised'], activebackground=self.c['panel'],
                           activeforeground=self.c['accent'], highlightcolor=self.c['accent'],
                           padx=6, pady=8).pack(side='left')
        self._label(controls, 'Volume', 9, 'muted').pack(side='left', padx=(16, 6))
        self.vol_scale = self._scale(controls, 0, 2, .05, self._on_vol_change, length=100)
        self.vol_scale.set(1)
        self.vol_scale.pack(side='left')
        meter = tk.Frame(controls, bg=self.c['panel'])
        meter.pack(side='right', fill='x', expand=True, padx=(24, 0))
        self.meter_label = self._label(meter, 'MIC LEVEL  /  -- dB', 8, 'muted')
        self.meter_label.pack(anchor='w')
        self.meter_canvas = tk.Canvas(meter, height=8, bg=self.c['raised'], highlightthickness=0, width=100)
        self.meter_canvas.pack(fill='x', pady=(6, 0))
        self.route_label = self._label(panel, '', 9, 'muted', anchor='w')
        self.route_label.pack(fill='x', pady=(10, 0))
        self.status_lbl = self._label(panel, 'Ready. Choose a voice, then start.', 9, 'muted', anchor='w')
        self.status_lbl.pack(fill='x', pady=(12, 0))

    def _workspace(self):
        body = tk.Frame(self.root, bg=self.c['bg'])
        body.pack(fill='both', expand=True, padx=24, pady=(0, 16))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, minsize=300)
        body.rowconfigure(0, weight=1)
        library = tk.Frame(body, bg=self.c['bg'])
        library.grid(row=0, column=0, sticky='nsew', padx=(0, 24))
        heading = tk.Frame(library, bg=self.c['bg'])
        heading.pack(fill='x', pady=(0, 12))
        self._label(heading, 'Voice library', 17, bold=True).pack(side='left')
        self.count_label = self._label(heading, '', 9, 'muted')
        self.count_label.pack(side='right')
        filters = tk.Frame(library, bg=self.c['bg'])
        filters.pack(fill='x', pady=(0, 12))
        self.search_entry = tk.Entry(filters, textvariable=self.search, bg=self.c['raised'], fg=self.c['text'],
                                     insertbackground=self.c['accent'], relief='flat', highlightthickness=1,
                                     highlightbackground=self.c['border'], highlightcolor=self.c['accent'])
        self._label(filters, 'Search', 9, 'muted').pack(side='left', padx=(0, 8))
        self.search_entry.pack(side='left', fill='x', expand=True, ipady=9)
        self.category_combo = ttk.Combobox(filters, textvariable=self.category, state='readonly', width=13,
                                          values=['All voices', 'Natural', 'Basic', 'Characters', 'Sci-Fi', 'Filters', 'Atmosphere', 'Custom'])
        self.category_combo.pack(side='left', padx=(12, 0))
        self.category_combo.bind('<<ComboboxSelected>>', lambda _: self._render_presets_grid())
        scroll = tk.Frame(library, bg=self.c['bg'])
        scroll.pack(fill='both', expand=True)
        self.library_canvas = tk.Canvas(scroll, bg=self.c['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll, orient='vertical', command=self.library_canvas.yview)
        self.library_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.library_canvas.pack(side='left', fill='both', expand=True)
        self.presets_grid_frame = tk.Frame(self.library_canvas, bg=self.c['bg'])
        self._grid_window = self.library_canvas.create_window(0, 0, window=self.presets_grid_frame, anchor='nw')
        self.presets_grid_frame.bind('<Configure>', lambda _: self.library_canvas.configure(scrollregion=self.library_canvas.bbox('all')))
        self.library_canvas.bind('<Configure>', lambda e: self.library_canvas.itemconfigure(self._grid_window, width=e.width))
        self.root.bind('<MouseWheel>', self._scroll_library)
        self._editor(body)
        self._render_presets_grid()

    def _scroll_library(self, event):
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        while widget:
            if widget in (self.library_canvas, self.editor_canvas):
                widget.yview_scroll(-int(event.delta / 120), 'units')
                return 'break'
            widget = getattr(widget, 'master', None)

    def _editor(self, body):
        host = tk.Frame(body, bg=self.c['panel'])
        host.grid(row=0, column=1, sticky='nsew')
        editor_actions = tk.Frame(host, bg=self.c['panel'], padx=20, pady=12)
        editor_actions.pack(side='bottom', fill='x')
        self.editor_canvas = tk.Canvas(host, bg=self.c['panel'], width=300, highlightthickness=0)
        bar = ttk.Scrollbar(host, orient='vertical', command=self.editor_canvas.yview)
        bar.pack(side='right', fill='y')
        self.editor_canvas.configure(yscrollcommand=bar.set)
        self.editor_canvas.pack(side='left', fill='both', expand=True)
        editor = tk.Frame(self.editor_canvas, bg=self.c['panel'], padx=20, pady=20)
        window = self.editor_canvas.create_window(0, 0, window=editor, anchor='nw')
        editor.bind('<Configure>', lambda _: self.editor_canvas.configure(scrollregion=self.editor_canvas.bbox('all')))
        self.editor_canvas.bind('<Configure>', lambda e: self.editor_canvas.itemconfigure(window, width=e.width))
        self._label(editor, 'NOW SELECTED', 9, 'accent', True).pack(anchor='w')
        self.active_name = self._label(editor, self.selected_preset_name, 18, bold=True, wraplength=255, justify='left')
        self.active_name.pack(anchor='w', pady=(8, 6))
        self.active_description = self._label(editor, VOICE_PRESETS[self.selected_preset_name]['description'], 10,
                                               'muted', wraplength=250, justify='left')
        self.active_description.pack(anchor='w')
        tk.Frame(editor, bg=self.c['border'], height=1).pack(fill='x', pady=20)
        self._label(editor, 'Create a voice', 14, bold=True).pack(anchor='w')
        self._label(editor, 'Move a control to switch to a custom voice.', 9, 'muted',
                    wraplength=250, justify='left').pack(anchor='w', pady=(4, 14))
        for attr, label, low, high, step, initial, value in (
            ('pitch', 'Pitch', -12, 12, .5, 0, '0.0 st'), ('dist', 'Distortion', 0, 25, 1, 0, '0 dB'),
            ('reverb', 'Space', 0, 1, .05, 0, '0%'), ('bit', 'Bit depth', 4, 16, 1, 16, '16 bits')):
            row = tk.Frame(editor, bg=self.c['panel'])
            row.pack(fill='x')
            self._label(row, label, 10).pack(side='left')
            readout = self._label(row, value, 9, 'accent', True)
            readout.pack(side='right')
            setattr(self, attr + '_val_lbl', readout)
            scale = self._scale(editor, low, high, step, self._on_custom_slider_change)
            scale.set(initial)
            scale.pack(fill='x', pady=(2, 12))
            setattr(self, attr + '_scale', scale)
        self.extra_scales = {}
        self.extra_readouts = {}
        groups = [
            ('Vocal character', [('formant', 'Formant shift', .5, 'st'), ('formant_mix', 'Formant blend', .05, '%')]),
            ('Tone EQ', [('warmth', 'Warmth', .5, 'dB'), ('presence', 'Presence', .5, 'dB'),
                         ('brightness', 'Brightness', .5, 'dB'), ('tone_mix', 'Tone blend', .05, '%')]),
            ('Layers and texture', [('doubler_mix', 'Doubler blend', .05, '%'),
                                    ('ring_hz', 'Ring frequency', 5, 'Hz'), ('ring_mix', 'Ring blend', .05, '%')]),
        ]
        self.extra_units = {}
        for title, settings in groups:
            tk.Frame(editor, bg=self.c['border'], height=1).pack(fill='x', pady=(8, 16))
            self._label(editor, title, 12, bold=True).pack(anchor='w', pady=(0, 12))
            for key, label, step, unit in settings:
                row = tk.Frame(editor, bg=self.c['panel'])
                row.pack(fill='x')
                self._label(row, label, 10).pack(side='left')
                self.extra_units[key] = unit
                value = EXTRA_DEFAULTS[key]
                readout = self._label(row, self._format_extra(value, unit), 9, 'accent', True)
                readout.pack(side='right')
                self.extra_readouts[key] = readout
                low, high = EXTRA_LIMITS[key]
                scale = self._scale(editor, low, high, step, self._on_custom_slider_change)
                scale.set(value)
                scale.pack(fill='x', pady=(2, 12))
                self.extra_scales[key] = scale
        self._label(editor, 'Formant changes resonance, not pitch. Blend 0% bypasses an effect.',
                    9, 'muted', wraplength=245, justify='left').pack(anchor='w', pady=(4, 12))
        self._button(editor_actions, 'Save custom voice', self._save_preset_prompt, True).pack(fill='x', pady=(4, 8))
        self._button(editor_actions, 'Reset controls', self._reset_controls).pack(fill='x')

    def _scale(self, parent, low, high, step, command, **kwargs):
        return tk.Scale(parent, from_=low, to=high, resolution=step, orient='horizontal', showvalue=False,
                        command=command, bg=parent.cget('bg'), fg=self.c['text'], troughcolor=self.c['border'],
                        activebackground=self.c['accent'], highlightthickness=0, sliderrelief='raised',
                        bd=2, sliderlength=18, width=10, **kwargs)

    def _render_presets_grid(self):
        for widget in self.presets_grid_frame.winfo_children():
            widget.destroy()
        self.preset_buttons.clear()
        self.all_presets = dict(VOICE_PRESETS)
        self.user_presets = load_user_presets()
        self.all_presets.update(self.user_presets)
        query = self.search.get().strip().lower()
        found = [(n, p) for n, p in self.all_presets.items() if
                 (self.category.get() == 'All voices' or p['category'] == self.category.get()) and
                 query in (n + ' ' + p['description']).lower()]
        self.count_label.configure(text=f'{len(found)} voices')
        for index, (name, preset) in enumerate(found):
            selected = name == self.selected_preset_name
            card = tk.Frame(self.presets_grid_frame, bg=self.c['border'], padx=1, pady=1)
            card.grid(row=index//3, column=index%3, sticky='nsew', padx=(0, 8), pady=(0, 8))
            text = f"{name}\n{'Selected' if selected else preset['category']}"
            button = self._button(card, text, lambda n=name, p=preset: self._activate_preset(n, p),
                                  anchor='w', justify='left', wraplength=155, height=2)
            button.configure(bg=self.c['selected'] if selected else self.c['panel'],
                             fg=self.c['accent'] if selected else self.c['text'], font=('Segoe UI', 10),
                             highlightthickness=1, padx=10, pady=8)
            button.pack(fill='both', expand=True)
            self.preset_buttons[name] = button
            if name in self.user_presets:
                delete = self._button(card, 'Delete', lambda n=name: self._delete_user_preset(n))
                delete.configure(pady=3, font=('Segoe UI', 9))
                delete.pack(fill='x')
        for col in (0, 1, 2):
            self.presets_grid_frame.columnconfigure(col, weight=1, uniform='voices')
        if not found:
            self._label(self.presets_grid_frame, 'No voices found. Try another search or category.', 11, 'muted',
                        wraplength=400).grid(row=0, column=0, columnspan=2, pady=40)
        self.library_canvas.yview_moveto(0)

    def _activate_preset(self, name, preset):
        if self._slider_job:
            self.root.after_cancel(self._slider_job)
            self._slider_job = None
        try:
            self.engine.set_voice(preset['builder']())
        except Exception as exc:
            messagebox.showerror('Cannot activate voice', str(exc), parent=self.root)
            return
        self.selected_preset_name = name
        self.active_name.configure(text=name)
        self.active_description.configure(text=preset['description'])
        if 'params' in preset:
            self._syncing = True
            for attr, key in (('pitch', 'pitch'), ('dist', 'distortion'), ('reverb', 'reverb'), ('bit', 'bitcrush')):
                getattr(self, attr+'_scale').set(preset['params'][key])
            for key, scale in self.extra_scales.items():
                scale.set(preset['params'].get(key, EXTRA_DEFAULTS[key]))
            self.root.update()
            self._syncing = False
            self._readouts()
        self._render_presets_grid()
        self._status(f'Voice selected: {name}')

    @staticmethod
    def _format_extra(value, unit):
        if unit == '%':
            return f'{value*100:.0f}%'
        return f'{value:+.1f} {unit}' if unit in ('st', 'dB') else f'{value:.0f} {unit}'

    def _extra_values(self):
        return {key: scale.get() for key, scale in self.extra_scales.items()}

    def _readouts(self):
        self.pitch_val_lbl.configure(text=f'{self.pitch_scale.get():+.1f} st')
        self.dist_val_lbl.configure(text=f'{self.dist_scale.get():.0f} dB')
        self.reverb_val_lbl.configure(text=f'{self.reverb_scale.get()*100:.0f}%')
        self.bit_val_lbl.configure(text=f'{self.bit_scale.get():.0f} bits')
        for key, value in self._extra_values().items():
            self.extra_readouts[key].configure(text=self._format_extra(value, self.extra_units[key]))

    def _on_custom_slider_change(self, _=None):
        if self._syncing:
            return
        self._readouts()
        if self._slider_job:
            self.root.after_cancel(self._slider_job)
        self._slider_job = self.root.after(160, self._apply_custom_sliders)

    def _apply_custom_sliders(self):
        self._slider_job = None
        try:
            board = create_custom_voice(self.pitch_scale.get(), self.reverb_scale.get(),
                                        self.dist_scale.get(), self.bit_scale.get(), **self._extra_values())
            self.engine.set_voice(board)
            self.selected_preset_name = 'Custom voice'
            self.active_name.configure(text='Custom voice')
            self.active_description.configure(text='Your own mix. Save it to keep it in the library.')
            self._render_presets_grid()
            self._status('Custom voice active. Save it when you like the sound.')
        except Exception as exc:
            self._status(f'Cannot apply controls: {exc}', True)

    def _reset_controls(self):
        self._syncing = True
        for attr, value in (('pitch', 0), ('dist', 0), ('reverb', 0), ('bit', 16)):
            getattr(self, attr+'_scale').set(value)
        for key, scale in self.extra_scales.items():
            scale.set(EXTRA_DEFAULTS[key])
        self.root.update()
        self._syncing = False
        self._readouts()
        self._on_custom_slider_change()

    def _save_preset_prompt(self):
        name = simpledialog.askstring('Save custom voice', 'Voice name', parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self.user_presets and not messagebox.askyesno('Replace voice', f'Replace "{name}"?', parent=self.root):
            return
        try:
            save_user_preset(name, self.pitch_scale.get(), self.dist_scale.get(), self.reverb_scale.get(), self.bit_scale.get(), **self._extra_values())
            self.category.set('All voices')
            self.search.set('')
            self._activate_preset(name, load_user_presets()[name])
            self._status(f'Saved voice: {name}')
        except (ValueError, OSError) as exc:
            messagebox.showerror('Cannot save voice', str(exc), parent=self.root)

    def _delete_user_preset(self, name):
        if messagebox.askyesno('Delete saved voice', f'Delete "{name}"?', parent=self.root):
            try:
                delete_user_preset(name)
                if self.selected_preset_name == name:
                    self._activate_preset('Clean (Normal)', VOICE_PRESETS['Clean (Normal)'])
                self._render_presets_grid()
            except (OSError, ValueError) as exc:
                messagebox.showerror('Cannot delete voice', str(exc), parent=self.root)

    def _toggle_audio_setup(self):
        if self.devices_panel.winfo_manager():
            self._save_audio_settings()
            self.devices_panel.pack_forget()
            self.setup_btn.configure(text='Audio setup')
        else:
            self.devices_panel.pack(fill='x', before=self.audio_controls)
            self.setup_btn.configure(text='Done')

    def _save_audio_settings(self):
        data = {key: combo.get().split('] ', 1)[-1] for key, combo in
                (('mic', self.in_combo), ('output', self.out_combo), ('monitor', self.monitor_combo))}
        try:
            temporary = self._audio_settings_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
            os.replace(temporary, self._audio_settings_path)
            self._saved_audio = data
        except OSError as exc:
            self._status(f'Could not remember audio setup: {exc}', True)

    def _refresh_devices(self):
        try:
            inputs, outputs = self.engine.get_devices()
            for key, combo, devices in (('output', self.out_combo, outputs), ('mic', self.in_combo, inputs),
                                         ('monitor', self.monitor_combo, outputs)):
                previous = combo.get().split('] ', 1)[-1] or self._saved_audio.get(key)
                names = [d['name'] for d in devices]
                combo['values'] = names + (['Headset preview only'] if key == 'output' else [])
                restored = next((i for i,n in enumerate(names) if n.split('] ',1)[-1] == previous), None)
                if previous == 'Headset preview only' and key == 'output':
                    combo.set(previous)
                    continue
                if restored is not None:
                    combo.current(restored)
                    continue
                if key == 'output':
                    candidates = [i for i,n in enumerate(names) if any(term in n.lower()
                                  for term in ('cable input', 'virtual cable', 'voicemod virtual', 'dummy output (voicemod)'))]
                    # This installation's Voicemod loopback was verified with MME.
                    preferred = next((i for i in candidates if 'dummy output (voicemod)' in names[i].lower()
                                      and '(MME)' in names[i]), None)
                else:
                    candidates = [i for i,n in enumerate(names) if not any(term in n.lower()
                                  for term in ('voicemod', 'cable', 'sound mapper', 'primary sound'))]
                    if key == 'monitor':
                        candidates = [i for i in candidates if any(t in names[i].lower() for t in ('headphone','speaker'))]
                    preferred = None
                    headset = [i for i in candidates if 'stealth 500' in names[i].lower()]
                    if headset:
                        candidates = headset
                    if key == 'mic' and 0 <= self.out_combo.current() < len(outputs):
                        api = outputs[self.out_combo.current()]['raw']['hostapi']
                        preferred = next((i for i in candidates if devices[i]['raw']['hostapi'] == api), None)
                if preferred is None:
                    preferred = next((i for i in candidates if 'WASAPI' in names[i]), candidates[0] if candidates else None)
                if preferred is None:
                    combo.set('Headset preview only' if key == 'output' else '')
                else:
                    combo.current(preferred)
            self.device_inputs, self.device_outputs = inputs, outputs
            routed = 0 <= self.out_combo.current() < len(outputs)
            self.route_label.configure(text=('Virtual microphone ready. Hear myself controls only your headphones.' if routed else
                                             'Headset preview only. A virtual microphone is needed to send effects to other apps.'))
            self._status('Ready. Choose a voice and press Start.', not(inputs and outputs))
        except Exception as exc:
            self.device_inputs, self.device_outputs = [], []
            self._status(f'Audio devices unavailable: {exc}', True)

    def _on_hear_myself_change(self):
        enabled = self.hear_var.get()
        index = self.monitor_combo.current()
        if enabled and index < 0:
            self.hear_var.set(False)
            self._status('Select headphones before enabling Hear myself.', True)
            return
        try:
            device = self.device_outputs[index]['index'] if index >= 0 else None
            self.engine.set_monitor(enabled, device)
            self._status('Headphone monitoring on.' if enabled else 'Hear myself off. Your headset preview is silent.' if self.engine.preview_only else 'Headphone monitoring off. App output continues.')
        except Exception as exc:
            self.hear_var.set(False)
            self.engine.set_monitor(False)
            self._status(f'Cannot enable monitoring: {exc}', True)

    def _on_mute_change(self):
        self.engine.mute_mic = self.mute_var.get()

    def _on_vol_change(self, value):
        self.engine.output_gain = float(value)

    def _status(self, text, error=False):
        self.status_lbl.configure(text=text, fg=self.c['danger'] if error else self.c['muted'])

    def _toggle_stream(self):
        if self.engine.is_running:
            self.engine.stop()
        else:
            if self.in_combo.current() < 0 or self.monitor_combo.current() < 0:
                self._status('Choose your headset microphone and headphones.', True)
                return
            try:
                output_index = self.out_combo.current()
                preview = not (0 <= output_index < len(self.device_outputs))
                monitor_device = self.device_outputs[self.monitor_combo.current()]['index']
                output_device = monitor_device if preview else self.device_outputs[output_index]['index']
                # Full-duplex streams require compatible host APIs.
                mic = self.device_inputs[self.in_combo.current()]
                if not preview:
                    target_api = self.device_outputs[output_index]['raw']['hostapi']
                    match = next((i for i,d in enumerate(self.device_inputs) if d['raw']['name'] == mic['raw']['name']
                                  and d['raw']['hostapi'] == target_api), None)
                    if match is not None:
                        self.in_combo.current(match)
                self._save_audio_settings()
                self.engine.start(self.device_inputs[self.in_combo.current()]['index'],
                                  output_device, monitor_device, preview_only=preview)
            except Exception as exc:
                self._status(f'Could not start audio: {exc}', True)
                return
        running = self.engine.is_running
        self.toggle_btn.configure(text='Stop voice changer' if running else 'Start voice changer',
                                  bg=self.c['raised'] if running else self.c['accent'],
                                  fg=self.c['danger'] if running else self.c['ink'])
        self.live_badge.configure(text='LIVE' if running else 'STOPPED',
                                  fg=self.c['accent'] if running else self.c['muted'])
        for combo in (self.in_combo, self.out_combo, self.monitor_combo):
            combo.configure(state='disabled' if running else 'readonly')
        self.refresh_btn.configure(state='disabled' if running else 'normal')
        self.hear_var.set(self.engine.monitor_enabled)
        self._status((f'Headset preview / {self.selected_preset_name}. Other apps still use their normal microphone.'
                      if self.engine.preview_only else f'Live / {self.selected_preset_name}') if running else 'Stopped. Ready when you are.')
        if running and self.engine.monitor_error:
            self._status(f'App output is live; headphone monitoring unavailable: {self.engine.monitor_error}', True)

    def _update_meter(self):
        canvas = self.meter_canvas
        canvas.delete('all')
        level = self.engine.current_rms_level
        db = 20 * math.log10(max(level, 1e-6))
        value = max(0, min(1, (db + 60) / 60))
        canvas.create_rectangle(0, 0, canvas.winfo_width()*value, 8,
                                fill=self.c['danger'] if db > -3 else self.c['accent'], width=0)
        self.meter_label.configure(text=f'MIC LEVEL  /  {db:.0f} dB' if level > 1e-6 else 'MIC LEVEL  /  -- dB')
        if self.engine.last_error:
            self._status(f'Audio error: {self.engine.last_error}', True)
        self._meter_job = self.root.after(50, self._update_meter)

    def on_closing(self):
        self._save_audio_settings()
        for job in (self._slider_job, self._meter_job):
            if job:
                self.root.after_cancel(job)
        self.engine.stop()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = VoiceModApp(root)
    root.mainloop()
