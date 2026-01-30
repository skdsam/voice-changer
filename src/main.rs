mod audio;

use audio::effects::EffectType;
use audio::engine::AudioEngine;
use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use slint::ComponentHandle;
use std::fs::File;
use std::io::{Read, Write};
use std::sync::Arc;

slint::include_modules!();

#[derive(Serialize, Deserialize, Clone)]
struct AppSettings {
    input_device: String,
    output_device: String,
    monitor_device: String,
    monitor_enabled: bool,
    selected_effect_index: i32,
    pitch: f32,
    intensity: f32,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            input_device: "Default".to_string(),
            output_device: "Default".to_string(),
            monitor_device: "Default".to_string(),
            monitor_enabled: false,
            selected_effect_index: 0,
            pitch: 0.5,
            intensity: 0.5,
        }
    }
}

fn load_settings() -> AppSettings {
    let mut file = match File::open("settings.json") {
        Ok(f) => f,
        Err(_) => return AppSettings::default(),
    };
    let mut contents = String::new();
    if file.read_to_string(&mut contents).is_ok() {
        serde_json::from_str(&contents).unwrap_or_default()
    } else {
        AppSettings::default()
    }
}

fn save_settings(settings: &AppSettings) {
    if let Ok(json) = serde_json::to_string_pretty(settings) {
        if let Ok(mut file) = File::create("settings.json") {
            let _ = file.write_all(json.as_bytes());
        }
    }
}

fn main() -> anyhow::Result<()> {
    let engine_instance = AudioEngine::new()?;
    let engine = Arc::new(Mutex::new(engine_instance));
    let ui = AppWindow::new()?;

    let settings = Arc::new(Mutex::new(load_settings()));
    let s = settings.lock().clone(); // Clone settings for initial UI/engine sync

    // Populate devices and sync initial state from settings
    {
        let mut engine_lock = engine.lock();
        engine_lock.setup_devices()?; // Ensure devices are set up before listing

        let input_list = engine_lock.list_inputs();
        let output_list = engine_lock.list_outputs();

        println!("--- Audio Devices Debug ---");
        println!("Input Devices: {:?}", input_list);
        println!("Output Devices: {:?}", output_list);

        let mut inputs: Vec<slint::SharedString> = vec!["Default".into()];
        inputs.extend(input_list.into_iter().map(|s| s.into()));

        let mut outputs: Vec<slint::SharedString> = vec!["Default".into()];
        outputs.extend(output_list.into_iter().map(|s| s.into()));

        ui.set_input_devices(std::rc::Rc::new(slint::VecModel::from(inputs)).into());
        ui.set_output_devices(std::rc::Rc::new(slint::VecModel::from(outputs)).into());

        // Sync engine state from loaded settings
        *engine_lock.selected_input.lock() = Some(s.input_device.clone());
        *engine_lock.selected_output.lock() = Some(s.output_device.clone());
        *engine_lock.selected_monitor.lock() = Some(s.monitor_device.clone());
        *engine_lock.monitor_enabled.lock() = s.monitor_enabled;
        *engine_lock.pitch.lock() = s.pitch as f64;
        *engine_lock.intensity.lock() = s.intensity as f64;

        let effect = match s.selected_effect_index {
            0 => EffectType::None,
            1 => EffectType::Robot,
            2 => EffectType::Megaphone,
            3 => EffectType::DeepVoice,
            4 => EffectType::HighVoice,
            5 => EffectType::Echo,
            6 => EffectType::Alien,
            7 => EffectType::Radio,
            8 => EffectType::Demon,
            9 => EffectType::Kid,
            10 => EffectType::CBRadio,
            11 => EffectType::Astronaut,
            12 => EffectType::Telephone,
            13 => EffectType::Monster,
            14 => EffectType::Chipmunk,
            15 => EffectType::Vader,
            16 => EffectType::Ghost,
            17 => EffectType::Cyberpunk,
            _ => EffectType::None,
        };
        *engine_lock.current_effect.lock() = effect;

        // Sync UI state from loaded settings
        ui.set_current_input(s.input_device.into());
        ui.set_current_output(s.output_device.into());
        ui.set_current_monitor(s.monitor_device.into());
        ui.set_monitor_active(s.monitor_enabled);
        ui.set_selected_effect_index(s.selected_effect_index);
        ui.set_pitch_value(s.pitch);
        ui.set_intensity_value(s.intensity);
    }

    let save_settings_fn = {
        let settings = settings.clone();
        move || {
            let s = settings.lock();
            save_settings(&s);
        }
    };

    ui.on_select_effect({
        let ui_handle = ui.as_weak();
        let engine = engine.clone();
        let settings = settings.clone();
        let save_settings_fn = save_settings_fn.clone();
        move |index| {
            let ui = ui_handle.unwrap();
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
                9 => EffectType::Kid,
                10 => EffectType::CBRadio,
                11 => EffectType::Astronaut,
                12 => EffectType::Telephone,
                13 => EffectType::Monster,
                14 => EffectType::Chipmunk,
                15 => EffectType::Vader,
                16 => EffectType::Ghost,
                17 => EffectType::Cyberpunk,
                _ => EffectType::None,
            };
            *engine.current_effect.lock() = effect;
            ui.set_selected_effect_index(index);

            settings.lock().selected_effect_index = index;
            save_settings_fn();
        }
    });

    ui.on_adjust_pitch({
        let engine = engine.clone();
        let settings = settings.clone();
        let save_settings_fn = save_settings_fn.clone();
        move |val| {
            let engine = engine.lock();
            *engine.pitch.lock() = val as f64;
            settings.lock().pitch = val;
            save_settings_fn();
        }
    });

    ui.on_adjust_intensity({
        let engine = engine.clone();
        let settings = settings.clone();
        let save_settings_fn = save_settings_fn.clone();
        move |val| {
            let engine = engine.lock();
            *engine.intensity.lock() = val as f64;
            settings.lock().intensity = val;
            save_settings_fn();
        }
    });

    ui.on_select_input_device({
        let engine = engine.clone();
        let settings = settings.clone();
        let save_settings_fn = save_settings_fn.clone();
        move |name| {
            let name_str = name.to_string();
            let mut engine = engine.lock();
            *engine.selected_input.lock() = Some(name_str.clone());
            let _ = engine.setup_devices();

            settings.lock().input_device = name_str;
            save_settings_fn();
        }
    });

    ui.on_select_output_device({
        let engine = engine.clone();
        let settings = settings.clone();
        let save_settings_fn = save_settings_fn.clone();
        move |name| {
            let name_str = name.to_string();
            let mut engine = engine.lock();
            *engine.selected_output.lock() = Some(name_str.clone());
            let _ = engine.setup_devices();

            settings.lock().output_device = name_str;
            save_settings_fn();
        }
    });

    ui.on_select_monitor_device({
        let engine = engine.clone();
        let settings = settings.clone();
        let save_settings_fn = save_settings_fn.clone();
        move |name| {
            let name_str = name.to_string();
            let mut engine = engine.lock();
            *engine.selected_monitor.lock() = Some(name_str.clone());
            let _ = engine.setup_devices();

            settings.lock().monitor_device = name_str;
            save_settings_fn();
        }
    });

    ui.on_toggle_monitor({
        let engine = engine.clone();
        let settings = settings.clone();
        let save_settings_fn = save_settings_fn.clone();
        move |active| {
            let mut engine_guard = engine.lock();
            *engine_guard.monitor_enabled.lock() = active;
            let _ = engine_guard.toggle_monitor(active);

            settings.lock().monitor_enabled = active;
            save_settings_fn();
        }
    });

    ui.on_toggle_audio({
        let ui_handle = ui.as_weak();
        let engine = engine.clone();
        move || {
            let ui = ui_handle.unwrap();
            let mut engine = engine.lock();
            let is_running = *engine.is_running.lock();
            if is_running {
                engine.stop();
                ui.set_audio_active(false);
            } else {
                if let Ok(_) = engine.start() {
                    ui.set_audio_active(true);
                }
            }
        }
    });

    ui.run()?;
    Ok(())
}
