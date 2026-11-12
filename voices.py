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
from voice_effects import FormantShift, RingModulation


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


def create_custom_voice(pitch_semitones=0., reverb_amount=0., distortion_db=0., bitcrush_bits=16, **extras):
    params = validate_params(pitch_semitones, distortion_db, reverb_amount, bitcrush_bits, **extras)
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
    if params['reverb'] > .01:
        effects.append(Reverb(room_size=.25 + params['reverb'] * .55,
                              damping=.6, wet_level=params['reverb'] * .3, dry_level=.95))
    return speech_chain(effects)


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


def validate_params(pitch, distortion, reverb, bitcrush, **extras):
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
        result[key] = value
    return result


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
                                     params.get("reverb", 0), params.get("bitcrush", 16),
                                     **{k: params[k] for k in EXTRA_DEFAULTS if k in params})
            p, d, r, b = (params[k] for k in ("pitch", "distortion", "reverb", "bitcrush"))
            presets[name] = {
                "description": f"Custom (Pitch {p:+.1f}, Dist {d}dB, Rev {int(r*100)}%)",
                "builder": lambda params=params: create_custom_voice(params['pitch'], params['reverb'],
                    params['distortion'], params['bitcrush'], **{k: params[k] for k in EXTRA_DEFAULTS}),
                "params": params, "category": "Custom"
            }
        except (TypeError, ValueError, AttributeError):
            continue
    return presets


def save_user_preset(name, pitch, distortion, reverb, bitcrush=16, **extras):
    name = name.strip()
    if not name or len(name) > 80 or name in VOICE_PRESETS:
        raise ValueError("Use a unique voice name of 1 to 80 characters, different from built-in voices.")
    params = validate_params(pitch, distortion, reverb, bitcrush, **extras)
    current = _read_presets()
    current[name] = params
    _write_presets(current)


def delete_user_preset(name):
    current = _read_presets()
    current.pop(name, None)
    _write_presets(current)
