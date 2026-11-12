"""
voices.py - Modular Voice Presets for Real-Time Voice Changer
-----------------------------------------------------------
Speech-focused presets using streaming native pitch processing and gentle leveling.
"""

import json
import os
import math
import tempfile
from pedalboard import (
    Pedalboard as NativePedalboard,
    PitchShift as NativePitchShift,
    Chorus,
    Distortion,
    Reverb,
    Delay,
    Bitcrush,
    HighpassFilter,
    LowpassFilter,
    PeakFilter,
    Compressor,
    NoiseGate,
    GSMFullRateCompressor,
    Phaser,
    Gain, LowShelfFilter, HighShelfFilter
)

from streaming_dsp import VoiceChain
from voice_effects import (
    FormantShift,
    RingModulation,
    Harmony,
    Resonator,
    ToneDelay,
    ParallelDistortion,
    CommunicationChannel,
    SampleRateReduce,
    Vocoder,
    DuckedReverb,
    EnvelopeTalkbox,
    Whisperizer,
    FrequencyShifter,
    SubharmonicTitan,
    ReverseGranulator,
    ShimmerReverb,
    TapeWowFlutter,
)


def Pedalboard(effects):
    return VoiceChain(effects, NativePedalboard, NativePitchShift)


PitchShift = NativePitchShift

CUSTOM_PRESETS_FILE = os.path.join(os.path.dirname(__file__), "custom_presets.json")


def speech_chain(effects, makeup_db=1.0):
    # Remove sub-rumble before transformation, then gently level the result.
    return Pedalboard([
        HighpassFilter(cutoff_frequency_hz=75),
        *effects,
        Compressor(threshold_db=-22, ratio=2.2, attack_ms=10, release_ms=110),
        Gain(gain_db=makeup_db),
    ])


def create_clean_voice():
    return speech_chain([], makeup_db=1.5)


def create_warm_low_voice():
    return speech_chain([
        PitchShift(semitones=-1.5),
        FormantShift(0.5, mix=0.55),
        LowShelfFilter(cutoff_frequency_hz=160, gain_db=2.0),
    ], makeup_db=1.5)


def create_deep_voice(semitones=-4.5):
    return speech_chain([
        PitchShift(semitones=semitones),
        FormantShift(-2.5, mix=0.85),
        Resonator(frequency=135, decay=0.40, mix=0.16),
        LowShelfFilter(cutoff_frequency_hz=150, gain_db=3.0),
        ParallelDistortion(drive_db=10, mix=0.14),
    ], makeup_db=2.0)


def create_monster_voice():
    return speech_chain([
        PitchShift(semitones=-7.0),
        FormantShift(-3.5, mix=0.9),
        ParallelDistortion(drive_db=16, mix=0.35),
        LowpassFilter(cutoff_frequency_hz=5200),
        DuckedReverb(room_size=0.45, damping=0.65, wet_level=0.16, predelay_ms=25.0, duck_amount=0.5),
    ], makeup_db=1.5)


def create_bright_voice():
    return speech_chain([
        PitchShift(semitones=1.5),
        FormantShift(-0.5, mix=0.5),
        PeakFilter(cutoff_frequency_hz=3000, gain_db=2.0),
        HighShelfFilter(cutoff_frequency_hz=8500, gain_db=2.5),
    ], makeup_db=1.5)


def create_chipmunk_voice(semitones=6.5):
    return speech_chain([
        PitchShift(semitones=semitones),
        FormantShift(4.0, mix=0.85),
        PeakFilter(cutoff_frequency_hz=2400, gain_db=2.0),
    ], makeup_db=1.5)


def create_robot_voice():
    return speech_chain([
        PitchShift(semitones=-2.0),
        RingModulation(frequency=140.0, mix=0.36),
        Resonator(frequency=260.0, decay=0.48, mix=0.22),
        Chorus(rate_hz=0.8, depth=0.20, feedback=0.05, mix=0.22),
        Bitcrush(bit_depth=10),
        LowpassFilter(cutoff_frequency_hz=7200),
    ], makeup_db=8.5)


def create_vocoder_voice():
    return speech_chain([
        Vocoder(carrier_hz=115.0, bands=16, mix=0.92),
        Chorus(rate_hz=0.6, depth=0.25, feedback=0.05, mix=0.25),
    ], makeup_db=4.5)


def create_radio_walkie_talkie():
    return speech_chain([CommunicationChannel(mode=2, drive=5, static=0, click=0)], makeup_db=2.0)


def create_telephone_voice():
    return speech_chain([CommunicationChannel(mode=1, drive=2)], makeup_db=2.0)


def create_astronaut_voice():
    return speech_chain([
        CommunicationChannel(mode=2, drive=3, static=0.06, click=0.15, mix=0.55, gate_db=-48),
        Resonator(frequency=320, decay=0.35, mix=0.14),
        Delay(delay_seconds=.065, feedback=.12, mix=.08),
    ], makeup_db=4.8)


def create_retro_8bit():
    return speech_chain([
        SampleRateReduce(target_rate=8500.0, mix=0.9),
        Bitcrush(bit_depth=7),
        LowpassFilter(cutoff_frequency_hz=4800),
    ], makeup_db=2.0)


def create_cathedral_voice():
    return speech_chain([
        DuckedReverb(room_size=0.82, damping=0.50, wet_level=0.30, predelay_ms=35.0, duck_amount=0.60),
    ], makeup_db=2.0)


def create_alien_voice():
    return speech_chain([
        PitchShift(semitones=2.5),
        FormantShift(-3.0, mix=0.80),
        Phaser(rate_hz=.8, depth=.55, centre_frequency_hz=1100, feedback=.25, mix=.32),
        ToneDelay(time_ms=95, feedback=.18, tone_hz=3500, mix=.14),
    ], makeup_db=4.5)


def create_broadcast_voice():
    return speech_chain([
        PeakFilter(cutoff_frequency_hz=280, gain_db=-2.5),
        LowShelfFilter(cutoff_frequency_hz=130, gain_db=2.0),
        PeakFilter(cutoff_frequency_hz=3200, gain_db=2.0),
        HighShelfFilter(cutoff_frequency_hz=9500, gain_db=2.0),
        ParallelDistortion(drive_db=6.0, mix=0.12),
    ], makeup_db=1.0)


def create_pa_stadium_voice():
    return speech_chain([
        HighpassFilter(cutoff_frequency_hz=320),
        LowpassFilter(cutoff_frequency_hz=4200),
        PeakFilter(cutoff_frequency_hz=1250, gain_db=5.0),
        ToneDelay(time_ms=145, feedback=0.18, tone_hz=2800, mix=0.22),
        DuckedReverb(room_size=0.70, damping=0.55, wet_level=0.22, predelay_ms=45.0, duck_amount=0.50),
    ], makeup_db=1.5)


def create_underwater_voice():
    return speech_chain([
        LowpassFilter(cutoff_frequency_hz=780),
        LowpassFilter(cutoff_frequency_hz=780),
        Phaser(rate_hz=0.35, depth=0.70, centre_frequency_hz=450, feedback=0.30, mix=0.45),
        Chorus(rate_hz=1.2, depth=0.45, feedback=0.1, mix=0.35),
    ], makeup_db=11.5)


def create_vintage_radio_voice():
    return speech_chain([
        HighpassFilter(cutoff_frequency_hz=320),
        LowpassFilter(cutoff_frequency_hz=3600),
        PeakFilter(cutoff_frequency_hz=1100, gain_db=4.0),
        ParallelDistortion(drive_db=14.0, mix=0.35),
    ], makeup_db=1.5)


def create_talkbox_voice():
    return speech_chain([
        EnvelopeTalkbox(sensitivity=0.075, q=3.8, mix=0.88),
        PeakFilter(cutoff_frequency_hz=1200, gain_db=2.0),
    ], makeup_db=2.5)


def create_whisper_voice():
    return speech_chain([
        Whisperizer(mix=0.92, seed=101),
        HighShelfFilter(cutoff_frequency_hz=3200, gain_db=2.0),
    ], makeup_db=4.0)


def create_shifter_voice():
    return speech_chain([
        FrequencyShifter(shift_hz=62.0, mix=0.78),
        HighpassFilter(cutoff_frequency_hz=110),
        PeakFilter(cutoff_frequency_hz=2600, gain_db=2.0),
    ], makeup_db=2.2)


def create_titan_voice():
    return speech_chain([
        SubharmonicTitan(sub_level=0.75, exciter_mix=0.22),
        PeakFilter(cutoff_frequency_hz=1900, gain_db=1.5),
    ], makeup_db=1.0)


def create_backmask_voice():
    return speech_chain([
        ReverseGranulator(grain_ms=85.0, mix=0.88),
        LowpassFilter(cutoff_frequency_hz=6800),
    ], makeup_db=4.5)


def create_shimmer_voice():
    return speech_chain([
        ShimmerReverb(room_size=0.86, damping=0.42, wet_level=0.35, shimmer_feedback=0.32, duck_amount=0.45),
        HighShelfFilter(cutoff_frequency_hz=6500, gain_db=1.5),
    ], makeup_db=1.5)


def create_cassette_voice():
    return speech_chain([
        TapeWowFlutter(wow_hz=0.85, wow_ms=4.2, flutter_hz=5.9, flutter_ms=0.45, drive=1.8, hiss_level=0.006, seed=202),
        HighpassFilter(cutoff_frequency_hz=160),
        LowShelfFilter(cutoff_frequency_hz=120, gain_db=3.0),
        LowpassFilter(cutoff_frequency_hz=4400),
    ], makeup_db=2.0)


EXTRA_DEFAULTS = dict(formant=0., formant_mix=1., warmth=0., presence=0., brightness=0.,
                      tone_mix=1., doubler_mix=0., ring_hz=70., ring_mix=0.)
EXTRA_LIMITS = dict(formant=(-6, 6), formant_mix=(0, 1), warmth=(-9, 9), presence=(-9, 9),
                    brightness=(-9, 9), tone_mix=(0, 1), doubler_mix=(0, 1), ring_hz=(20, 500), ring_mix=(0, 1))


EXTRA_DEFAULTS.update(harmony_enabled=1., harmony_pitch1=-7., harmony_level1=.35,
    harmony_pitch2=7., harmony_level2=.25, harmony_mix=0., resonator_enabled=1.,
    resonator_hz=180., resonator_decay=.55, resonator_mix=0., delay_enabled=1.,
    delay_ms=180., delay_feedback=.25, delay_tone=4000., delay_mix=0.,
    parallel_enabled=1., parallel_drive=12., parallel_mix=0.)
EXTRA_LIMITS.update(harmony_enabled=(0,1), harmony_pitch1=(-12,12), harmony_level1=(0,1),
    harmony_pitch2=(-12,12), harmony_level2=(0,1), harmony_mix=(0,1), resonator_enabled=(0,1),
    resonator_hz=(80,1600), resonator_decay=(0,.85), resonator_mix=(0,1), delay_enabled=(0,1),
    delay_ms=(20,800), delay_feedback=(0,.75), delay_tone=(500,10000), delay_mix=(0,1),
    parallel_enabled=(0,1), parallel_drive=(0,30), parallel_mix=(0,1))


EXTRA_DEFAULTS.update(comms_enabled=1.,comms_mode=0.,comms_drive=3.,comms_static=0.,comms_click=0.,comms_mix=1.,comms_gate=-44.)
EXTRA_LIMITS.update(comms_enabled=(0,1),comms_mode=(0,2),comms_drive=(0,18),comms_static=(0,1),comms_click=(0,1),comms_mix=(0,1),comms_gate=(-70,-30))


def _communication(params):
    return CommunicationChannel(int(params['comms_mode']),params['comms_drive'],params['comms_static'],params['comms_click'],params['comms_mix'],params['comms_gate'])


def create_custom_voice(pitch_semitones=0., reverb_amount=0., distortion_db=0., bitcrush_bits=16, base_voice=None, **extras):
    params = validate_params(pitch_semitones, distortion_db, reverb_amount, bitcrush_bits, base_voice=base_voice, **extras)
    effects = []
    if abs(params['pitch']) > .05:
        effects.append(PitchShift(semitones=params['pitch']))
    if abs(params['formant']) > .01 and params['formant_mix'] > 0:
        effects.append(FormantShift(params['formant'], params['formant_mix']))
    for key, effect, frequency in (('warmth', LowShelfFilter, 200), ('presence', PeakFilter, 2500),
                                    ('brightness', HighShelfFilter, 5000)):
        gain = params[key] * params['tone_mix']
        if abs(gain) > .01:
            effects.append(effect(cutoff_frequency_hz=frequency, gain_db=gain))
    if params['doubler_mix'] > 0:
        effects.append(Chorus(rate_hz=.45, depth=.15, centre_delay_ms=18, feedback=0,
                              mix=params['doubler_mix']))
    if params['ring_mix'] > 0:
        effects.append(RingModulation(params['ring_hz'], params['ring_mix']))
    if params['distortion'] > .5:
        effects.extend([Distortion(drive_db=params['distortion']),
                        Gain(gain_db=-min(15.0, params['distortion'] * .65))])
    if params['bitcrush'] < 16:
        effects.append(Bitcrush(bit_depth=params['bitcrush']))
    if params['comms_enabled'] and params['comms_mode'] and params['comms_mix']:
        effects.append(_communication(params))
    if params['parallel_enabled'] and params['parallel_mix'] > 0:
        effects.append(ParallelDistortion(params['parallel_drive'], params['parallel_mix']))
    if params['harmony_enabled'] and params['harmony_mix'] > 0 and (params['harmony_level1'] + params['harmony_level2']) > 0:
        has_shift = abs(params['harmony_pitch1']) > 0.01 or abs(params['harmony_pitch2']) > 0.01
        effects.append(Harmony(params['harmony_pitch1'], params['harmony_level1'],
                               params['harmony_pitch2'], params['harmony_level2'],
                               params['harmony_mix'], width=0.65 if has_shift else 0.0))
    if params['resonator_enabled'] and params['resonator_mix'] > 0:
        effects.append(Resonator(params['resonator_hz'],params['resonator_decay'],params['resonator_mix']))
    if params['delay_enabled'] and params['delay_mix'] > 0:
        effects.append(ToneDelay(params['delay_ms'],params['delay_feedback'],params['delay_tone'],params['delay_mix']))
    if params['reverb'] > .01:
        effects.append(Reverb(room_size=.25 + params['reverb'] * .55,
                              damping=.6, wet_level=params['reverb'] * .3, dry_level=.95))
    if base_voice and 'params' in VOICE_PRESETS[base_voice]:
        return speech_chain(effects)
    if base_voice:
        base = VOICE_PRESETS[base_voice]['builder']()
        defaults = builtin_editor_params(base_voice)
        replacements = {NativePitchShift: ('pitch', 'semitones'), Distortion: ('distortion', 'drive_db'),
                        Bitcrush: ('bitcrush', 'bit_depth'), Reverb: ('reverb', 'wet_level')}
        retained = []
        handled = set()
        for effect in base.effects:
            if isinstance(effect,CommunicationChannel):
                handled.add('comms')
                if params['comms_enabled'] and params['comms_mode'] and params['comms_mix']:
                    retained.append(_communication(params))
                continue
            for kind, (key, attribute) in replacements.items():
                if isinstance(effect, kind):
                    handled.add(key)
                    if abs(params[key]-defaults[key]) > 1e-6:
                        setattr(effect, attribute, params[key]*.3 if key == 'reverb' else params[key])
                    break
            retained.append(effect)
        # Existing modules are edited in place; unexposed filters stay intact.
        additions = []
        for effect in effects:
            if isinstance(effect,CommunicationChannel) and 'comms' in handled:
                continue
            key = next((key for kind, (key, _) in replacements.items() if isinstance(effect, kind)), None)
            if key in handled:
                continue
            if isinstance(effect, Gain) and 'distortion' in handled:
                continue
            additions.append(effect)
        return Pedalboard([*retained, *additions])
    return speech_chain(effects)


def builtin_editor_params(name):
    if 'params' in VOICE_PRESETS[name]:
        return dict(VOICE_PRESETS[name]['params'])
    params = dict(pitch=0., distortion=0., reverb=0., bitcrush=16, **EXTRA_DEFAULTS)
    for effect in VOICE_PRESETS[name]['builder']().effects:
        if isinstance(effect,CommunicationChannel):
            params.update(comms_mode=effect.mode,comms_drive=effect.drive,comms_static=effect.static,
                          comms_click=effect.click,comms_mix=effect.mix,comms_gate=effect.gate_db)
        elif isinstance(effect, NativePitchShift):
            params['pitch'] = round(effect.semitones*2)/2
        elif isinstance(effect, Distortion):
            params['distortion'] = round(effect.drive_db)
        elif isinstance(effect, Bitcrush):
            params['bitcrush'] = int(effect.bit_depth)
        elif isinstance(effect, Reverb):
            params['reverb'] = min(1., round(effect.wet_level/.3/.05)*.05)
    params['base_voice'] = name
    return params


# Registry of predefined voices available in the application
VOICE_PRESETS = {
    "Broadcast": {
        "description": "Studio podcaster polish: de-mud, warmth, air & gentle saturation",
        "builder": create_broadcast_voice, "category": "Natural"
    },
    "Warm Low": {
        "description": "Subtle natural lower voice with preserved vocal clarity",
        "builder": create_warm_low_voice, "category": "Natural"
    },
    "Bright": {
        "description": "Crisp, airy vocal lift with full high-end presence",
        "builder": create_bright_voice, "category": "Natural"
    },
    "Clean (Normal)": {
        "description": "Original microphone voice with clean leveling",
        "builder": create_clean_voice,
        "category": "Basic"
    },
    "Deep (Vader)": {
        "description": "Dark masked villain: deep pitch, darkened formant & mask resonance",
        "builder": lambda: create_deep_voice(-4.5),
        "category": "Characters"
    },
    "Monster / Demon": {
        "description": "Deep sub-pitch with oversampled grit and ducked dark ambience",
        "builder": create_monster_voice,
        "category": "Characters"
    },
    "Chipmunk": {
        "description": "High-pitched cartoon voice with upward formant shaping",
        "builder": lambda: create_chipmunk_voice(6.5),
        "category": "Characters"
    },
    "Cyborg Robot": {
        "description": "Metallic android voice with ring mod, resonator & bitcrush",
        "builder": create_robot_voice,
        "category": "Sci-Fi"
    },
    "Synth Vocoder": {
        "description": "16-band harmonic synth vocoder with crisp consonant air",
        "builder": create_vocoder_voice,
        "category": "Sci-Fi"
    },
    "Walkie-Talkie": {
        "description": "Compressed radio channel with speech-triggered squelch",
        "builder": create_radio_walkie_talkie,
        "category": "Filters"
    },
    "Telephone": {
        "description": "Handset resonance, narrow bandwidth and controlled saturation",
        "builder": create_telephone_voice,
        "category": "Filters"
    },
    "PA Stadium": {
        "description": "Arena horn megaphone with slapback echo and crowd-hall decay",
        "builder": create_pa_stadium_voice,
        "category": "Filters"
    },
    "Vintage Radio": {
        "description": "1940s tube broadcast with midrange horn focus & warm drive",
        "builder": create_vintage_radio_voice,
        "category": "Filters"
    },
    "Astronaut": {
        "description": "Helmet comms with radio squelch, cavity resonance & subtle echo",
        "builder": create_astronaut_voice,
        "category": "Sci-Fi"
    },
    "8-Bit Arcade": {
        "description": "Retro console crunch with 8.5 kHz sample-hold & 7-bit depth",
        "builder": create_retro_8bit,
        "category": "Sci-Fi"
    },
    "Cathedral Echo": {
        "description": "Spacious pre-delayed hall that ducks under active speech",
        "builder": create_cathedral_voice,
        "category": "Atmosphere"
    },
    "Underwater": {
        "description": "Submerged resonant low-pass with liquid phaser & chorus sweep",
        "builder": create_underwater_voice,
        "category": "Atmosphere"
    },
    "Alien": {
        "description": "Otherworldly split pitch/formant warp with phaser movement",
        "builder": create_alien_voice,
        "category": "Sci-Fi"
    },
    "Envelope Talkbox": {
        "description": "Speech-reactive dual vowel filter sweep triggered by syllable loudness",
        "builder": create_talkbox_voice,
        "category": "Filters"
    },
    "Shadow Whisper": {
        "description": "Pitchless spectral-noise whisper preserving articulation without vocal cords",
        "builder": create_whisper_voice,
        "category": "Atmosphere"
    },
    "Cyber Shifter": {
        "description": "Analytic single-sideband frequency shift (+62 Hz linear inharmonic warp)",
        "builder": create_shifter_voice,
        "category": "Sci-Fi"
    },
    "Sub-Bass Titan": {
        "description": "Zero-latency f0/2 subharmonic octave generator paired with crisp air exciter",
        "builder": create_titan_voice,
        "category": "Characters"
    },
    "Backmask": {
        "description": "Overlapping 85 ms reversed grains for surreal backwards-syllable speech",
        "builder": create_backmask_voice,
        "category": "Atmosphere"
    },
    "Celestial Shimmer": {
        "description": "Granular +12 st octave-up feedback reverb cloud under clean lead speech",
        "builder": create_shimmer_voice,
        "category": "Atmosphere"
    },
    "Broken Cassette": {
        "description": "Dual-LFO fractional-delay tape wow & flutter with asymmetric hysteresis",
        "builder": create_cassette_voice,
        "category": "Filters"
    }
}



def _register_character(name,description,**settings):
    params=validate_params(settings.pop('pitch',0),settings.pop('distortion',0),
                           settings.pop('reverb',0),settings.pop('bitcrush',16),**settings)
    VOICE_PRESETS[name]={'description':description,'category':'Characters','params':params,
        'builder':lambda params=params:create_custom_voice(params['pitch'],params['reverb'],params['distortion'],
                     params['bitcrush'],**{k:params[k] for k in EXTRA_DEFAULTS})}


def validate_params(pitch, distortion, reverb, bitcrush, base_voice=None, **extras):
    values = (float(pitch), float(distortion), float(reverb), float(bitcrush))
    for value, low, high, label in zip(values, (-12, 0, 0, 4), (12, 25, 1, 16),
                                        ("Pitch", "Distortion", "Reverb", "Bit depth")):
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{label} must be between {low} and {high}.")
    if not values[3].is_integer():
        raise ValueError("Bit depth must be a whole number.")
    result = dict(zip(("pitch", "distortion", "reverb", "bitcrush"), (*values[:3], int(values[3]))))
    unknown = set(extras) - set(EXTRA_DEFAULTS)
    if unknown:
        raise ValueError(f"Unknown voice settings: {', '.join(sorted(unknown))}")
    for key, default in EXTRA_DEFAULTS.items():
        value = float(extras.get(key, default))
        low, high = EXTRA_LIMITS[key]
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}.")
        if key.endswith('_enabled') and value not in (0.,1.):
            raise ValueError(f'{key} must be on or off.')
        if key == 'comms_mode' and not value.is_integer():
            raise ValueError('Channel type must be Off, Telephone or Radio.')
        result[key] = value
    if base_voice is not None and (not isinstance(base_voice, str) or base_voice not in VOICE_PRESETS):
        raise ValueError('The original built-in voice is unavailable.')
    result['base_voice'] = base_voice
    return result



_register_character('Space Marine','Heavy armored voice with metallic helmet resonance',
    pitch=-3,formant=-2,warmth=2,presence=2,parallel_drive=15,parallel_mix=.2,
    resonator_hz=180,resonator_decay=.55,resonator_mix=.2,delay_ms=45,delay_feedback=.1,delay_tone=3200,delay_mix=.08)
_register_character('Ghost','Ethereal layered voice with dark trailing echoes',
    formant=2,reverb=.55,harmony_pitch1=7,harmony_level1=.3,harmony_pitch2=12,harmony_level2=.18,
    harmony_mix=.3,delay_ms=260,delay_feedback=.35,delay_tone=2500,delay_mix=.2,brightness=-2)
_register_character('Goblin','Small nasal character with a restrained raspy edge',
    pitch=2.5,formant=3,presence=4,warmth=-3,parallel_drive=12,parallel_mix=.15)
_register_character('Hive Mind','A lead voice surrounded by two pitched companions',
    harmony_pitch1=-7,harmony_level1=.55,harmony_pitch2=7,harmony_level2=.45,
    harmony_mix=.65,doubler_mix=.12,reverb=.2)


_register_character('Kid (DSP prototype)','Youthful pitch/resonance experiment; realism not validated',
    pitch=3.5,formant=2.5,warmth=-3,presence=1,brightness=1)


def _read_presets():
    if not os.path.exists(CUSTOM_PRESETS_FILE):
        return {}
    with open(CUSTOM_PRESETS_FILE, encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, dict):
        raise ValueError("Preset file must contain a JSON object.")
    return data


def _write_presets(data):
    directory = os.path.dirname(os.path.abspath(CUSTOM_PRESETS_FILE))
    fd, temporary = tempfile.mkstemp(prefix=".voices-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(data, target, indent=2, allow_nan=False)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, CUSTOM_PRESETS_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_user_presets():
    """Load valid entries independently so one bad voice cannot hide the rest."""
    try:
        data = _read_presets()
    except (OSError, ValueError):
        return {}
    presets = {}
    for name, params in data.items():
        try:
            if not name.strip() or name in VOICE_PRESETS:
                continue
            if isinstance(params,dict) and 'comms_mode' not in params and params.get('base_voice') in ('Telephone','Walkie-Talkie'):
                inherited=builtin_editor_params(params['base_voice'])
                params={**params,**{key:inherited[key] for key in EXTRA_DEFAULTS if key.startswith('comms_')}}
            params = validate_params(params.get("pitch", 0), params.get("distortion", 0),
                                     params.get("reverb", 0), params.get("bitcrush", 16), base_voice=params.get('base_voice'),
                                     **{k: params[k] for k in EXTRA_DEFAULTS if k in params})
            p, d, r, b = (params[k] for k in ("pitch", "distortion", "reverb", "bitcrush"))
            presets[name] = {
                "description": f"Custom (Pitch {p:+.1f}, Dist {d}dB, Rev {int(r*100)}%)",
                "builder": lambda params=params: create_custom_voice(params['pitch'], params['reverb'],
                    params['distortion'], params['bitcrush'], base_voice=params.get('base_voice'), **{k: params[k] for k in EXTRA_DEFAULTS}),
                "params": params, "category": "Custom"
            }
        except (TypeError, ValueError, AttributeError):
            continue
    return presets


def save_user_preset(name, pitch, distortion, reverb, bitcrush=16, base_voice=None, **extras):
    name = name.strip()
    if not name or len(name) > 80 or name in VOICE_PRESETS:
        raise ValueError("Use a unique voice name of 1 to 80 characters, different from built-in voices.")
    params = validate_params(pitch, distortion, reverb, bitcrush, base_voice=base_voice, **extras)
    current = _read_presets()
    current[name] = params
    _write_presets(current)


def delete_user_preset(name):
    current = _read_presets()
    current.pop(name, None)
    _write_presets(current)


PRESET_BUNDLE_FORMAT = "voice-studio-preset"


def _write_json_file(dest_path, payload):
    directory = os.path.dirname(os.path.abspath(dest_path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".export-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(payload, target, indent=2, allow_nan=False)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, dest_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _exportable_params(name, custom_params=None):
    if custom_params is not None:
        p = custom_params
        return validate_params(p.get("pitch", 0), p.get("distortion", 0), p.get("reverb", 0),
                               p.get("bitcrush", 16), base_voice=p.get("base_voice"),
                               **{k: p[k] for k in EXTRA_DEFAULTS if k in p})
    user = _read_presets()
    if name in user:
        p = user[name]
        return validate_params(p.get("pitch", 0), p.get("distortion", 0), p.get("reverb", 0),
                               p.get("bitcrush", 16), base_voice=p.get("base_voice"),
                               **{k: p[k] for k in EXTRA_DEFAULTS if k in p})
    if name in VOICE_PRESETS:
        return builtin_editor_params(name)
    raise ValueError(f"Voice '{name}' was not found to export.")


def export_voice_preset(name, dest_path, custom_params=None):
    """Export one voice preset (built-in, saved custom, or current editor state) to a shareable JSON/.vmvoice file."""
    clean_name = (name or "").strip() or "Custom voice"
    params = _exportable_params(clean_name, custom_params=custom_params)
    payload = {"format": PRESET_BUNDLE_FORMAT, "version": 1, "voices": {clean_name: params}}
    _write_json_file(dest_path, payload)
    return dest_path


def export_voice_pack(dest_path, names=None):
    """Export multiple saved custom voices into one shareable voice pack file."""
    user = _read_presets()
    selected = list(user.keys()) if names is None else [n for n in names if n in user]
    if not selected:
        raise ValueError("No saved custom voices available to export.")
    voices_payload = {n: _exportable_params(n) for n in selected}
    payload = {"format": PRESET_BUNDLE_FORMAT, "version": 1, "voices": voices_payload}
    _write_json_file(dest_path, payload)
    return list(voices_payload.keys())


def _unique_import_name(raw_name, current, conflict="rename"):
    base = (raw_name or "").strip()[:80]
    if not base:
        raise ValueError("Preset entry is missing a valid name.")
    candidate = base
    if candidate in VOICE_PRESETS:
        candidate = f"{base[:69]} (Imported)"
    if conflict == "overwrite" and candidate not in VOICE_PRESETS:
        return candidate
    index = 2
    final = candidate
    while final in current or final in VOICE_PRESETS:
        suffix = f" ({index})"
        final = f"{candidate[:80 - len(suffix)]}{suffix}"
        index += 1
    return final


def import_voice_presets(src_path, conflict="rename"):
    """Import a shared .vmvoice/.json preset or pack into user custom presets."""
    with open(src_path, encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, dict):
        raise ValueError("Shared preset file must contain a JSON object.")
    entries = data["voices"] if data.get("format") == PRESET_BUNDLE_FORMAT and isinstance(data.get("voices"), dict) else data
    if not entries:
        raise ValueError("No voices found in preset file.")

    current = _read_presets()
    imported = []
    for raw_name, params in entries.items():
        if not isinstance(params, dict):
            raise ValueError(f"Invalid preset settings for '{raw_name}'.")
        base_voice = params.get("base_voice")
        if base_voice is not None and base_voice not in VOICE_PRESETS:
            base_voice = None
        validated = validate_params(
            params.get("pitch", 0), params.get("distortion", 0),
            params.get("reverb", 0), params.get("bitcrush", 16),
            base_voice=base_voice,
            **{k: params[k] for k in EXTRA_DEFAULTS if k in params}
        )
        target_name = _unique_import_name(raw_name, current, conflict=conflict)
        current[target_name] = validated
        imported.append(target_name)
    _write_presets(current)
    return imported
