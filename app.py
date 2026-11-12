"""Voice Studio desktop interface. Run with python app.py."""
import json
import math
import os
import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sounddevice as sd
from pedalboard import Resample
from pedalboard.io import AudioFile

from engine import AudioEngine
from hotkeys import GlobalHotkey, HOTKEYS
import soundboard
from voices import (
    VOICE_PRESETS,
    EXTRA_DEFAULTS,
    EXTRA_LIMITS,
    create_custom_voice,
    load_user_presets,
    save_user_preset,
    delete_user_preset,
    builtin_editor_params,
    export_voice_preset,
    export_voice_pack,
    import_voice_presets,
)


CATEGORY_LIST = ['All voices', 'Natural', 'Basic', 'Characters', 'Sci-Fi', 'Filters', 'Atmosphere', 'Custom']


class VoiceModApp:
    def __init__(self, root):
        self.root = root
        root.title('Voice Studio')
        root.geometry('1240x860')
        root.minsize(1020, 740)
        self.c = dict(
            bg='#0D1117',
            panel='#11161E',
            card='#141A22',
            raised='#18202B',
            border='#222D3C',
            border_hi='#3A4B63',
            text='#F1F5F9',
            muted='#8D9BAE',
            subtle='#64748B',
            accent='#4AE3B5',
            ink='#08221A',
            selected='#162C27',
            info='#60A5FA',
            warn='#FBBF24',
            warn_bg='#2A2315',
            danger='#F87171',
            danger_bg='#291A1E',
        )
        root.configure(bg=self.c['bg'])
        root.option_add('*Font', ('Segoe UI', 10))
        self.engine = AudioEngine(sample_rate=44100, blocksize=512)
        self.selected_preset_name = 'Clean (Normal)'
        self._editor_base_voice = None
        self._hotkey = None
        self._voice_test = None
        self._hotkey_job = None
        self._slider_job = None
        self._syncing = True
        self._meter_job = None
        self._active_tab = 'voices'
        self._latency_cache = {}
        self.preset_buttons = {}
        self.category_pills = {}

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
        self.search.trace_add('write', lambda *_: self._render_library())
        root.bind('<Control-f>', lambda _: self.search_entry.focus_set())
        root.protocol('WM_DELETE_WINDOW', self.on_closing)
        self._update_meter()
        self._apply_hotkey(save=False)
        self._poll_hotkey()

    def _styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'TCombobox',
            fieldbackground=self.c['raised'],
            background=self.c['border'],
            foreground=self.c['text'],
            arrowcolor=self.c['accent'],
            padding=7,
            bordercolor=self.c['border'],
            lightcolor=self.c['border'],
            darkcolor=self.c['border'],
        )
        style.map(
            'TCombobox',
            fieldbackground=[('readonly', self.c['raised'])],
            foreground=[('readonly', self.c['text']), ('disabled', self.c['muted'])],
        )
        style.configure(
            'Vertical.TScrollbar',
            background=self.c['border'],
            troughcolor=self.c['panel'],
            borderwidth=0,
            arrowsize=11,
        )
        self.root.option_add('*TCombobox*Listbox.background', self.c['raised'])
        self.root.option_add('*TCombobox*Listbox.foreground', self.c['text'])
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.c['selected'])

    def _label(self, parent, text, size=10, color='text', bold=False, **kwargs):
        return tk.Label(
            parent,
            text=text,
            font=('Segoe UI', size, 'bold' if bold else 'normal'),
            bg=parent.cget('bg'),
            fg=self.c[color],
            **kwargs,
        )

    def _button(self, parent, text, command, primary=False, tone='default', **kwargs):
        if primary:
            bg, fg, border = self.c['accent'], self.c['ink'], self.c['accent']
        elif tone == 'danger':
            bg, fg, border = self.c['danger_bg'], self.c['danger'], '#3B262B'
        elif tone == 'info':
            bg, fg, border = self.c['raised'], self.c['info'], self.c['border']
        else:
            bg, fg, border = self.c['raised'], self.c['text'], self.c['border']
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=('Segoe UI', 9, 'bold' if primary else 'normal'),
            bg=bg,
            fg=fg,
            activebackground=self.c['accent'],
            activeforeground=self.c['ink'],
            relief='flat',
            bd=0,
            padx=12,
            pady=7,
            cursor='hand2',
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=self.c['accent'],
            **kwargs,
        )

    def _header(self):
        header = tk.Frame(self.root, bg=self.c['panel'], padx=22, pady=12)
        header.pack(fill='x')
        tk.Frame(self.root, bg=self.c['border'], height=1).pack(fill='x')

        left = tk.Frame(header, bg=self.c['panel'])
        left.pack(side='left')
        brand = tk.Canvas(left, width=28, height=28, bg=self.c['panel'], highlightthickness=0)
        brand.pack(side='left', padx=(0, 10))
        for x, height in ((4, 10), (10, 20), (16, 26), (22, 14)):
            brand.create_line(x, 14 - height / 2, x, 14 + height / 2, fill=self.c['accent'], width=3, capstyle='round')
        self._label(left, 'Voice Studio', 16, bold=True).pack(side='left', padx=(0, 22))

        tabs_host = tk.Frame(left, bg=self.c['bg'], padx=3, pady=3)
        tabs_host.pack(side='left')
        self.tab_voices_btn = tk.Button(
            tabs_host,
            text='Voice Changer',
            command=lambda: self._switch_tab('voices'),
            font=('Segoe UI', 9, 'bold'),
            relief='flat',
            bd=0,
            padx=12,
            pady=5,
            cursor='hand2',
        )
        self.tab_voices_btn.pack(side='left', padx=(0, 3))
        self.tab_soundboard_btn = tk.Button(
            tabs_host,
            text='Soundboard & Clips',
            command=lambda: self._switch_tab('soundboard'),
            font=('Segoe UI', 9, 'bold'),
            relief='flat',
            bd=0,
            padx=12,
            pady=5,
            cursor='hand2',
        )
        self.tab_soundboard_btn.pack(side='left')

        right = tk.Frame(header, bg=self.c['panel'])
        right.pack(side='right')
        self.live_badge = self._label(right, '● STOPPED', 9, 'muted', bold=True, padx=11, pady=6)
        self.live_badge.configure(bg=self.c['raised'])
        self.live_badge.pack(side='right', padx=(10, 0))
        self.setup_btn = self._button(right, 'Audio Setup', self._toggle_audio_setup)
        self.setup_btn.pack(side='right', padx=(8, 0))
        self._button(right, 'A/B Test', self._open_voice_test).pack(side='right', padx=(8, 0))
        self._button(right, 'Export / Share', lambda: self._open_share_dialog('export'), tone='info').pack(side='right', padx=(8, 0))
        self._button(right, 'Import', lambda: self._open_share_dialog('import')).pack(side='right')
        self._style_workspace_tabs()

    def _style_workspace_tabs(self):
        voices_active = self._active_tab == 'voices'
        self.tab_voices_btn.configure(
            bg=self.c['raised'] if voices_active else self.c['bg'],
            fg=self.c['accent'] if voices_active else self.c['muted'],
        )
        self.tab_soundboard_btn.configure(
            bg=self.c['raised'] if not voices_active else self.c['bg'],
            fg=self.c['accent'] if not voices_active else self.c['muted'],
        )

    def _switch_tab(self, tab):
        if tab not in ('voices', 'soundboard'):
            return
        self._active_tab = tab
        self._style_workspace_tabs()
        if tab == 'voices':
            self.pills_frame.pack(fill='x', pady=(8, 0))
            self.soundboard_toolbar.pack_forget()
        else:
            self.pills_frame.pack_forget()
            self.soundboard_toolbar.pack(fill='x', pady=(8, 0))
        self._render_library()

    def _audio_panel(self):
        dock_border = tk.Frame(self.root, bg=self.c['border'])
        dock_border.pack(side='bottom', fill='x')
        panel = tk.Frame(dock_border, bg=self.c['panel'], padx=20, pady=12)
        panel.pack(fill='both', pady=(1, 0))

        # Collapsible Audio Setup drawer (shown above dock on demand)
        devices = tk.Frame(panel, bg=self.c['card'], padx=14, pady=12,
                           highlightthickness=1, highlightbackground=self.c['border'])
        self.devices_panel = devices
        devices.columnconfigure(0, weight=1)
        devices.columnconfigure(1, weight=1)
        devices.columnconfigure(2, weight=1)
        for col, text, attr in (
            (0, 'MICROPHONE INPUT', 'in_combo'),
            (1, 'VIRTUAL OUTPUT (OPTIONAL)', 'out_combo'),
            (2, 'HEADPHONES / MONITOR', 'monitor_combo'),
        ):
            field = tk.Frame(devices, bg=self.c['card'])
            field.grid(row=0, column=col, sticky='ew', padx=(0, 12))
            self._label(field, text, 8, 'muted', True).pack(anchor='w', pady=(0, 4))
            combo = ttk.Combobox(field, state='readonly', width=16)
            combo.pack(fill='x')
            setattr(self, attr, combo)
        self.refresh_btn = self._button(devices, 'Refresh', self._refresh_devices)
        self.refresh_btn.grid(row=0, column=3, sticky='s')

        controls = tk.Frame(panel, bg=self.c['panel'])
        self.audio_controls = controls
        controls.pack(fill='x')

        self.toggle_btn = self._button(controls, 'Start voice changer', self._toggle_stream, primary=True, width=18)
        self.toggle_btn.configure(pady=8)
        self.toggle_btn.pack(side='left', padx=(0, 14))

        self.hear_var = tk.BooleanVar(value=False)
        self.mute_var = tk.BooleanVar(value=False)
        self.hygiene_var = tk.BooleanVar(value=bool(self._saved_audio.get('mic_hygiene', True)))
        self.engine.set_mic_hygiene(self.hygiene_var.get())

        for text, var, command in (
            ('Hear myself', self.hear_var, self._on_hear_myself_change),
            ('Clean mic', self.hygiene_var, self._on_hygiene_change),
            ('Mute mic', self.mute_var, self._on_mute_change),
        ):
            tk.Checkbutton(
                controls,
                text=text,
                variable=var,
                command=command,
                bg=self.c['raised'],
                fg=self.c['text'],
                selectcolor=self.c['selected'],
                activebackground=self.c['raised'],
                activeforeground=self.c['accent'],
                relief='flat',
                highlightthickness=1,
                highlightbackground=self.c['border'],
                padx=8,
                pady=5,
                cursor='hand2',
            ).pack(side='left', padx=(0, 6))

        shortcut_box = tk.Frame(controls, bg=self.c['panel'])
        shortcut_box.pack(side='left', padx=(12, 0))
        self._label(shortcut_box, 'Hotkey', 8, 'muted').pack(side='left', padx=(0, 6))
        saved_key = self._saved_audio.get('hotkey', 'Ctrl+Alt+V')
        self.hotkey_var = tk.StringVar(value=saved_key if saved_key in HOTKEYS or saved_key == 'Disabled' else 'Ctrl+Alt+V')
        self.hotkey_combo = ttk.Combobox(
            shortcut_box, textvariable=self.hotkey_var, state='readonly', width=12, values=[*HOTKEYS, 'Disabled']
        )
        self.hotkey_combo.pack(side='left')
        self.hotkey_combo.bind('<<ComboboxSelected>>', lambda _: self._apply_hotkey())

        # Right side: Output gain & segmented 16-LED mic meter
        right_dock = tk.Frame(controls, bg=self.c['panel'])
        right_dock.pack(side='right', fill='x', expand=True, padx=(16, 0))

        meter = tk.Frame(right_dock, bg=self.c['panel'])
        meter.pack(side='right', fill='x', expand=True, padx=(14, 0))
        meter_head = tk.Frame(meter, bg=self.c['panel'])
        meter_head.pack(fill='x')
        self._label(meter_head, 'MIC INPUT', 8, 'muted', True).pack(side='left')
        self.meter_label = self._label(meter_head, '-- dB', 8, 'accent', True)
        self.meter_label.pack(side='right')
        self.meter_canvas = tk.Canvas(meter, height=10, bg=self.c['bg'], highlightthickness=0, width=130)
        self.meter_canvas.pack(fill='x', pady=(4, 0))

        vol_box = tk.Frame(right_dock, bg=self.c['panel'])
        vol_box.pack(side='right')
        self._label(vol_box, 'Out Vol', 8, 'muted').pack(side='left', padx=(0, 6))
        self.vol_scale = self._scale(vol_box, 0, 2, .05, self._on_vol_change, length=88)
        self.vol_scale.set(1)
        self.vol_scale.pack(side='left')

        # Single compact footer line combining route, status & hotkey hint
        footer = tk.Frame(panel, bg=self.c['panel'])
        footer.pack(fill='x', pady=(8, 0))
        self.status_lbl = self._label(footer, 'Ready. Choose a voice, then start.', 9, 'muted', anchor='w')
        self.status_lbl.pack(side='left')
        self.route_label = self._label(footer, '', 8, 'subtle', anchor='e')
        self.route_label.pack(side='right')
        self.hotkey_status = self._label(footer, '', 8, 'subtle')
        self.hotkey_status.pack(side='right', padx=(0, 14))

    def _workspace(self):
        body = tk.Frame(self.root, bg=self.c['bg'])
        body.pack(fill='both', expand=True, padx=20, pady=14)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, minsize=330)
        body.rowconfigure(0, weight=1)

        library = tk.Frame(body, bg=self.c['bg'])
        library.grid(row=0, column=0, sticky='nsew', padx=(0, 18))

        # Top Search + Result Count Row
        search_bar = tk.Frame(library, bg=self.c['bg'])
        search_bar.pack(fill='x')
        search_wrap = tk.Frame(
            search_bar, bg=self.c['card'], highlightthickness=1, highlightbackground=self.c['border'], padx=10, pady=2
        )
        search_wrap.pack(side='left', fill='x', expand=True)
        self._label(search_wrap, 'Search', 9, 'muted').pack(side='left', padx=(0, 8))
        self.search_entry = tk.Entry(
            search_wrap,
            textvariable=self.search,
            bg=self.c['card'],
            fg=self.c['text'],
            insertbackground=self.c['accent'],
            relief='flat',
            bd=0,
        )
        self.search_entry.pack(side='left', fill='x', expand=True, ipady=6)
        self.count_label = self._label(search_bar, '', 9, 'muted')
        self.count_label.pack(side='right', padx=(12, 0))

        # Pill Filter Bar (Voice Changer mode)
        self.pills_frame = tk.Frame(library, bg=self.c['bg'])
        self.pills_frame.pack(fill='x', pady=(10, 0))
        for cat in CATEGORY_LIST:
            short = 'All' if cat == 'All voices' else cat
            btn = tk.Button(
                self.pills_frame,
                text=short,
                command=lambda c=cat: self._select_category(c),
                font=('Segoe UI', 9),
                relief='flat',
                bd=0,
                padx=11,
                pady=4,
                cursor='hand2',
                highlightthickness=1,
            )
            btn.pack(side='left', padx=(0, 6))
            self.category_pills[cat] = btn
        self._style_category_pills()

        # Soundboard Toolbar (hidden unless Soundboard tab active)
        self.soundboard_toolbar = tk.Frame(
            library, bg=self.c['card'], padx=12, pady=8, highlightthickness=1, highlightbackground=self.c['border']
        )
        self._label(
            self.soundboard_toolbar,
            'Trigger WAV / MP3 clips straight into your virtual microphone or preview locally.',
            9,
            'muted',
        ).pack(side='left')
        self._button(self.soundboard_toolbar, 'Stop Playing', self._stop_soundboard, tone='danger').pack(
            side='right', padx=(8, 0)
        )
        self._button(self.soundboard_toolbar, '+ Import Sound File', self._import_sound_prompt, primary=True).pack(
            side='right'
        )

        # Scrollable Card Area
        scroll = tk.Frame(library, bg=self.c['bg'])
        scroll.pack(fill='both', expand=True, pady=(12, 0))
        self.library_canvas = tk.Canvas(scroll, bg=self.c['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll, orient='vertical', command=self.library_canvas.yview)
        self.library_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.library_canvas.pack(side='left', fill='both', expand=True)
        self.presets_grid_frame = tk.Frame(self.library_canvas, bg=self.c['bg'])
        self._grid_window = self.library_canvas.create_window(0, 0, window=self.presets_grid_frame, anchor='nw')
        self.presets_grid_frame.bind(
            '<Configure>', lambda _: self.library_canvas.configure(scrollregion=self.library_canvas.bbox('all'))
        )
        self.library_canvas.bind(
            '<Configure>', lambda e: self.library_canvas.itemconfigure(self._grid_window, width=e.width)
        )
        self.root.bind('<MouseWheel>', self._scroll_library)

        self._editor(body)
        self._render_library()

    def _select_category(self, category):
        self.category.set(category)
        self._style_category_pills()
        self._render_library()

    def _style_category_pills(self):
        current = self.category.get()
        for cat, btn in self.category_pills.items():
            active = cat == current
            btn.configure(
                bg=self.c['accent'] if active else self.c['card'],
                fg=self.c['ink'] if active else self.c['muted'],
                highlightbackground=self.c['accent'] if active else self.c['border'],
                font=('Segoe UI', 9, 'bold' if active else 'normal'),
            )

    def _scroll_library(self, event):
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        while widget:
            if widget in (self.library_canvas, self.editor_canvas):
                widget.yview_scroll(-int(event.delta / 120), 'units')
                return 'break'
            widget = getattr(widget, 'master', None)

    def _editor(self, body):
        host = tk.Frame(body, bg=self.c['panel'], highlightthickness=1, highlightbackground=self.c['border'])
        host.grid(row=0, column=1, sticky='nsew')

        editor_actions = tk.Frame(host, bg=self.c['bg'], padx=16, pady=12)
        editor_actions.pack(side='bottom', fill='x')
        tk.Frame(host, bg=self.c['border'], height=1).pack(side='bottom', fill='x')

        self.editor_canvas = tk.Canvas(host, bg=self.c['panel'], width=326, highlightthickness=0)
        bar = ttk.Scrollbar(host, orient='vertical', command=self.editor_canvas.yview)
        bar.pack(side='right', fill='y')
        self.editor_canvas.configure(yscrollcommand=bar.set)
        self.editor_canvas.pack(side='left', fill='both', expand=True)

        editor = tk.Frame(self.editor_canvas, bg=self.c['panel'], padx=16, pady=16)
        window = self.editor_canvas.create_window(0, 0, window=editor, anchor='nw')
        editor.bind('<Configure>', lambda _: self.editor_canvas.configure(scrollregion=self.editor_canvas.bbox('all')))
        self.editor_canvas.bind('<Configure>', lambda e: self.editor_canvas.itemconfigure(window, width=e.width))

        # Active Voice Summary Card
        summary = tk.Frame(
            editor, bg=self.c['card'], padx=14, pady=12, highlightthickness=1, highlightbackground=self.c['border']
        )
        summary.pack(fill='x')
        top_meta = tk.Frame(summary, bg=self.c['card'])
        top_meta.pack(fill='x')
        self._label(top_meta, 'ACTIVE VOICE', 8, 'accent', True).pack(side='left')
        self.latency_label = self._label(top_meta, '', 8, 'accent', True)
        self.latency_label.pack(side='right')
        self._update_latency_label()

        self.active_name = self._label(summary, self.selected_preset_name, 14, bold=True, wraplength=270, justify='left')
        self.active_name.pack(anchor='w', pady=(6, 4))
        self.active_description = self._label(
            summary, VOICE_PRESETS[self.selected_preset_name]['description'], 9, 'muted', wraplength=270, justify='left'
        )
        self.active_description.pack(anchor='w')

        card_btns = tk.Frame(summary, bg=self.c['card'])
        card_btns.pack(fill='x', pady=(10, 0))
        card_btns.columnconfigure(0, weight=1)
        card_btns.columnconfigure(1, weight=1)
        self._button(card_btns, 'Edit in Rack', self._recall_voice).grid(row=0, column=0, sticky='ew', padx=(0, 6))
        self._button(card_btns, 'Share Voice', self._export_active_voice, tone='info').grid(row=0, column=1, sticky='ew')

        tk.Frame(editor, bg=self.c['border'], height=1).pack(fill='x', pady=14)
        self._label(editor, 'Voice Shaper', 12, bold=True).pack(anchor='w')
        self._label(editor, 'Move a slider to sculpt a custom variation.', 9, 'muted', wraplength=280, justify='left').pack(
            anchor='w', pady=(2, 10)
        )

        primary_card = tk.Frame(
            editor, bg=self.c['card'], padx=12, pady=10, highlightthickness=1, highlightbackground=self.c['border']
        )
        primary_card.pack(fill='x', pady=(0, 10))
        for attr, label, low, high, step, initial, value in (
            ('pitch', 'Pitch Shift', -12, 12, .5, 0, '0.0 st'),
            ('dist', 'Harmonic Grit', 0, 25, 1, 0, '0 dB'),
            ('reverb', 'Space & Reverb', 0, 1, .05, 0, '0%'),
            ('bit', 'Bit Depth', 4, 16, 1, 16, '16 bits'),
        ):
            row = tk.Frame(primary_card, bg=self.c['card'])
            row.pack(fill='x')
            self._label(row, label, 9).pack(side='left')
            readout = self._label(row, value, 9, 'accent', True)
            readout.pack(side='right')
            setattr(self, attr + '_val_lbl', readout)
            scale = self._scale(primary_card, low, high, step, self._on_custom_slider_change)
            scale.set(initial)
            scale.pack(fill='x', pady=(2, 8))
            setattr(self, attr + '_scale', scale)

        self.extra_scales = {}
        self.extra_readouts = {}
        self.effect_enabled = {}
        self.effect_sections = {}
        groups = [
            ('Vocal character', [('formant', 'Formant shift', .5, 'st'), ('formant_mix', 'Formant blend', .05, '%')]),
            (
                'Tone EQ',
                [
                    ('warmth', 'Warmth', .5, 'dB'),
                    ('presence', 'Presence', .5, 'dB'),
                    ('brightness', 'Brightness', .5, 'dB'),
                    ('tone_mix', 'Tone blend', .05, '%'),
                ],
            ),
            (
                'Layers and texture',
                [('doubler_mix', 'Doubler blend', .05, '%'), ('ring_hz', 'Ring frequency', 5, 'Hz'), ('ring_mix', 'Ring blend', .05, '%')],
            ),
            (
                'Harmony',
                [
                    ('harmony_pitch1', 'Layer 1 pitch', .5, 'st'),
                    ('harmony_level1', 'Layer 1 level', .05, '%'),
                    ('harmony_pitch2', 'Layer 2 pitch', .5, 'st'),
                    ('harmony_level2', 'Layer 2 level', .05, '%'),
                    ('harmony_mix', 'Harmony blend', .05, '%'),
                ],
            ),
            ('Resonator', [('resonator_hz', 'Resonance', 10, 'Hz'), ('resonator_decay', 'Decay', .05, '%'), ('resonator_mix', 'Resonator blend', .05, '%')]),
            ('Delay', [('delay_ms', 'Echo time', 5, 'ms'), ('delay_feedback', 'Feedback', .05, '%'), ('delay_tone', 'Echo tone', 100, 'Hz'), ('delay_mix', 'Echo blend', .05, '%')]),
            (
                'Communications',
                [
                    ('comms_mode', 'Channel type', 1, 'channel'),
                    ('comms_drive', 'Channel drive', 1, 'dB'),
                    ('comms_gate', 'Radio gate threshold', 1, 'dB'),
                    ('comms_static', 'Radio static', .05, '%'),
                    ('comms_click', 'End click', .05, '%'),
                    ('comms_mix', 'Channel blend', .05, '%'),
                ],
            ),
            ('Parallel distortion', [('parallel_drive', 'Drive', 1, 'dB'), ('parallel_mix', 'Rough layer blend', .05, '%')]),
        ]
        enable_keys = {
            'Harmony': 'harmony_enabled',
            'Resonator': 'resonator_enabled',
            'Delay': 'delay_enabled',
            'Communications': 'comms_enabled',
            'Parallel distortion': 'parallel_enabled',
        }
        self.extra_units = {}
        self._label(editor, 'DSP MODULES', 8, 'subtle', True).pack(anchor='w', pady=(4, 6))

        for title, settings in groups:
            box = tk.Frame(editor, bg=self.c['card'], highlightthickness=1, highlightbackground=self.c['border'])
            box.pack(fill='x', pady=(0, 6))
            header = tk.Frame(box, bg=self.c['card'], padx=8, pady=4)
            header.pack(fill='x')
            details = tk.Frame(box, bg=self.c['card'], padx=10, pady=6)
            toggle = self._button(header, title + '  +', lambda t=title: self._toggle_effect_section(t))
            toggle.configure(bg=self.c['card'], highlightthickness=0, padx=2, pady=4, anchor='w', font=('Segoe UI', 9, 'bold'))
            toggle.pack(side='left', fill='x', expand=True)
            self.effect_sections[title] = (toggle, details)
            if title in enable_keys:
                key = enable_keys[title]
                variable = tk.BooleanVar(value=bool(EXTRA_DEFAULTS[key]))
                self.effect_enabled[key] = variable
                tk.Checkbutton(
                    header,
                    text='On',
                    variable=variable,
                    command=self._on_custom_slider_change,
                    bg=self.c['card'],
                    fg=self.c['text'],
                    selectcolor=self.c['selected'],
                    activebackground=self.c['card'],
                    activeforeground=self.c['accent'],
                ).pack(side='right')
            for key, label, step, unit in settings:
                row = tk.Frame(details, bg=self.c['card'])
                row.pack(fill='x', pady=(4, 0))
                self._label(row, label, 9).pack(side='left')
                self.extra_units[key] = unit
                value = EXTRA_DEFAULTS[key]
                readout = self._label(row, self._format_extra(value, unit), 9, 'accent', True)
                readout.pack(side='right')
                self.extra_readouts[key] = readout
                low, high = EXTRA_LIMITS[key]
                scale = self._scale(details, low, high, step, self._on_custom_slider_change)
                scale.set(value)
                scale.pack(fill='x', pady=(1, 6))
                self.extra_scales[key] = scale
            if title == 'Vocal character':
                details.pack(fill='x')
                toggle.configure(text=title + '  -')

        editor_actions.columnconfigure(0, weight=2)
        editor_actions.columnconfigure(1, weight=1)
        self._button(editor_actions, 'Save Custom Voice', self._save_preset_prompt, primary=True).grid(
            row=0, column=0, sticky='ew', padx=(0, 8)
        )
        self._button(editor_actions, 'Reset', self._reset_controls).grid(row=0, column=1, sticky='ew')

    def _toggle_effect_section(self, title):
        toggle, details = self.effect_sections[title]
        if details.winfo_manager():
            details.pack_forget()
            toggle.configure(text=title + '  +')
        else:
            details.pack(fill='x', after=toggle.master)
            toggle.configure(text=title + '  -')

    def _scale(self, parent, low, high, step, command, **kwargs):
        return tk.Scale(
            parent,
            from_=low,
            to=high,
            resolution=step,
            orient='horizontal',
            showvalue=False,
            command=command,
            bg=parent.cget('bg'),
            fg=self.c['text'],
            troughcolor=self.c['border'],
            activebackground=self.c['accent'],
            highlightthickness=0,
            sliderrelief='flat',
            bd=0,
            sliderlength=14,
            width=7,
            **kwargs,
        )

    def _preset_latency_ms(self, name, preset):
        if name in self._latency_cache:
            return self._latency_cache[name]
        try:
            board = preset['builder']()
            rate = max(8000, int(self.engine.sample_rate or 44100))
            dsp_frames = board.latency_frames(rate) if hasattr(board, 'latency_frames') else 0
            ms = (dsp_frames + self.engine.blocksize) * 1000.0 / rate
        except Exception:
            ms = 12.0
        self._latency_cache[name] = ms
        return ms

    def _render_library(self):
        if self._active_tab == 'soundboard':
            self._render_soundboard_grid()
        else:
            self._render_presets_grid()

    def _render_presets_grid(self):
        for widget in self.presets_grid_frame.winfo_children():
            widget.destroy()
        self.preset_buttons.clear()
        self.all_presets = dict(VOICE_PRESETS)
        self.user_presets = load_user_presets()
        self.all_presets.update(self.user_presets)

        query = self.search.get().strip().lower()
        found = [
            (n, p)
            for n, p in self.all_presets.items()
            if (self.category.get() == 'All voices' or p['category'] == self.category.get())
            and query in (n + ' ' + p['description']).lower()
        ]
        self.count_label.configure(text=f'{len(found)} voices')

        for index, (name, preset) in enumerate(found):
            selected = name == self.selected_preset_name
            bg_col = self.c['selected'] if selected else self.c['card']
            border_col = self.c['accent'] if selected else self.c['border']
            card = tk.Frame(
                self.presets_grid_frame,
                bg=bg_col,
                padx=12,
                pady=10,
                highlightthickness=1,
                highlightbackground=border_col,
            )
            card.grid(row=index // 3, column=index % 3, sticky='nsew', padx=(0, 10), pady=(0, 10))

            head = tk.Frame(card, bg=bg_col)
            head.pack(fill='x')
            title_lbl = tk.Label(
                head,
                text=name,
                font=('Segoe UI', 10, 'bold'),
                bg=bg_col,
                fg=self.c['accent'] if selected else self.c['text'],
                anchor='w',
                justify='left',
                wraplength=150,
                cursor='hand2',
            )
            title_lbl.pack(side='left', fill='x', expand=True)

            ms = self._preset_latency_ms(name, preset)
            badge_bg = '#122B23' if ms < 25 else self.c['warn_bg'] if ms < 105 else self.c['raised']
            badge_fg = self.c['accent'] if ms < 25 else self.c['warn'] if ms < 105 else self.c['muted']
            lat_lbl = tk.Label(
                head,
                text=f'~{ms:.0f}ms',
                font=('Consolas', 8, 'bold'),
                bg=badge_bg,
                fg=badge_fg,
                padx=6,
                pady=1,
                cursor='hand2',
            )
            lat_lbl.pack(side='right', anchor='n')

            desc_text = preset['description']
            if len(desc_text) > 74:
                desc_text = desc_text[:71].rstrip() + '...'
            desc_lbl = tk.Label(
                card,
                text=desc_text,
                font=('Segoe UI', 8),
                bg=bg_col,
                fg=self.c['muted'],
                anchor='w',
                justify='left',
                wraplength=210,
                height=2,
                cursor='hand2',
            )
            desc_lbl.pack(fill='x', pady=(6, 8))

            foot = tk.Frame(card, bg=bg_col)
            foot.pack(fill='x')
            status_lbl = tk.Label(
                foot,
                text='● Active' if selected else preset['category'],
                font=('Segoe UI', 8, 'bold' if selected else 'normal'),
                bg=bg_col,
                fg=self.c['accent'] if selected else self.c['subtle'],
                cursor='hand2',
            )
            status_lbl.pack(side='left')

            if name in self.user_presets:
                del_btn = tk.Button(
                    foot,
                    text='Delete',
                    command=lambda n=name: self._delete_user_preset(n),
                    font=('Segoe UI', 8),
                    bg=bg_col,
                    fg=self.c['danger'],
                    activebackground=bg_col,
                    activeforeground=self.c['danger'],
                    relief='flat',
                    bd=0,
                    cursor='hand2',
                )
                del_btn.pack(side='right', padx=(8, 0))

            exp_btn = tk.Button(
                foot,
                text='Export',
                command=lambda n=name: self._export_voice_by_name(n),
                font=('Segoe UI', 8),
                bg=bg_col,
                fg=self.c['info'],
                activebackground=bg_col,
                activeforeground=self.c['text'],
                relief='flat',
                bd=0,
                cursor='hand2',
            )
            exp_btn.pack(side='right')

            activate = lambda _e=None, n=name, p=preset: self._activate_preset(n, p)
            for w in (card, head, title_lbl, lat_lbl, desc_lbl, foot, status_lbl):
                w.bind('<Button-1>', activate)
            self.preset_buttons[name] = title_lbl

        for col in (0, 1, 2):
            self.presets_grid_frame.columnconfigure(col, weight=1, uniform='voices')
        if not found:
            self._label(
                self.presets_grid_frame,
                'No voices found. Try another search or category pill.',
                11,
                'muted',
                wraplength=420,
            ).grid(row=0, column=0, columnspan=3, pady=40)
        self.library_canvas.yview_moveto(0)

    def _render_soundboard_grid(self):
        for widget in self.presets_grid_frame.winfo_children():
            widget.destroy()
        clips = soundboard.list_sound_clips()
        query = self.search.get().strip().lower()
        found = [c for c in clips if query in (c['name'] + ' ' + c['ext']).lower()]
        self.count_label.configure(text=f'{len(found)} clips')

        if not found:
            empty = tk.Frame(
                self.presets_grid_frame, bg=self.c['card'], padx=24, pady=28,
                highlightthickness=1, highlightbackground=self.c['border'],
            )
            empty.grid(row=0, column=0, columnspan=3, sticky='ew', pady=24)
            self._label(empty, 'No soundboard clips imported yet.', 12, bold=True).pack(anchor='center')
            self._label(
                empty,
                'Import .wav, .mp3, .flac, or .ogg clips to play them into your virtual microphone or share them.',
                9,
                'muted',
                wraplength=440,
                justify='center',
            ).pack(anchor='center', pady=(6, 14))
            self._button(empty, '+ Import Sound File', self._import_sound_prompt, primary=True).pack(anchor='center')
            for col in (0, 1, 2):
                self.presets_grid_frame.columnconfigure(col, weight=1, uniform='voices')
            return

        for index, clip in enumerate(found):
            card = tk.Frame(
                self.presets_grid_frame,
                bg=self.c['card'],
                padx=12,
                pady=10,
                highlightthickness=1,
                highlightbackground=self.c['border'],
            )
            card.grid(row=index // 3, column=index % 3, sticky='nsew', padx=(0, 10), pady=(0, 10))
            head = tk.Frame(card, bg=self.c['card'])
            head.pack(fill='x')
            self._label(head, clip['name'], 10, bold=True, wraplength=155, justify='left').pack(side='left', fill='x', expand=True)
            ext_lbl = tk.Label(
                head,
                text=clip['ext'].lstrip('.').upper(),
                font=('Consolas', 8, 'bold'),
                bg=self.c['raised'],
                fg=self.c['info'],
                padx=6,
                pady=1,
            )
            ext_lbl.pack(side='right')
            self._label(card, f"{clip['duration_sec']:.1f}s  ·  {clip['size_kb']} KB", 8, 'muted').pack(
                anchor='w', pady=(4, 10)
            )

            actions = tk.Frame(card, bg=self.c['card'])
            actions.pack(fill='x')
            self._button(actions, 'Play', lambda c=clip: self._play_soundboard_clip(c), primary=True).pack(
                side='left', padx=(0, 6)
            )
            self._button(actions, 'Share', lambda c=clip: self._export_sound_clip_prompt(c), tone='info').pack(
                side='left'
            )
            del_btn = tk.Button(
                actions,
                text='Remove',
                command=lambda c=clip: self._delete_sound_clip_prompt(c),
                font=('Segoe UI', 8),
                bg=self.c['card'],
                fg=self.c['danger'],
                activebackground=self.c['card'],
                relief='flat',
                bd=0,
                cursor='hand2',
            )
            del_btn.pack(side='right')

        for col in (0, 1, 2):
            self.presets_grid_frame.columnconfigure(col, weight=1, uniform='voices')
        self.library_canvas.yview_moveto(0)

    def _play_soundboard_clip(self, clip):
        if self.engine.is_running:
            ok = self.engine.play_sound(clip['path'])
            self._status(
                f"Playing clip into live output: {clip['name']}" if ok else f"Could not play clip: {clip['name']}",
                not ok,
            )
            return
        try:
            with AudioFile(clip['path']) as f:
                sr = int(f.samplerate)
                audio = f.read(f.frames).astype('float32')
            target_dev = None
            idx = self.monitor_combo.current()
            if 0 <= idx < len(getattr(self, 'device_outputs', [])):
                target_dev = self.device_outputs[idx]['index']
                dev_sr = int(sd.query_devices(target_dev)['default_samplerate'])
                if dev_sr > 0 and dev_sr != sr:
                    audio = Resample(target_sample_rate=dev_sr)(audio, sample_rate=sr)
                    sr = dev_sr
            sd.stop()
            sd.play(audio.T, samplerate=sr, device=target_dev)
            self._status(f"Previewing clip locally (headphones): {clip['name']}")
        except Exception as exc:
            self._status(f'Could not preview clip: {exc}', True)

    def _stop_soundboard(self):
        self.engine.stop_sound()
        try:
            sd.stop()
        except Exception:
            pass
        self._status('Stopped soundboard playback.')

    def _import_sound_prompt(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title='Import Sound Clip',
            filetypes=[('Audio files', '*.wav *.mp3 *.flac *.ogg *.aiff'), ('All files', '*.*')],
        )
        if not path:
            return
        try:
            clip = soundboard.import_sound_clip(path)
            self._switch_tab('soundboard')
            self._status(f"Imported sound clip: {clip['name']}")
        except Exception as exc:
            messagebox.showerror('Cannot import sound clip', str(exc), parent=self.root)

    def _export_sound_clip_prompt(self, clip):
        dest = filedialog.asksaveasfilename(
            parent=self.root,
            title=f"Share Sound Clip — {clip['name']}",
            initialfile=clip['filename'],
            defaultextension=clip['ext'],
            filetypes=[(f"{clip['ext'].upper()} audio", f"*{clip['ext']}"), ('All files', '*.*')],
        )
        if not dest:
            return
        try:
            soundboard.export_sound_clip(clip['path'], dest)
            self._status(f"Exported clip to {os.path.basename(dest)}")
        except Exception as exc:
            messagebox.showerror('Cannot export clip', str(exc), parent=self.root)

    def _delete_sound_clip_prompt(self, clip):
        if messagebox.askyesno('Remove sound clip', f"Remove \"{clip['name']}\" from your soundboard?", parent=self.root):
            try:
                soundboard.delete_sound_clip(clip['path'])
                self._render_soundboard_grid()
                self._status(f"Removed sound clip: {clip['name']}")
            except Exception as exc:
                messagebox.showerror('Cannot remove clip', str(exc), parent=self.root)

    def _current_editor_params_dict(self):
        return dict(
            pitch=float(self.pitch_scale.get()),
            distortion=float(self.dist_scale.get()),
            reverb=float(self.reverb_scale.get()),
            bitcrush=int(self.bit_scale.get()),
            base_voice=self._editor_base_voice,
            **self._extra_values(),
        )

    def _export_active_voice(self):
        self._export_voice_by_name(self.selected_preset_name)

    def _export_voice_by_name(self, name):
        is_live_custom = name == 'Custom voice'
        suggested = 'custom_voice.vmvoice' if is_live_custom else f"{name.replace('/', '_').replace(' ', '_')}.vmvoice"
        dest = filedialog.asksaveasfilename(
            parent=self.root,
            title=f'Share Voice Preset — {name}',
            initialfile=suggested,
            defaultextension='.vmvoice',
            filetypes=[('Voice Studio Preset', '*.vmvoice'), ('JSON preset', '*.json')],
        )
        if not dest:
            return
        try:
            if is_live_custom:
                export_voice_preset('Custom voice', dest, custom_params=self._current_editor_params_dict())
            else:
                export_voice_preset(name, dest)
            self._status(f'Exported shareable voice: {os.path.basename(dest)}')
        except Exception as exc:
            messagebox.showerror('Cannot export voice', str(exc), parent=self.root)

    def _export_pack_prompt(self):
        user = load_user_presets()
        if not user:
            messagebox.showinfo(
                'No custom voices yet',
                'Save or customize a voice first before exporting a custom voice pack (you can still share any built-in voice individually).',
                parent=self.root,
            )
            return
        dest = filedialog.asksaveasfilename(
            parent=self.root,
            title='Export All Custom Voices Pack',
            initialfile='voice_studio_pack.json',
            defaultextension='.json',
            filetypes=[('Voice Pack JSON', '*.json'), ('Voice Studio Pack', '*.vmvoice')],
        )
        if not dest:
            return
        try:
            names = export_voice_pack(dest)
            self._status(f'Exported {len(names)} custom voices to {os.path.basename(dest)}')
        except Exception as exc:
            messagebox.showerror('Cannot export pack', str(exc), parent=self.root)

    def _export_processed_audio_prompt(self):
        default_src = os.path.join(os.path.dirname(__file__), 'previews', 'source.wav')
        src = filedialog.askopenfilename(
            parent=self.root,
            title='Select Audio File to Render with Active Voice',
            initialdir=os.path.dirname(default_src) if os.path.exists(default_src) else os.path.dirname(__file__),
            filetypes=[('Audio files', '*.wav *.mp3 *.flac *.ogg *.aiff'), ('All files', '*.*')],
        )
        if not src:
            return
        voice_name = self.selected_preset_name
        stem = voice_name.replace('/', '_').replace(' ', '_')
        dest = filedialog.asksaveasfilename(
            parent=self.root,
            title=f'Export Processed Audio ({voice_name})',
            initialfile=f'{stem}_processed.wav',
            defaultextension='.wav',
            filetypes=[('WAV audio', '*.wav'), ('MP3 audio', '*.mp3'), ('FLAC audio', '*.flac')],
        )
        if not dest:
            return
        try:
            if voice_name == 'Custom voice':
                p = self._current_editor_params_dict()
                builder = lambda: create_custom_voice(
                    p['pitch'], p['reverb'], p['distortion'], p['bitcrush'],
                    base_voice=p.get('base_voice'), **{k: p[k] for k in EXTRA_DEFAULTS},
                )
            else:
                builder = self.all_presets[voice_name]['builder']
            soundboard.export_processed_audio(src, builder, dest, sample_rate=int(self.engine.sample_rate or 44100))
            self._status(f'Exported processed sound: {os.path.basename(dest)}')
        except Exception as exc:
            messagebox.showerror('Cannot export processed audio', str(exc), parent=self.root)

    def _import_voice_prompt(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title='Import Shared Voice Preset (.vmvoice / .json)',
            filetypes=[('Voice Presets', '*.vmvoice *.json'), ('All files', '*.*')],
        )
        if not path:
            return
        try:
            imported = import_voice_presets(path, conflict='rename')
            self._latency_cache.clear()
            self.category.set('All voices')
            self._style_category_pills()
            self._switch_tab('voices')
            user = load_user_presets()
            if imported and imported[0] in user:
                self._activate_preset(imported[0], user[imported[0]])
            self._status(f"Imported {len(imported)} voice(s): {', '.join(imported)}")
        except Exception as exc:
            messagebox.showerror('Cannot import voice preset', str(exc), parent=self.root)

    def _open_share_dialog(self, mode='export'):
        win = tk.Toplevel(self.root)
        win.title('Share Voices & Sounds')
        win.configure(bg=self.c['panel'])
        win.geometry('520x390')
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        top = tk.Frame(win, bg=self.c['card'], padx=18, pady=14)
        top.pack(fill='x')
        self._label(top, 'Share Voices & Sound Clips', 13, bold=True).pack(anchor='w')
        self._label(
            top,
            'Export shareable .vmvoice preset files, bundle custom packs, or render processed .wav/.mp3 audio clips.',
            9,
            'muted',
            wraplength=470,
            justify='left',
        ).pack(anchor='w', pady=(3, 0))
        tk.Frame(win, bg=self.c['border'], height=1).pack(fill='x')

        body = tk.Frame(win, bg=self.c['panel'], padx=18, pady=16)
        body.pack(fill='both', expand=True)

        if mode == 'import':
            items = [
                (
                    'Import Shared Voice Preset (.vmvoice / .json)',
                    'Load voices shared by friends directly into your Custom library.',
                    'Import Voice',
                    True,
                    lambda: (win.destroy(), self._import_voice_prompt()),
                ),
                (
                    'Import Soundboard Audio Clip (.wav / .mp3 / .flac)',
                    'Add sound effects into your Soundboard tab for instant mic playback.',
                    'Import Sound',
                    False,
                    lambda: (win.destroy(), self._import_sound_prompt()),
                ),
            ]
        else:
            items = [
                (
                    f'Export Active Voice ({self.selected_preset_name})',
                    'Saves a portable .vmvoice file capturing exact DSP sliders & filters.',
                    'Export Voice',
                    True,
                    lambda: (win.destroy(), self._export_active_voice()),
                ),
                (
                    'Export All Custom Voices Pack (.json)',
                    'Bundles all saved user voices into one shareable pack.',
                    'Export Pack',
                    False,
                    lambda: (win.destroy(), self._export_pack_prompt()),
                ),
                (
                    'Render & Export Processed Audio (.wav / .mp3)',
                    'Processes any recording through the active voice for Discord or social sharing.',
                    'Render Audio',
                    False,
                    lambda: (win.destroy(), self._export_processed_audio_prompt()),
                ),
            ]

        for title, desc, btn_text, is_pri, action in items:
            row = tk.Frame(
                body, bg=self.c['card'], padx=14, pady=12, highlightthickness=1, highlightbackground=self.c['border']
            )
            row.pack(fill='x', pady=(0, 10))
            info = tk.Frame(row, bg=self.c['card'])
            info.pack(side='left', fill='x', expand=True, padx=(0, 12))
            self._label(info, title, 10, bold=True, wraplength=310, justify='left').pack(anchor='w')
            self._label(info, desc, 8, 'muted', wraplength=310, justify='left').pack(anchor='w', pady=(2, 0))
            self._button(row, btn_text, action, primary=is_pri).pack(side='right')

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
        self._editor_base_voice = preset.get('params', {}).get('base_voice')
        if 'params' in preset:
            self._syncing = True
            for attr, key in (('pitch', 'pitch'), ('dist', 'distortion'), ('reverb', 'reverb'), ('bit', 'bitcrush')):
                getattr(self, attr + '_scale').set(preset['params'][key])
            for key, scale in self.extra_scales.items():
                scale.set(preset['params'].get(key, EXTRA_DEFAULTS[key]))
            for key, variable in self.effect_enabled.items():
                variable.set(bool(preset['params'].get(key, EXTRA_DEFAULTS[key])))
            self.root.update()
            self._syncing = False
            self._readouts()
        self._render_library()
        self._update_latency_label()
        self._status(f'Voice selected: {name}')

    def _load_editor_params(self, params):
        if self._slider_job:
            self.root.after_cancel(self._slider_job)
            self._slider_job = None
        self._syncing = True
        try:
            for attr, key in (('pitch', 'pitch'), ('dist', 'distortion'), ('reverb', 'reverb'), ('bit', 'bitcrush')):
                getattr(self, attr + '_scale').set(params[key])
            for key, scale in self.extra_scales.items():
                scale.set(params.get(key, EXTRA_DEFAULTS[key]))
            for key, variable in self.effect_enabled.items():
                variable.set(bool(params.get(key, EXTRA_DEFAULTS[key])))
            self.root.update()
        finally:
            self._syncing = False
        self._editor_base_voice = params.get('base_voice')
        self._readouts()

    def _recall_voice(self):
        preset = self.all_presets.get(self.selected_preset_name)
        if preset is None:
            self._status('The current custom voice is already in the editor.')
            self.editor_canvas.yview_moveto(0)
            return
        name = self.selected_preset_name
        params = dict(preset['params']) if 'params' in preset else builtin_editor_params(name)
        self._load_editor_params(params)
        self.editor_canvas.yview_moveto(0)
        self._status(f'Loaded {name} into Voice Shaper. Original filters are retained.')

    def _apply_hotkey(self, save=True):
        name = self.hotkey_var.get()
        if name == 'Disabled':
            if self._hotkey:
                self._hotkey.close()
                self._hotkey = None
            self.hotkey_status.configure(text='Shortcut off', fg=self.c['subtle'])
        elif self._hotkey and self._hotkey.name == name:
            return
        else:
            try:
                replacement = GlobalHotkey(name)
            except Exception as exc:
                active = f' ({self._hotkey.name})' if self._hotkey else ''
                self.hotkey_status.configure(text=str(exc) + active, fg=self.c['danger'])
                if self._hotkey:
                    self.hotkey_var.set(self._hotkey.name)
                return
            if self._hotkey:
                self._hotkey.close()
            self._hotkey = replacement
            self.hotkey_status.configure(text=f'Global hotkey ready ({name})', fg=self.c['subtle'])
        if save:
            self._save_audio_settings()

    def _poll_hotkey(self):
        if self._hotkey:
            try:
                while True:
                    self._hotkey.events.get_nowait()
                    self._toggle_stream()
            except queue.Empty:
                pass
        self._hotkey_job = self.root.after(60, self._poll_hotkey)

    @staticmethod
    def _format_extra(value, unit):
        if unit == 'channel':
            return ('Off', 'Telephone', 'Radio')[int(value)]
        if unit == '%':
            return f'{value * 100:.0f}%'
        return f'{value:+.1f} {unit}' if unit in ('st', 'dB') else f'{value:.0f} {unit}'

    def _extra_values(self):
        return {
            **{key: scale.get() for key, scale in self.extra_scales.items()},
            **{key: float(variable.get()) for key, variable in self.effect_enabled.items()},
        }

    def _readouts(self):
        self.pitch_val_lbl.configure(text=f'{self.pitch_scale.get():+.1f} st')
        self.dist_val_lbl.configure(text=f'{self.dist_scale.get():.0f} dB')
        self.reverb_val_lbl.configure(text=f'{self.reverb_scale.get() * 100:.0f}%')
        self.bit_val_lbl.configure(text=f'{self.bit_scale.get():.0f} bits')
        for key, value in self._extra_values().items():
            if key not in self.extra_readouts:
                continue
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
            board = create_custom_voice(
                self.pitch_scale.get(),
                self.reverb_scale.get(),
                self.dist_scale.get(),
                self.bit_scale.get(),
                base_voice=self._editor_base_voice,
                **self._extra_values(),
            )
            self.engine.set_voice(board)
            self.selected_preset_name = 'Custom voice'
            self.active_name.configure(text='Custom voice')
            self.active_description.configure(text='Your own mix. Save or Share it anytime.')
            self._render_library()
            self._update_latency_label()
            self._status('Custom voice active. Save it to keep in your library.')
        except Exception as exc:
            self._status(f'Cannot apply controls: {exc}', True)

    def _reset_controls(self):
        self._editor_base_voice = None
        self._syncing = True
        for attr, value in (('pitch', 0), ('dist', 0), ('reverb', 0), ('bit', 16)):
            getattr(self, attr + '_scale').set(value)
        for key, scale in self.extra_scales.items():
            scale.set(EXTRA_DEFAULTS[key])
        for key, variable in self.effect_enabled.items():
            variable.set(bool(EXTRA_DEFAULTS[key]))
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
            save_user_preset(
                name,
                self.pitch_scale.get(),
                self.dist_scale.get(),
                self.reverb_scale.get(),
                self.bit_scale.get(),
                base_voice=self._editor_base_voice,
                **self._extra_values(),
            )
            self._latency_cache.pop(name, None)
            self.category.set('All voices')
            self._style_category_pills()
            self.search.set('')
            self._switch_tab('voices')
            self._activate_preset(name, load_user_presets()[name])
            self._status(f'Saved voice: {name}')
        except (ValueError, OSError) as exc:
            messagebox.showerror('Cannot save voice', str(exc), parent=self.root)

    def _delete_user_preset(self, name):
        if messagebox.askyesno('Delete saved voice', f'Delete "{name}"?', parent=self.root):
            try:
                delete_user_preset(name)
                self._latency_cache.pop(name, None)
                if self.selected_preset_name == name:
                    self._activate_preset('Clean (Normal)', VOICE_PRESETS['Clean (Normal)'])
                self._render_library()
            except (OSError, ValueError) as exc:
                messagebox.showerror('Cannot delete voice', str(exc), parent=self.root)

    def _toggle_audio_setup(self):
        if self.devices_panel.winfo_manager():
            self._save_audio_settings()
            self.devices_panel.pack_forget()
            self.setup_btn.configure(text='Audio Setup')
        else:
            self.devices_panel.pack(fill='x', before=self.audio_controls, pady=(0, 12))
            self.setup_btn.configure(text='Done')

    def _save_audio_settings(self):
        data = {
            key: combo.get().split('] ', 1)[-1]
            for key, combo in (('mic', self.in_combo), ('output', self.out_combo), ('monitor', self.monitor_combo))
        }
        data['hotkey'] = self.hotkey_var.get()
        data['mic_hygiene'] = bool(self.hygiene_var.get())
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
            for key, combo, devices in (
                ('output', self.out_combo, outputs),
                ('mic', self.in_combo, inputs),
                ('monitor', self.monitor_combo, outputs),
            ):
                previous = combo.get().split('] ', 1)[-1] or self._saved_audio.get(key)
                names = [d['name'] for d in devices]
                combo['values'] = names + (['Headset preview only'] if key == 'output' else [])
                restored = next((i for i, n in enumerate(names) if n.split('] ', 1)[-1] == previous), None)
                if previous == 'Headset preview only' and key == 'output':
                    combo.set(previous)
                    continue
                if restored is not None:
                    combo.current(restored)
                    continue
                if key == 'output':
                    candidates = [
                        i
                        for i, n in enumerate(names)
                        if any(term in n.lower() for term in ('cable input', 'virtual cable', 'voicemod virtual', 'dummy output (voicemod)'))
                    ]
                    preferred = next(
                        (i for i in candidates if 'dummy output (voicemod)' in names[i].lower() and '(MME)' in names[i]),
                        None,
                    )
                else:
                    candidates = [
                        i
                        for i, n in enumerate(names)
                        if not any(term in n.lower() for term in ('voicemod', 'cable', 'sound mapper', 'primary sound'))
                    ]
                    if key == 'monitor':
                        candidates = [i for i in candidates if any(t in names[i].lower() for t in ('headphone', 'speaker'))]
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
            self.route_label.configure(
                text='Virtual mic ready' if routed else 'Headset preview only'
            )
            self._status('Ready. Choose a voice and press Start.', not (inputs and outputs))
        except Exception as exc:
            self.device_inputs, self.device_outputs = [], []
            self._status(f'Audio devices unavailable: {exc}', True)

    def _on_hear_myself_change(self):
        enabled = self.hear_var.get()
        index = self.monitor_combo.current()
        if enabled and index < 0:
            self.hear_var.set(False)
            self._status('Select headphones in Audio Setup before enabling Hear myself.', True)
            return
        try:
            device = self.device_outputs[index]['index'] if index >= 0 else None
            self.engine.set_monitor(enabled, device)
            self._status(
                'Headphone monitoring on.'
                if enabled
                else 'Hear myself off. Headset preview is silent.'
                if self.engine.preview_only
                else 'Headphone monitoring off. App output continues.'
            )
        except Exception as exc:
            self.hear_var.set(False)
            self.engine.set_monitor(False)
            self._status(f'Cannot enable monitoring: {exc}', True)

    def _on_mute_change(self):
        self.engine.mute_mic = self.mute_var.get()

    def _on_hygiene_change(self):
        self.engine.set_mic_hygiene(self.hygiene_var.get())

    def _update_latency_label(self):
        ms = self.engine.current_latency_ms()
        tier = 'low' if ms < 25 else 'moderate' if ms < 105 else 'buffered'
        self.latency_label.configure(text=f'DSP + block latency: ~{ms:.0f} ms ({tier})')

    def _on_vol_change(self, value):
        self.engine.output_gain = float(value)

    def _status(self, text, error=False):
        self.status_lbl.configure(text=text, fg=self.c['danger'] if error else self.c['muted'])

    def _open_voice_test(self):
        if self._voice_test is not None and not self._voice_test.closed:
            self._voice_test.window.lift()
            return
        if self.in_combo.current() < 0 or self.monitor_combo.current() < 0:
            self._status('Choose a microphone and headphones in Audio Setup before testing.', True)
            return
        if self.engine.is_running:
            self._toggle_stream()
        from voice_test import VoiceTestWindow

        builders = {name: preset['builder'] for name, preset in self.all_presets.items()}
        pitch, reverb, dist, bits = self.pitch_scale.get(), self.reverb_scale.get(), self.dist_scale.get(), self.bit_scale.get()
        extras = self._extra_values()
        base = self._editor_base_voice
        builders['Current editor'] = lambda: create_custom_voice(pitch, reverb, dist, bits, base_voice=base, **extras)
        selected = self.selected_preset_name if self.selected_preset_name in builders else 'Current editor'
        self._voice_test = VoiceTestWindow(
            self,
            builders,
            selected,
            self.device_inputs[self.in_combo.current()]['index'],
            self.device_outputs[self.monitor_combo.current()]['index'],
        )
        self._status('Live output paused for A/B comparison. Close test window before restarting.')

    def _toggle_stream(self):
        if self._voice_test is not None and not self._voice_test.closed and not self.engine.is_running:
            self._status('Close A/B Test before restarting live audio.', True)
            return
        if self.engine.is_running:
            self.engine.stop()
        else:
            if self.in_combo.current() < 0 or self.monitor_combo.current() < 0:
                self._status('Choose your headset microphone and headphones in Audio Setup.', True)
                return
            try:
                output_index = self.out_combo.current()
                preview = not (0 <= output_index < len(self.device_outputs))
                monitor_device = self.device_outputs[self.monitor_combo.current()]['index']
                output_device = monitor_device if preview else self.device_outputs[output_index]['index']
                mic = self.device_inputs[self.in_combo.current()]
                if not preview:
                    target_api = self.device_outputs[output_index]['raw']['hostapi']
                    match = next(
                        (
                            i
                            for i, d in enumerate(self.device_inputs)
                            if d['raw']['name'] == mic['raw']['name'] and d['raw']['hostapi'] == target_api
                        ),
                        None,
                    )
                    if match is not None:
                        self.in_combo.current(match)
                self._save_audio_settings()
                self.engine.start(
                    self.device_inputs[self.in_combo.current()]['index'],
                    output_device,
                    monitor_device,
                    preview_only=preview,
                )
            except Exception as exc:
                self._status(f'Could not start audio: {exc}', True)
                return
        running = self.engine.is_running
        self.toggle_btn.configure(
            text='Stop voice changer' if running else 'Start voice changer',
            bg=self.c['danger_bg'] if running else self.c['accent'],
            fg=self.c['danger'] if running else self.c['ink'],
            highlightbackground='#3B262B' if running else self.c['accent'],
        )
        self.live_badge.configure(
            text='● LIVE' if running else '● STOPPED',
            bg=self.c['selected'] if running else self.c['raised'],
            fg=self.c['accent'] if running else self.c['muted'],
        )
        for combo in (self.in_combo, self.out_combo, self.monitor_combo):
            combo.configure(state='disabled' if running else 'readonly')
        self.refresh_btn.configure(state='disabled' if running else 'normal')
        self.hear_var.set(self.engine.monitor_enabled)
        if running and self.engine._route_guard is not None:
            self.route_label.configure(text='Processed feed active')
        elif not running:
            self.route_label.configure(text='Audio stopped')
        self._status(
            (
                f'Headset preview / {self.selected_preset_name}.'
                if self.engine.preview_only
                else f'Live / {self.selected_preset_name}'
            )
            if running
            else 'Stopped. Ready when you are.'
        )
        if running and self.engine.monitor_error:
            self._status(f'App output is live; headphone monitoring unavailable: {self.engine.monitor_error}', True)

    def _update_meter(self):
        canvas = self.meter_canvas
        canvas.delete('all')
        level = self.engine.current_rms_level
        db = 20 * math.log10(max(level, 1e-6))
        value = max(0.0, min(1.0, (db + 60) / 60))
        width = max(1, canvas.winfo_width())
        segments = 16
        gap = 2
        seg_w = max(2, (width - gap * (segments - 1)) / segments)
        lit = int(round(value * segments))
        for i in range(segments):
            x0 = i * (seg_w + gap)
            x1 = x0 + seg_w
            if i < lit:
                color = self.c['danger'] if i >= 13 else self.c['warn'] if i >= 10 else self.c['accent']
            else:
                color = self.c['raised']
            canvas.create_rectangle(x0, 1, x1, 9, fill=color, width=0)
        self.meter_label.configure(text=f'{db:.0f} dB' if level > 1e-6 else '-- dB')

        if self.engine._route_guard is not None and self.engine._route_guard.error:
            routing_error = self.engine._route_guard.error
            if self.engine.is_running:
                self._toggle_stream()
            self._status(f'Stopped to prevent mixed audio: {routing_error}', True)
        if self.engine.last_error:
            self._status(f'Audio error: {self.engine.last_error}', True)
        self._meter_job = self.root.after(50, self._update_meter)

    def on_closing(self):
        if self._voice_test is not None and not self._voice_test.closed:
            self._voice_test.close()
        self._save_audio_settings()
        if self._hotkey:
            self._hotkey.close()
        for job in (self._slider_job, self._meter_job, self._hotkey_job):
            if job:
                self.root.after_cancel(job)
        self.engine.stop()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = VoiceModApp(root)
    root.mainloop()
