# Voice Studio

A focused Windows microphone voice changer with 14 effect presets and saved custom voices.

## Run

```powershell
python -m pip install -r requirements.txt
python app.py
```

Select your microphone, a virtual cable as App output, and your headphones as Monitor. Choose a voice, then start. Hear myself independently enables headphone monitoring; untick it while leaving the processed App output running.

Adjust pitch, distortion, reverb and bit depth, then use Save Current Settings as New Preset. Saved voices appear in the voice list and are stored in custom_presets.json. Names must differ from built-in names. Existing custom names are replaced when saved again. Invalid settings are rejected and saves use atomic replacement. Back up this JSON file to transfer voices.

## Use in Discord or games

A separate working virtual audio cable is required. Select its playback endpoint as this app's output and its paired recording endpoint as the game's microphone. Endpoint names may differ (for VB-Cable, typically CABLE Input is playback and CABLE Output is recording). The app does not install a driver or create a virtual microphone. No suitable cable endpoint was exposed in the device inventory during this session. A Voicemod executable alone does not establish that its driver is usable by this app.

## Sound and latency

Pitch processing now uses the native SoundTouch 2.3.3 library instead of the original two-tap delay effect. Pitch voices use a 120 ms output reservoir to absorb the library's burst output without inserting gaps. Device latency is additional; actual end-to-end latency has not been measured. Non-pitch voices do not use this reservoir.

Start with Broadcast (no pitch transformation), Warm Low (-2 semitones) or Bright (+2 semitones) for everyday use. Character presets have reduced distortion, modulation and echo to retain speech clarity. Extreme custom settings remain intentionally capable of heavy effects. Existing custom preset parameter values are preserved, but their output changes with the upgraded engine and gain staging.

SoundTouch handles pitch; an optional separate spectral-envelope effect now provides approximate independent formant shifting. These are DSP voices, not AI speaker models, and natural identity replacement is not implemented. Subjective quality still depends on the microphone and source voice.

Effect state persists between callbacks. A final limiter and finite-value check protect output. Processing errors appear in the status line. Soundboard controls are omitted from the UI to keep it focused on voices.

For more natural identity transformations, an independently evaluated formant-preserving or neural conversion backend is a future addition. No AI model loading or training is implemented.

## Validation

```powershell
python -m unittest -v test_presets
```

Tests cover all 14 built-in voices over continuous 512-sample blocks at 44.1/48 kHz, non-silent finite bounded output, native pitch accuracy over ?12 semitones, stereo agreement, buffer underruns, effect order, reverb tails, and custom preset persistence/validation. They do not establish subjective quality, real hardware latency, or stability over long sessions. Listen with your microphone before relying on any preset.

## REA investigation

Used the CLI distributed by https://github.com/morluto/rea against the locally installed C:\Program Files\Voicemod V3\Voicemod.exe. The CLI reported version 4.0.1. Artifact inspection identified a PE file and recorded its SHA-256. Evidence is in analysis/voicemod-artifact.json. Deeper native analysis failed because no supported provider was configured; diagnostics are in analysis/voicemod-analysis.json. No conclusions about Voicemod's internal audio algorithms or models can be drawn from that inspection.

## Listening previews

The previews directory contains the same Windows synthesized speech passed through each preset. These are comparison artifacts, not recordings of your microphone. Start with Broadcast.wav, Warm_Low.wav, Bright.wav and Deep_Vader.wav.

To compare on your own recorded speech:

```powershell
python render_previews.py my-speech.wav --output my-previews
```

The renderer runs the same callback and limiter used for live output. A two-second silence tail is added for buffered speech and ambience.

## Native dependency

Windows x64 Python is required for the bundled SoundTouch DLL. Keep vendor/soundtouch alongside the Python files. The unmodified DLL package was downloaded from the official SoundTouch site. Its license, headers, source link and binary SHA-256 hashes are included in that directory. See vendor/soundtouch/COPYING.TXT and provenance.json. Missing or incompatible DLLs produce a startup error instead of silently using the old lower-quality effect.

Native pitch benchmarks are recorded in analysis/pitch-benchmark.json. A separate 60-second simulated stereo stream at -12 semitones/48 kHz completed with zero native buffer underruns. These are offline processing checks, not hardware drop-out or subjective listening measurements.

The expanded Voicemod inspection is documented in analysis/voice-quality-investigation.md. It found native pitch/formant, SoundTouch, denoising and AI-related components in the larger per-user app, but did not recover individual voice implementations.

## Desktop interface

The UI uses a charcoal and mint theme, a searchable/category-filtered voice library, a separate custom editor, and persistent audio controls. Both content panels scroll at smaller window sizes. Ctrl+F focuses search; native buttons and sliders support keyboard navigation. Selected voices have a text indicator as well as a color change. Device changes are disabled while streaming. Restart the app to load the new interface.

Design guidance: UI/UX Pro Max, installed locally under .agents/skills/ui-ux-pro-max. Its flat-design, contrast, focus and spacing guidance was adapted to Tkinter; web landing-page and mobile-only recommendations were not applied.

## Additional custom effects

Scroll through the custom editor to access:

- Formant shift: -6 to +6 semitones of approximate spectral-envelope shifting, with an aligned dry/wet blend. Negative values darken resonance; positive values brighten it. Harmonic frequencies are retained. It is not a neural voice model and large shifts can sound colored. It adds 1024 frames of delay (about 21 ms at 48 kHz) when enabled, in addition to any pitch buffering.
- Tone EQ: warmth (200 Hz shelf), presence (2.5 kHz peak), brightness (5 kHz shelf), each +/-9 dB. Tone blend scales all three gains toward neutral.
- Doubler: a gently modulated 18 ms chorus delay with dry/wet blend.
- Ring modulation: a continuous 20-500 Hz carrier and dry/wet blend for metallic/robotic textures.

All new settings are saved with custom voices. Older preset files receive neutral defaults. Save and Reset remain pinned below the scrollable editor. These controls build a new custom chain; they do not edit the selected built-in preset's internal chain.

The former Send audio / Output enabled control has been replaced by Hear myself. Select a virtual cable for App output and headphones for Monitor. There are now independent application and headphone outputs; see the monitoring section below.

Run all effect and preset checks with `python -m unittest -v test_presets test_voice_effects`. Checks include ring-modulation sidebands, formant envelope movement with retained harmonics, chunk continuity, aligned dry blending, combined processing and old/new preset round trips. Offline combined-effect timing was below the 10.67 ms callback budget in a local 1000-block run; this does not measure hardware latency or guarantee realtime scheduling.

## Hear myself / independent monitoring

- App output / virtual cable: receives the processed voice whenever the voice changer is running.
- Headphones / monitor: select your physical headphones. Tick Hear myself to hear the processed voice; untick it to silence only the monitor. It defaults to off.
- In Discord or the game, select the virtual cable's paired recording endpoint as the microphone. For VB-Cable, this is usually CABLE Output, while this app sends to CABLE Input.
- Keep App output separate from your physical headphones. Sending the main output to speakers will remain audible regardless of the monitor checkbox.
- Mute microphone affects microphone audio on both paths. Volume applies to both paths.

The monitor uses a separate sounddevice OutputStream and a bounded audio queue; voice DSP runs once. Turning monitoring off clears its queue. A headphone startup failure leaves App output running and displays an error. Devices cannot be changed while streaming. The monitor negotiates its own supported sample rate and resamples the preview when it differs from the application stream.

Validation: `python -m unittest -v test_monitoring test_presets test_voice_effects` (15 tests). Monitoring tests cover main output with monitoring disabled, identical processed monitor audio, queue clearing, partial block reads, bounded buffering, same-headset preview switching, and independent failure handling. They use mocked device startup; full app-to-virtual-cable routing has not been tested because this machine did not expose a virtual cable endpoint during implementation.

## Simple headset setup

For the Stealth 500PC, select Microphone (Stealth 500PC) as Microphone and Speakers (Stealth 500PC) as Headphones / Monitor. Leave optional App output on Headset preview only. Start the changer, then tick Hear myself to listen; untick it to silence the preview. Choosing the headset itself as optional App output also uses this checkbox-controlled preview mode, without opening a duplicate monitor stream.

Preview mode requires no virtual cable and does not change Windows defaults or the microphone signal received by other applications. Those apps still receive the original headset microphone. To use effects in apps that follow Windows defaults, install a working virtual audio cable, select its playback endpoint as this app's optional output, and make its paired recording endpoint the Windows default input (including the default communications input where needed). Keep the headset as default playback. Apps with an explicit microphone override need that override changed separately. No Windows defaults or audio drivers are changed automatically by this app.

## Simple everyday controls

Audio Setup is now collapsed by default. The app remembers the microphone, virtual output and monitor by name in audio_settings.json, so changing device indices after restarting Windows does not by itself lose selections. Start/Stop and Hear myself remain visible.

On this installation, a later check exposed Voicemod's Microphone and Dummy Output endpoints. A synthetic loopback probe verified the MME pair (normalized correlation about 0.91); evidence is in analysis/virtual-route-probe.json. WASAPI rejected that endpoint pair, so automatic selection uses its verified MME route with a matching MME headset input. Headphone monitoring uses a separate output stream. The headset-to-Voicemod duplex stream also opened successfully.

This uses the existing Voicemod driver rather than installing a Voice Studio driver. Its availability may depend on Voicemod running. It does not prove compatibility with every Voicemod release or replace end-to-end listening in the target app. Windows' current default capture device was Microphone (Voicemod) during this check. No default-device changes were made by Voice Studio. If defaults change, select the virtual microphone as Windows default input once; keep the Stealth headset as default playback.

## Headphone sample-rate compatibility

The Stealth 500PC MME microphone runs at 44.1 kHz by default, while its WASAPI playback endpoint requires 48 kHz in the tested configuration. The monitor now tries the source rate, the device native rate, and standard fallback rates. A continuous, stateful linear resampler converts only the headphone feed, leaving application audio and voice processing at their original rate. Monitor toggling clears the conversion history as well as queued audio.

Verified on this machine: the actual Stealth WASAPI headphone stream opened at 48 kHz with a 44.1 kHz source. All 17 tests pass, including fallback negotiation, resampling duration/pitch/chunk continuity, and the earlier routing/effect checks. This hardware check opened a silent monitor stream; it did not record or play back microphone speech.

## Recall voices and global shortcut

Select a voice, then click Edit this voice above the custom editor. It loads pitch, distortion, reverb and bit depth while retaining the original built-in filter chain; tone/formant/texture controls can add variation. Save under a new name to preserve the original. Recalling a saved custom voice restores its settings and built-in base, if any. Reset controls clears the base and returns to a neutral custom chain.

The bottom Start/Stop shortcut defaults to Ctrl+Alt+V, works outside the focused app and can be changed or disabled. It is stored in local audio settings. Registration conflicts are shown inline; closing the app releases the shortcut. Stop halts the stream rather than bypassing effects with the clean microphone.

All 20 audio/variation tests pass. A local Windows check verified hotkey registration, delivery to the Tk thread, recall and persistence. No synthetic keyboard input was sent to other applications.

## Character effects and new presets

Space Marine, Ghost, Goblin and Hive Mind bring the built-in library to 18 presets. Space Marine combines a lower pitch/formant, a parallel rough layer and short helmet resonance. Ghost uses light harmony and dark echo/reverb (not a synthesized whisper or breath model). Goblin uses raised pitch/formants, nasal presence and mild rasp. Hive Mind layers two pitched companions around a lead voice.

Expandable editor sections expose:

- Harmony: two pitch intervals (-12 to +12 semitones), independent layer levels and overall blend. The lead is retained in the normalized stack. Harmony adds 120 ms of alignment buffering on top of any upstream pitch/formant latency.
- Resonator: 80-1600 Hz tuning, damped feedback decay and blend, implemented as a short filtered feedback delay.
- Delay: 20-800 ms echo time, feedback up to 75%, 500-10000 Hz echo low-pass tone and blend. Tone filtering colors the wet output, not each trip around the feedback loop.
- Parallel distortion: 0-30 dB drive and a rough-layer blend that retains clean speech.

Each new section has an On bypass switch; switching it off retains its slider values. A zero blend also bypasses the effect. All settings persist in custom voices, including variations loaded with Edit this voice. Older voices receive zero blends, preserving their previous processing.

These presets are DSP character effects, not realistic AI speaker models. Local offline 48 kHz stereo runs processed 1000 blocks per new preset with zero native pitch-buffer underruns; 99th-percentile processing was under 1.4 ms per 512-frame block. This is not a measurement of hardware latency, scheduling under game load or subjective microphone quality.

Run all 25 checks:

```powershell
python -m unittest -v test_presets test_voice_effects test_voice_editing test_monitoring test_character_effects
```

Tests include harmony layer frequencies/alignment, stable delay/resonator tails, bypass behavior, parameter bounds, saved settings and exact recall of the new presets. Use render_previews.py on the same speech recording to compare voices by listening.

## Avoiding a doubled original voice with Voicemod's driver

Voicemod itself can read the headset microphone and write its original voice to the same virtual output that Voice Studio uses. The Windows mixer then combines those two applications. Voicemod can also have a separate headphone-monitor feed. Hear myself in Voice Studio cannot otherwise control those other-process feeds.

When using a Voicemod virtual output, Voice Studio now isolates its own feed: a Windows audio-session guard temporarily mutes only Voicemod.exe's rendering sessions on the selected virtual output and selected headphone endpoint. Other applications and the physical microphone's volume are not muted. Start also watches for newly created Voicemod sessions; Stop and normal window closure restore each session's previous mute state. If route isolation fails, startup fails or an active stream stops rather than silently continuing with mixed audio.

This requires pycaw and its comtypes/psutil dependencies, included in requirements.txt. Update dependencies before starting:

```powershell
python -m pip install -r requirements.txt
```

Forced termination cannot run normal restoration; if Voicemod remains muted afterward, reset its per-application output mute in the Windows volume mixer. This guard is specific to the existing Voicemod route; other virtual cables do not need it.

For a recording test, select Microphone (Voicemod) in Windows Sound Recorder, start Voice Studio with Deep (Vader), and leave Hear myself unticked. Record a short phrase, stop recording, then play it back. The saved recording should contain the transformed voice, not a separate original-mic overlay. Harmony, doubler and delay presets deliberately contain layers, so Deep is a clearer isolation test.

29 automated tests pass, including no raw input added to processed output, targeted competing-session muting, restoration, and failed-start cleanup. On the implementation machine, the live headset-to-virtual stream started with both competing Voicemod render feeds muted, then restored their original mute states on Stop. A synthetic 220-to-110 Hz pitch probe through the virtual device had the original frequency around 40 dB below the transformed frequency; this probe is not a substitute for listening to a speech recording.


## Quality audit and comparison

Use Test voice for same-sample, level-matched comparisons. See docs/AUDIO_EFFECTS_AUDIT.md and docs/AUTOMATED_AUDIT.md for the 140-configuration audit. The rebuilt telephone/radio settings are in the Communications section. Kid (DSP prototype) is available for evaluation; realistic neural conversion remains open, documented in docs/CHILD_VOICE_EVALUATION.md. The suite now contains 38 tests.
