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
from voice_effects import FormantShift, RingModulation, Harmony, Resonator, ToneDelay, ParallelDistortion


def Pedalboard(effects):
    return VoiceChain(effects, NativePedalboard, NativePitchShift)


PitchShift = NativePitchShift

CUSTOM_PRESETS_FILE = os.path.join(os.path.dirname(__file__), "custom_presets.json")


def speech_chain(effects):
    # Remove rumble before transformation, then gently level the result.
    return Pedalboard([
        HighpassFilter(cutoff_frequency_hz=70),
        *effects,
        Compressor(threshold_db=-22, ratio=2.0, attack_ms=10, release_ms=120),
        Gain(gain_db=2),
    ])


def create_clean_voice():
    return speech_chain([])


def create_deep_voice(semitones=-3.5):
    return speech_chain([
        PitchShift(semitones=semitones),
        PeakFilter(cutoff_frequency_hz=160, gain_db=2),
        PeakFilter(cutoff_frequency_hz=2800, gain_db=1.5),
    ])


def create_monster_voice():
    return speech_chain([
        PitchShift(semitones=-6),
        Distortion(drive_db=3),
        Gain(gain_db=-3),
        LowpassFilter(cutoff_frequency_hz=6500),
    ])


def create_chipmunk_voice(semitones=5):
    return speech_chain([PitchShift(semitones=semitones),
                         LowpassFilter(cutoff_frequency_hz=8500)])


def create_robot_voice():
    return speech_chain([
        PitchShift(semitones=-1.5),
        Chorus(rate_hz=7, depth=.35, feedback=.05, mix=.25),
        Bitcrush(bit_depth=12),
        LowpassFilter(cutoff_frequency_hz=7500),
    ])


def create_radio_walkie_talkie():
    return speech_chain([
        HighpassFilter(cutoff_frequency_hz=320),
        LowpassFilter(cutoff_frequency_hz=3800),
        Distortion(drive_db=2), Gain(gain_db=-2),
        PeakFilter(cutoff_frequency_hz=1800, gain_db=2),
    ])


def create_telephone_voice():
    return speech_chain([
        HighpassFilter(cutoff_frequency_hz=300),
        LowpassFilter(cutoff_frequency_hz=3400),
        PeakFilter(cutoff_frequency_hz=1600, gain_db=2),
    ])


def create_astronaut_voice():
    return speech_chain([
        HighpassFilter(cutoff_frequency_hz=250),
        LowpassFilter(cutoff_frequency_hz=4800),
        Delay(delay_seconds=.075, feedback=.12, mix=.08),
        Reverb(room_size=.3, damping=.65, wet_level=.08, dry_level=.95),
    ])


def create_retro_8bit():
    return speech_chain([Bitcrush(bit_depth=9),
                         LowpassFilter(cutoff_frequency_hz=5500)])


def create_cathedral_voice():
    return speech_chain([
        Reverb(room_size=.78, damping=.6, wet_level=.18, dry_level=.95),
    ])


def create_alien_voice():
    return speech_chain([
        PitchShift(semitones=3),
        Phaser(rate_hz=.45, depth=.35, centre_frequency_hz=1100,
               feedback=.1, mix=.18),
        Delay(delay_seconds=.09, feedback=.1, mix=.07),
    ])


def create_broadcast_voice():
    return speech_chain([
        PeakFilter(cutoff_frequency_hz=150, gain_db=2),
        PeakFilter(cutoff_frequency_hz=3200, gain_db=2),
    ])


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
                        Gain(gain_db=-min(12, params['distortion'] * .5))])
    if params['bitcrush'] < 16:
        effects.append(Bitcrush(bit_depth=params['bitcrush']))
    if params['parallel_enabled'] and params['parallel_mix'] > 0:
        effects.append(ParallelDistortion(params['parallel_drive'],params['parallel_mix']))
    if params['harmony_enabled'] and params['harmony_mix'] > 0 and (params['harmony_level1']+params['harmony_level2']) > 0:
        effects.append(Harmony(params['harmony_pitch1'],params['harmony_level1'],
                               params['harmony_pitch2'],params['harmony_level2'],params['harmony_mix']))
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
        if isinstance(effect, NativePitchShift):
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
        "description": "Warm, clear announcer EQ without pitch shifting",
        "builder": create_broadcast_voice, "category": "Natural"
    },
    "Warm Low": {
        "description": "Subtle lower voice, minus 2 semitones",
        "builder": lambda: create_deep_voice(-2), "category": "Natural"
    },
    "Bright": {
        "description": "Subtle brighter voice, plus 2 semitones",
        "builder": lambda: create_chipmunk_voice(2), "category": "Natural"
    },
    "Clean (Normal)": {
        "description": "Original microphone voice with clean leveling",
        "builder": create_clean_voice,
        "category": "Basic"
    },
    "Deep (Vader)": {
        "description": "Deep cinematic pitch shift with bass boost",
        "builder": lambda: create_deep_voice(-3.5),
        "category": "Characters"
    },
    "Monster / Demon": {
        "description": "Terrifying sub-pitch with distortion and presence",
        "builder": create_monster_voice,
        "category": "Characters"
    },
    "Chipmunk": {
        "description": "High-pitched cartoon / chipmunk voice",
        "builder": lambda: create_chipmunk_voice(5.0),
        "category": "Characters"
    },
    "Cyborg Robot": {
        "description": "Mechanical metallic modulation with bitcrush",
        "builder": create_robot_voice,
        "category": "Sci-Fi"
    },
    "Walkie-Talkie": {
        "description": "Analog two-way radio with bandpass filter & crunch",
        "builder": create_radio_walkie_talkie,
        "category": "Filters"
    },
    "Telephone": {
        "description": "Clear narrow-band telephone voice",
        "builder": create_telephone_voice,
        "category": "Filters"
    },
    "Astronaut": {
        "description": "Helmet intercom with delay and space reverb",
        "builder": create_astronaut_voice,
        "category": "Sci-Fi"
    },
    "8-Bit Arcade": {
        "description": "Gentle retro digital character with 9-bit depth",
        "builder": create_retro_8bit,
        "category": "Sci-Fi"
    },
    "Cathedral Echo": {
        "description": "Spacious hall with clear foreground speech",
        "builder": create_cathedral_voice,
        "category": "Atmosphere"
    },
    "Alien": {
        "description": "Extraterrestrial voice with phase modulation",
        "builder": create_alien_voice,
        "category": "Sci-Fi"
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
