# Voice Studio

A Windows desktop voice changer with a compact voice library, custom effects, and independent headphone monitoring. This replaces the previous Rust/Slint prototype, which remains in Git history.

## Run

Requires Windows 10/11 and Python 3.11 x64 (the tested version).

```powershell
git clone https://github.com/skdsam/voice-changer.git
cd voice-changer
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

No compilation is needed. Keep `vendor/soundtouch` alongside the Python files.

## Everyday use

1. Open **Audio setup** once and select your physical microphone and headphones.
2. Select **Headset preview only** for a local test, or a compatible virtual audio device's playback endpoint to send effects to other apps.
3. Choose a voice and press **Start voice changer**.
4. Tick **Hear myself** to hear the effects. Untick it to silence headphones while virtual-device output continues.
5. Press **Stop voice changer** when finished.

Device choices are remembered locally. Microphone mute and master volume apply to both outputs. If the main output and monitor are the same headset, the app uses checkbox-controlled preview mode.

## Discord, games and Windows defaults

The app does not install a virtual microphone driver or change Windows defaults. Other apps using the physical headset microphone directly receive the original voice.

With VB-Cable, choose **CABLE Input** as Voice Studio's output and **CABLE Output** as the other app's microphone. For apps following Windows defaults, set the virtual recording endpoint as the default input/default communications input once. Keep headphones as default playback.

Voicemod virtual outputs are also detected. One installation's `Dummy Output (Voicemod)` / `Microphone (Voicemod)` MME pair passed a synthetic loopback check. Compatibility is not guaranteed across releases, and those endpoints may disappear when Voicemod closes. No Voicemod drivers, binaries or voice assets are included. The app tries to match the physical input's host API to the virtual output.

## Voices and custom effects

19 built-in presets include Clean, Broadcast, Warm Low, Bright, Deep, Monster, Chipmunk, Cyborg, Walkie-Talkie, Telephone, Astronaut, 8-Bit, Cathedral, Alien, Space Marine, Ghost, Goblin, Hive Mind and Kid (DSP prototype).

The custom editor provides pitch, approximate formant shifting, warmth/presence/brightness EQ, doubler, ring modulation, distortion, bit depth and reverb. Blend controls let you reduce the stronger effects. Select a voice and click **Edit this voice** to copy its primary settings into the editor. Built-in variations preserve the original filters, including filters without dedicated sliders. Adjust controls and save under a new name. Changing a primary control replaces that part of the copied chain; it does not stack an extra pitch shifter on top.

Save named custom voices to the library. Settings are validated and saved atomically to `custom_presets.json`. Older presets load neutral defaults for newer effects. Custom voices and `audio_settings.json` are local and ignored by Git.

## Quality and latency

These are DSP effects, not neural speaker-conversion models. Formant shifting approximates spectral-envelope movement, not vocal-tract modeling. Extreme shifts can sound artificial; start with Broadcast, Warm Low or Bright.

Pitch voices use a 120 ms output reservoir. Formant processing adds 1024 frames (about 21 ms at 48 kHz). Device buffering adds further latency. Final output is limited and checked for non-finite samples.

Headphone monitoring has a separate stream, supported-rate negotiation and bounded queue. A continuous linear resampler converts only the monitor feed when sample rates differ. A monitor startup failure leaves application output running. Hardware compatibility, end-to-end latency and subjective quality need checking on the target setup.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_presets test_voice_effects test_monitoring test_voice_editing
```

38 tests cover preset streaming, pitch accuracy, formant behavior, ring-modulation sidebands, effect order, settings compatibility, monitoring isolation, sample-rate fallback and resampling continuity. Hardware startup is mocked in the suite.

## Listening comparisons

```powershell
.\.venv\Scripts\python.exe render_previews.py my-speech.wav --output my-previews
```

Processes the same recording through each built-in preset using the live callback and limiter, adding a short tail for buffered speech and ambience.

## Third-party components

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The unmodified SoundTouch 2.3.3 x64 DLL, license, C API header, provenance and upstream source archive are included in `vendor/soundtouch`.

## Global Start/Stop shortcut

The bottom control defaults to **Ctrl+Alt+V**. It starts or stops the audio stream, including while the window is minimized or another app has focus. The selector also offers Ctrl+Alt+F8, F8, F9, F10 and Disabled. The selected key is remembered in local audio settings. Holding a key does not repeatedly toggle the stream.

If another app owns the combination, registration reports a conflict. A previously active shortcut stays registered when a replacement fails. Closing Voice Studio releases the shortcut. The shortcut uses Windows RegisterHotKey; it does not record general keyboard input.

**Stop** stops sending audio to the virtual microphone; it is not a clean-voice bypass. **Hear myself** remains independent.

Tests verify that recalling all built-ins without edits produces the original audio, primary pitch edits retain the remaining effects, and saved variations retain their built-in base. Existing custom voices without a built-in base remain supported.

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

## Rebuilt telephone and radio / local comparison

Telephone now uses cascaded band edges, handset resonance, speech compression and controlled saturation. Walkie-Talkie has distinct radio compression and bandwidth plus speech-triggered squelch. In Create a voice, expand Communications to choose Off / Telephone / Radio, adjust drive and gate threshold, or add optional static and end clicks. Texture defaults to off. Edit this voice recalls the complete communications settings; older saved variations inherit the correct channel type.

Click **Test voice** to pause live output and open a local comparison window:

1. Record up to eight seconds from the selected physical microphone; Stop recording ends it early.
2. Choose a preset to process the same sample again without rerecording.
3. Play original and Play processed use the selected headphones, active-speech RMS matching, algorithmic latency compensation and peak protection.
4. Export pair optionally saves original.wav and processed.wav to a folder you select. Both exports have matched levels; the original is not an untouched raw archival capture.

Audio stays in memory unless exported and is discarded when the test window closes. Playback is local; the live stream cannot restart while testing. The app does not restart live output automatically after closing the test. The comparison includes a two-second tail, so very long echo/reverb tails may be truncated. Level matching is RMS-based, not LUFS.

Kid (DSP prototype) is a youthful pitch/formant experiment, not an established realistic child voice. A suitable neural model has not been selected or integrated. The [child-voice evaluation](docs/CHILD_VOICE_EVALUATION.md) records that open milestone rather than implying realism has been achieved.

## Effect audit

See the [effect-by-effect audit and quality plan](docs/AUDIO_EFFECTS_AUDIT.md) and [automated measurements](docs/AUTOMATED_AUDIT.md). The final offline run covered 140 combinations of presets and individual/stacked stress effects, with no errors, sanitized invalid samples, clipped output samples or native pitch-buffer underruns. Resonator normalization was improved to retain usable level at high decay. These are engineering checks, not a guarantee of subjective quality.

Reproduce the audit without recording a microphone:

```powershell
python audit_audio.py --report-dir audit-results
python -m unittest discover -v
```

The full suite has 38 tests. Record a real speech sample with the Stealth headset to provide the missing perceptual listening signoff.
