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

14 built-in presets include Clean, Broadcast, Warm Low, Bright, Deep, Monster, Chipmunk, Cyborg, Walkie-Talkie, Telephone, Astronaut, 8-Bit, Cathedral and Alien.

The custom editor provides pitch, approximate formant shifting, warmth/presence/brightness EQ, doubler, ring modulation, distortion, bit depth and reverb. Blend controls let you reduce the stronger effects. Custom controls create a new chain rather than editing a built-in preset's internal chain.

Save named custom voices to the library. Settings are validated and saved atomically to `custom_presets.json`. Older presets load neutral defaults for newer effects. Custom voices and `audio_settings.json` are local and ignored by Git.

## Quality and latency

These are DSP effects, not neural speaker-conversion models. Formant shifting approximates spectral-envelope movement, not vocal-tract modeling. Extreme shifts can sound artificial; start with Broadcast, Warm Low or Bright.

Pitch voices use a 120 ms output reservoir. Formant processing adds 1024 frames (about 21 ms at 48 kHz). Device buffering adds further latency. Final output is limited and checked for non-finite samples.

Headphone monitoring has a separate stream, supported-rate negotiation and bounded queue. A continuous linear resampler converts only the monitor feed when sample rates differ. A monitor startup failure leaves application output running. Hardware compatibility, end-to-end latency and subjective quality need checking on the target setup.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_presets test_voice_effects test_monitoring
```

17 tests cover preset streaming, pitch accuracy, formant behavior, ring-modulation sidebands, effect order, settings compatibility, monitoring isolation, sample-rate fallback and resampling continuity. Hardware startup is mocked in the suite.

## Listening comparisons

```powershell
.\.venv\Scripts\python.exe render_previews.py my-speech.wav --output my-previews
```

Processes the same recording through each built-in preset using the live callback and limiter, adding a short tail for buffered speech and ambience.

## Third-party components

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The unmodified SoundTouch 2.3.3 x64 DLL, license, C API header, provenance and upstream source archive are included in `vendor/soundtouch`.
