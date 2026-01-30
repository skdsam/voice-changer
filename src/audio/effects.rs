use fundsp::hacker32::*;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum EffectType {
    None,
    Robot,
    Megaphone,
    DeepVoice,
    HighVoice,
    Echo,
    Alien,
    Radio,
    Demon,
    Kid,
    CBRadio,
    Astronaut,
    Telephone,
    Monster,
    Chipmunk,
    Vader,
    Ghost,
    Cyberpunk,
}

/// Creates an effect chain based on the selected effect type and tuning parameters.
/// `pitch` and `intensity` are expected to be in the range [0.0, 1.0].
pub fn create_effect_chain(effect: EffectType, pitch: f32, intensity: f32) -> Box<dyn AudioUnit> {
    // Clamp inputs to prevent out-of-range values
    let pitch = pitch.clamp(0.0, 1.0);
    let intensity = intensity.clamp(0.0, 1.0);

    match effect {
        EffectType::None => Box::new(pass()) as Box<dyn AudioUnit>,

        // Robot: Subtle ring modulation with harmonics
        EffectType::Robot => {
            let robot_freq = 100.0f32 + pitch * 150.0f32; // Range: 100-250 Hz
            Box::new(
                pass() * (sine_hz(robot_freq) * 0.6f32 + 0.4f32) >> lowpass_hz(4000.0f32, 1.0f32),
            ) as Box<dyn AudioUnit>
        }

        // Megaphone: Band-limited distortion
        EffectType::Megaphone => {
            let gain = 2.0f32 + intensity * 4.0f32; // Range: 2-6x gain
            Box::new(
                highpass_hz(500.0f32, 1.0f32)
                    >> lowpass_hz(3000.0f32, 1.0f32)
                    >> pass() * gain
                    >> clip()
                    >> pass() * 0.5f32,
            ) as Box<dyn AudioUnit>
        }

        // DeepVoice: Low-frequency resonance boost
        EffectType::DeepVoice => {
            let base_f = 150.0f32 - pitch * 50.0f32; // Range: 100-150 Hz
            let boost = 8.0f32 + intensity * 6.0f32; // Range: 8-14 dB boost
            Box::new(
                lowpass_hz(500.0f32, 1.0f32)
                    >> bell_hz(base_f, 2.0f32, boost)
                    >> bell_hz(base_f * 0.5f32, 2.0f32, boost * 0.5f32),
            ) as Box<dyn AudioUnit>
        }

        // HighVoice: High-frequency resonance boost
        EffectType::HighVoice => {
            let base_f = 2500.0f32 + pitch * 1000.0f32; // Range: 2500-3500 Hz
            let boost = 6.0f32 + intensity * 8.0f32; // Range: 6-14 dB boost
            Box::new(
                highpass_hz(300.0f32, 1.0f32) >> bell_hz(base_f, 3.0f32, boost) >> pass() * 0.7f32,
            ) as Box<dyn AudioUnit>
        }

        // Echo: Multi-tap delay
        EffectType::Echo => {
            let delay_time = 0.08f32 + intensity * 0.25f32; // Range: 80-330ms
            Box::new(pass() & (delay(delay_time) * 0.4f32) & (delay(delay_time * 2.0f32) * 0.15f32))
                as Box<dyn AudioUnit>
        }

        // Alien: Subtle tremolo with harmonics
        EffectType::Alien => {
            let mod_f = 5.0f32 + pitch * 20.0f32; // Range: 5-25 Hz
            Box::new(
                pass() * (sine_hz(mod_f) * 0.3f32 + 0.7f32)
                    >> bell_hz(1500.0f32, 2.0f32, 6.0f32 + intensity * 6.0f32),
            ) as Box<dyn AudioUnit>
        }

        // Radio: Classic AM radio simulation
        EffectType::Radio => {
            let gain = 2.0f32 + intensity * 2.0f32;
            Box::new(
                highpass_hz(800.0f32, 1.0f32)
                    >> lowpass_hz(2500.0f32, 1.0f32)
                    >> pass() * gain
                    >> clip()
                    >> pass() * 0.6f32,
            ) as Box<dyn AudioUnit>
        }

        // Demon: Low growl with subtle modulation
        EffectType::Demon => {
            let mod_rate = 2.0f32 + pitch * 8.0f32; // Range: 2-10 Hz
            Box::new(
                lowpass_hz(400.0f32, 1.0f32)
                    >> (pass() * (sine_hz(mod_rate) * 0.2f32 + 0.8f32))
                    >> bell_hz(100.0f32, 3.0f32, 12.0f32 + intensity * 8.0f32),
            ) as Box<dyn AudioUnit>
        }

        // Kid: Brightened voice with gentle formant shift
        EffectType::Kid => {
            let hp_freq = 600.0f32 + pitch * 200.0f32; // Range: 600-800 Hz
            let boost = 8.0f32 + intensity * 6.0f32;
            Box::new(
                highpass_hz(hp_freq, 1.0f32)
                    >> bell_hz(3000.0f32, 3.0f32, boost)
                    >> bell_hz(5000.0f32, 2.0f32, boost * 0.6f32)
                    >> pass() * 0.8f32,
            ) as Box<dyn AudioUnit>
        }

        // CBRadio: Harsh band-limited compression
        EffectType::CBRadio => {
            let gain = 3.0f32 + intensity * 3.0f32;
            Box::new(
                highpass_hz(700.0f32, 1.0f32)
                    >> lowpass_hz(2200.0f32, 1.0f32)
                    >> pass() * gain
                    >> clip()
                    >> pass() * 0.5f32,
            ) as Box<dyn AudioUnit>
        }

        // Astronaut: Space helmet resonance
        EffectType::Astronaut => {
            let resonance = 1500.0f32 + pitch * 500.0f32; // Range: 1500-2000 Hz
            Box::new(
                highpass_hz(800.0f32, 1.0f32)
                    >> lowpass_hz(3500.0f32, 1.0f32)
                    >> bell_hz(resonance, 6.0f32, 12.0f32 + intensity * 6.0f32)
                    >> pass() * 0.7f32,
            ) as Box<dyn AudioUnit>
        }

        // Telephone: Classic phone line simulation
        EffectType::Telephone => Box::new(
            highpass_hz(300.0f32, 1.0f32)
                >> lowpass_hz(3400.0f32, 1.0f32)
                >> bell_hz(1000.0f32, 2.0f32, 8.0f32),
        ) as Box<dyn AudioUnit>,

        // Monster: Heavy bass with distortion
        EffectType::Monster => {
            let cutoff = 200.0f32 + (1.0f32 - pitch) * 150.0f32; // Range: 200-350 Hz
            let gain = 4.0f32 + intensity * 4.0f32;
            Box::new(
                lowpass_hz(cutoff, 1.0f32)
                    >> pass() * gain
                    >> clip()
                    >> lowpass_hz(500.0f32, 1.0f32)
                    >> pass() * 0.6f32,
            ) as Box<dyn AudioUnit>
        }

        // Chipmunk: High-pitched formant shift
        EffectType::Chipmunk => {
            let hp_freq = 1200.0f32 + pitch * 400.0f32; // Range: 1200-1600 Hz
            let boost = 12.0f32 + intensity * 8.0f32;
            Box::new(
                highpass_hz(hp_freq, 1.5f32)
                    >> bell_hz(4000.0f32, 4.0f32, boost)
                    >> bell_hz(6500.0f32, 3.0f32, boost * 0.7f32)
                    >> pass() * 0.6f32,
            ) as Box<dyn AudioUnit>
        }

        // Vader: Breathing mask effect
        EffectType::Vader => {
            let breath_rate = 0.3f32 + pitch * 0.7f32; // Range: 0.3-1.0 Hz
            Box::new(
                lowpass_hz(500.0f32, 1.0f32)
                    >> bell_hz(120.0f32, 4.0f32, 14.0f32)
                    >> bell_hz(250.0f32, 3.0f32, 10.0f32)
                    >> (pass() * (sine_hz(breath_rate) * 0.15f32 + 0.85f32)),
            ) as Box<dyn AudioUnit>
        }

        // Ghost: Ethereal reverb-like delays
        EffectType::Ghost => {
            let d = 0.05f32 + intensity * 0.2f32; // Range: 50-250ms
            let b1 = delay(d) >> mul(0.35f32);
            let b2 = delay(d * 2.5f32) >> mul(0.2f32);
            let b3 = delay(d * 4.0f32) >> mul(0.1f32);
            Box::new(highpass_hz(400.0f32, 1.0f32) & b1 & b2 & b3) as Box<dyn AudioUnit>
        }

        // Cyberpunk: Aggressive distortion with presence
        EffectType::Cyberpunk => {
            let crunch = 3.0f32 + intensity * 5.0f32; // Range: 3-8x gain
            Box::new(
                pass() * crunch
                    >> clip()
                    >> bell_hz(1500.0f32, 4.0f32, 10.0f32)
                    >> bell_hz(3000.0f32, 3.0f32, 8.0f32)
                    >> pass() * 0.25f32,
            ) as Box<dyn AudioUnit>
        }
    }
}
