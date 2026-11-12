# Youthful voice: prototype and realism evaluation

## Available now

Kid (DSP prototype) uses a modest +3.5 semitone pitch change, +2.5 semitone approximate formant shift, reduced warmth and restrained presence/brightness boosts. It avoids distortion, chorus, echo and harmony, so those do not mask the underlying speech quality. All controls are recallable with Edit this voice. It is an experiment, not a verified realistic child identity.

Whether it sounds youthful depends strongly on the original speaker, delivery and microphone. Raising pitch alone does not reproduce a child's articulation, resonance or learned speaker identity. No age or realism score has been measured.

## Neural candidate evaluated at documentation level

The [official RVC project](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) provides real-time voice conversion. Its [real-time implementation](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/realtime_gui.py) takes model checkpoint/index paths and supports pitch/formant controls. Its [current setup documentation](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md) targets Python 3.12 and hardware-specific Torch dependencies. That is a separate environment from this app's tested Python 3.11 installation.

This makes a separate local inference worker a plausible integration route rather than adding heavy model inference inside the audio callback. The RTX 4070 Ti is a candidate for evaluation, not a guarantee of a latency target.

## What is not implemented or established

No compatible childlike checkpoint with verified usage/distribution terms has been selected. No model weights, model runtime or neural conversion integration have been installed. Documentation review is not an inference benchmark. The DSP prototype is not a substitute for that missing evaluation.

## Required next experiment

1. Select a suitable model with clear terms and documented voice provenance, ideally a generic character rather than a named person's imitation.
2. Benchmark it in an isolated environment on this GPU using the same captured phrase as the DSP comparison.
3. Check speaker consistency, intelligibility, sibilants, quiet speech, high/low input pitch and source-voice leakage.
4. Measure full microphone-to-output latency and run at least a sustained session under game load.
5. Integrate a bounded, asynchronous local PCM worker with explicit model errors and no silent raw-microphone fallback.
6. Add the result as a realistic voice only after listening and latency acceptance.

The realistic-child-voice milestone remains open. The app does not imply that arbitrary downloaded weights will work or that this prototype has achieved it.
