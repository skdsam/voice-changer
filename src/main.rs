mod audio;

use audio::effects::EffectType;
use audio::engine::AudioEngine;
use parking_lot::Mutex;
use std::sync::Arc;

slint::include_modules!();

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let mut engine = AudioEngine::new()?;
    engine.setup_devices()?;

    let engine = Arc::new(Mutex::new(engine));
    let ui = AppWindow::new()?;

    // Populate devices
    {
        let engine_lock = engine.lock();
        let inputs: Vec<slint::SharedString> = engine_lock
            .list_inputs()
            .into_iter()
            .map(|s| s.into())
            .collect();
        let outputs: Vec<slint::SharedString> = engine_lock
            .list_outputs()
            .into_iter()
            .map(|s| s.into())
            .collect();

        ui.set_input_devices(std::rc::Rc::new(slint::VecModel::from(inputs)).into());
        ui.set_output_devices(std::rc::Rc::new(slint::VecModel::from(outputs)).into());
    }

    ui.on_toggle_audio({
        let ui_handle = ui.as_weak();
        let engine = engine.clone();
        move || {
            let ui = ui_handle.unwrap();
            let mut engine = engine.lock();
            let current = ui.get_audio_active();

            if !current {
                if let Err(e) = engine.setup_devices().and_then(|_| engine.start()) {
                    eprintln!("Failed to start engine: {}", e);
                    return;
                }
                ui.set_audio_active(true);
            } else {
                engine.stop();
                ui.set_audio_active(false);
            }
        }
    });
    ui.on_select_input_device({
        let engine = engine.clone();
        move |val| {
            let engine = engine.lock();
            *engine.selected_input.lock() = Some(val.to_string());
        }
    });

    ui.on_select_output_device({
        let engine = engine.clone();
        move |val| {
            let engine = engine.lock();
            *engine.selected_output.lock() = Some(val.to_string());
        }
    });

    ui.on_select_monitor_device({
        let engine = engine.clone();
        move |val| {
            let engine = engine.lock();
            *engine.selected_monitor.lock() = Some(val.to_string());
        }
    });

    ui.on_toggle_monitor({
        let engine = engine.clone();
        move |val| {
            let engine = engine.lock();
            *engine.monitor_enabled.lock() = val;
        }
    });
    ui.on_select_effect({
        let engine = engine.clone();
        move |index| {
            let engine = engine.lock();
            let effect = match index {
                0 => EffectType::None,
                1 => EffectType::Robot,
                2 => EffectType::Megaphone,
                3 => EffectType::DeepVoice,
                4 => EffectType::HighVoice,
                5 => EffectType::Echo,
                6 => EffectType::Alien,
                7 => EffectType::Radio,
                8 => EffectType::Demon,
                _ => EffectType::None,
            };
            *engine.current_effect.lock() = effect;
        }
    });

    ui.run()?;
    Ok(())
}
