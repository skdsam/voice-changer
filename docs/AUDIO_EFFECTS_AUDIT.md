# Audio effects audit and voice quality plan

Audit date: 12 November 2026. Scope: the full 19-preset library, exposed effect controls, built-in editing, live output and local A/B testing. Automated results are in [AUTOMATED_AUDIT.md](AUTOMATED_AUDIT.md) and [audio-audit.json](audio-audit.json).

## What the measurements establish

140 combinations covered mono/stereo at 44.1/48 kHz: 19 presets and 16 individual/stacked stress chains. Input included low/normal/loud harmonic speech-like sections, broadband consonant-like noise, pauses and trailing silence. This run reported zero processing failures, zero sanitized non-finite samples, zero hard-clipped output samples and zero native pitch-buffer underruns. Every measured 99th-percentile callback duration was below its block budget on this machine.

These are stability and signal checks, not perceptual quality scores. They do not establish realistic speaker identity, intelligibility on actual speech, hardware round-trip latency or performance while gaming. Matching a synthetic vowel is not proof that a child voice sounds real.

## Findings and changes made

1. **Telephone lacked a handset character.** Replaced the shallow EQ-only path with cascaded band edges, midrange handset resonance, speech compression and controlled saturation. A test confirms strong rejection of low rumble and high treble relative to the speech band.
2. **Walkie-talkie lacked radio behavior.** Added a dedicated, more compressed radio channel with distinct bandwidth, hysteretic squelch, a 160 ms release hold and short gain ramps. Static and end clicks are optional, off by default, and occur around speech rather than continuous room noise. The gate threshold is adjustable for different microphones.
3. **Resonator lost too much level at high decay.** Replaced linear feedback attenuation with energy-based normalization. This makes strong resonance more usable; tonal buildup is still possible and the master limiter remains necessary.
4. **Listening comparisons were inconsistent.** Added Test voice: bounded local recording, same-sample preset auditioning, explicit original/processed playback, algorithmic latency trimming and active-speech RMS matching with peak protection. Export is explicit; closing the window clears sample references. Main live output is paused and blocked from restarting until the test closes.
5. **Signal sanitizing could hide instability in audit results.** Added an invalid-sample counter before sanitizing and included it in the audit. The final run required no sanitizing.
6. **Old communications variations needed migration.** Saved Telephone/Walkie-Talkie variations without the new communication settings inherit their channel type instead of silently losing the effect. Explicit new bypass settings remain respected.

## Effect-by-effect review

| Effect | Useful starting range | Current strengths | Limits / next improvement |
|---|---|---|---|
| Native pitch | +/-2 to 5 semitones | Stable streaming, measured pitch accuracy | 120 ms reservoir; extreme shifts are synthetic. Evaluate a formant-preserving backend for natural voices. |
| Formant | +/-1 to 3 semitones, moderate blend | Changes envelope while retaining harmonic frequencies in synthetic tests | Cepstral approximation; can color consonants and strong shifts. Not a learned voice model. Adds 1024 frames. |
| Warmth/presence/brightness EQ | +/-1 to 4 dB | Independent tonal controls and neutral defaults | Broad shelves/peak, no dedicated de-esser or nasal-band control yet. |
| Compression / master limiter | Gentle ratio, avoid clipped input | Speech leveling and bounded final output | Limiter can change level, so use matched A/B. Cannot repair a clipped microphone. |
| Serial distortion | Low drive for speech | Distinct grit | Strong drive can obscure consonants; aliasing has not been perceptually assessed. Prefer parallel distortion for clarity. |
| Parallel distortion | 10-30% blend | Clean lead remains audible with rough texture | Strong full-wet settings change level; oversampled waveshaping is a future improvement. |
| Bit depth | 9-12 bits | Clear digital character | 4-6 bits can erase quiet detail. Extremes are creative degradation, not an everyday voice. |
| Doubler / chorus | 10-35% blend | Thickens voices | Deliberate extra voice; high blends sound doubled. This is different from the fixed routing bug. |
| Ring modulation | 40-150 Hz, 10-40% blend | Metallic and robotic coloration | High rates/full wet reduce naturalness. Sidebands are verified, subjective harshness still needs listening. |
| Harmony | Modest layer levels and blend | Two pitch layers; lead aligned to their buffering | Adds 120 ms on top of upstream effects; deliberately multi-voiced, no stereo placement controls yet. |
| Resonator | 120-500 Hz, 10-35% blend | Tunable helmet/metal character, better high-decay level | Feedback capped at 85%; full wet is intentionally hollow. |
| Delay | 40-250 ms, 5-25% blend | Clear echo controls and stable tails | Tone filters the wet output, not each feedback pass. Long feedback tails exceed the comparison tool's two-second tail. |
| Reverb | Subtle space for speech | Useful atmosphere | Long/wet rooms smear speech. Compare consonants, not just vowels. |
| Phaser | Preset-tuned subtle blend | Alien movement | Present in Alien, not yet a full editable phaser section. |
| Telephone | Full channel blend, low drive | Now has stronger bandwidth shaping and handset character | DSP handset simulation, not an actual telephony codec. Needs Stealth speech listening signoff. |
| Radio | Full channel blend, adjust gate to room | Compression, squelch, optional speech-triggered texture | A high threshold can clip quiet words; static/clicks are decoration, not essential speech. |
| Headphone resampler | Automatic | Independent device rates and continuous timing | Linear interpolation is for monitoring; application output is unchanged. Higher-quality resampling is a future option. |

## Repeatable listening acceptance

Use Test voice to capture the same eight-second phrase, then reuse it across voices. Include normal words, quiet words, a loud phrase, sibilants, plosives and a sustained vowel. Suggested phrase: "Please check these six small boxes. Peter packed a bright blue bag. One, two, three. Ah, ee, oo."

For each preset, review:

- Words remain understandable at matched levels.
- The character remains stable across vowels, consonants and loud/quiet passages.
- No unintended original-mic overlay, no broken syllables and no unexplained silence.
- No excessive harshness, pumping, ringing or room-noise amplification.
- The intended effect is distinct from neighboring presets.
- Hardware latency and a longer live session are acceptable on the Stealth headset.

The automated suite covers all built-ins and exact recall before edits. Human listening signoff remains pending; no preset is declared universally excellent based on the synthetic audit.

## Strong-effect development priorities

**Delivered:** stronger communications channels, configurable radio texture, high-decay resonator gain fix, matched comparison workflow, full parameter/stability audit, and a clearly labeled youthful DSP experiment.

**Next quality priorities:** input gain/noise-floor calibration; a de-esser and narrower resonance EQ; oversampled saturation; editable modulation controls; stereo layer placement; and longer-duration game-load testing. Keep effect defaults conservative, retain explicit blend/bypass and preserve the original voice when saving variants.

**Next realism milestone:** evaluate a neural conversion worker with a suitable voice model. Do not label the DSP kid prototype realistic. See [CHILD_VOICE_EVALUATION.md](CHILD_VOICE_EVALUATION.md).
