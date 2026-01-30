use fundsp::hacker::*;

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
}

pub fn create_effect_chain(effect: EffectType) -> Box<dyn AudioUnit> {
    match effect {
        EffectType::None => Box::new(pass()) as Box<dyn AudioUnit>,
        EffectType::Robot => {
            Box::new(pass() * (sine_hz(400.0) + sine_hz(800.0) * 0.5) >> lowpass_hz(3000.0, 1.0))
                as Box<dyn AudioUnit>
        }
        EffectType::Megaphone => {
            Box::new(highpass_hz(600.0, 1.0) >> lowpass_hz(2500.0, 1.0) >> pass() * 5.0 >> clip())
                as Box<dyn AudioUnit>
        }
        EffectType::DeepVoice => {
            Box::new(lowpass_hz(400.0, 1.0) >> peak_hz(200.0, 1.0) >> peak_hz(100.0, 1.0))
                as Box<dyn AudioUnit>
        }
        EffectType::HighVoice => {
            Box::new(highpass_hz(1000.0, 1.0) >> peak_hz(3000.0, 1.0)) as Box<dyn AudioUnit>
        }
        EffectType::Echo => {
            Box::new(pass() & delay(0.2) * 0.5 & delay(0.4) * 0.2) as Box<dyn AudioUnit>
        }
        EffectType::Alien => {
            Box::new(pass() * (sine_hz(20.0) * 0.5 + 0.5) * sine_hz(60.0)) as Box<dyn AudioUnit>
        }
        EffectType::Radio => {
            Box::new(highpass_hz(1000.0, 1.0) >> lowpass_hz(2000.0, 1.0) >> pass() * 3.0 >> clip())
                as Box<dyn AudioUnit>
        }
        EffectType::Demon => {
            Box::new(lowpass_hz(300.0, 1.0) * sine_hz(15.0) >> lowpass_hz(500.0, 1.0))
                as Box<dyn AudioUnit>
        }
    }
}
