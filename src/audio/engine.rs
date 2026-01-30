use crate::audio::effects::{EffectType, create_effect_chain};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use parking_lot::Mutex;
use ringbuf::SharedRb;
use std::sync::Arc;

pub struct AudioEngine {
    host: cpal::Host,
    input_device: Option<cpal::Device>,
    output_device: Option<cpal::Device>,
    input_stream: Option<cpal::Stream>,
    output_stream: Option<cpal::Stream>,
    pub is_running: Arc<Mutex<bool>>,
    pub current_effect: Arc<Mutex<EffectType>>,
    pub selected_input: Arc<Mutex<Option<String>>>,
    pub selected_output: Arc<Mutex<Option<String>>>,
    pub selected_monitor: Arc<Mutex<Option<String>>>,
    pub monitor_enabled: Arc<Mutex<bool>>,
    monitor_stream: Option<cpal::Stream>,
}

impl AudioEngine {
    pub fn new() -> anyhow::Result<Self> {
        let host = cpal::default_host();
        Ok(Self {
            host,
            input_device: None,
            output_device: None,
            input_stream: None,
            output_stream: None,
            is_running: Arc::new(Mutex::new(false)),
            current_effect: Arc::new(Mutex::new(EffectType::None)),
            selected_input: Arc::new(Mutex::new(None)),
            selected_output: Arc::new(Mutex::new(None)),
            selected_monitor: Arc::new(Mutex::new(None)),
            monitor_enabled: Arc::new(Mutex::new(false)),
            monitor_stream: None,
        })
    }

    pub fn list_inputs(&self) -> Vec<String> {
        self.host
            .input_devices()
            .map(|devices| {
                devices
                    .map(|d| d.name().unwrap_or_else(|_| "Unknown".to_string()))
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn list_outputs(&self) -> Vec<String> {
        self.host
            .output_devices()
            .map(|devices| {
                devices
                    .map(|d| d.name().unwrap_or_else(|_| "Unknown".to_string()))
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn setup_devices(&mut self) -> anyhow::Result<()> {
        let selected_input = self.selected_input.lock().clone();
        let selected_output = self.selected_output.lock().clone();

        self.input_device = match selected_input {
            Some(ref name) => self
                .host
                .input_devices()?
                .find(|d| d.name().ok().as_ref() == Some(name)),
            None => self.host.default_input_device(),
        };

        self.output_device = match selected_output {
            Some(ref name) => self
                .host
                .output_devices()?
                .find(|d| d.name().ok().as_ref() == Some(name)),
            None => self.host.default_output_device(),
        };

        if self.input_device.is_none() || self.output_device.is_none() {
            anyhow::bail!("Input or output device not found");
        }

        Ok(())
    }

    pub fn start(&mut self) -> anyhow::Result<()> {
        let input_config: cpal::StreamConfig = self
            .input_device
            .as_ref()
            .unwrap()
            .default_input_config()?
            .into();
        let output_config: cpal::StreamConfig = self
            .output_device
            .as_ref()
            .unwrap()
            .default_output_config()?
            .into();

        let input_channels = input_config.channels as usize;
        let output_channels = output_config.channels as usize;

        // Rings buffer for input -> processing
        let rb_in = SharedRb::<f32, Vec<std::mem::MaybeUninit<f32>>>::new(8192);
        let (mut prod_in, mut cons_in) = rb_in.split();

        // Ring buffer for processing -> output
        let rb_out = SharedRb::<f32, Vec<std::mem::MaybeUninit<f32>>>::new(8192);
        let (mut prod_out, mut cons_out) = rb_out.split();

        // Optional monitor ring buffer
        let monitor_enabled = *self.monitor_enabled.lock();
        let (mut prod_mon, mut cons_mon) = if monitor_enabled {
            let rb = SharedRb::<f32, Vec<std::mem::MaybeUninit<f32>>>::new(8192);
            let (p, c) = rb.split();
            (Some(p), Some(c))
        } else {
            (None, None)
        };

        // Capture is_running to control thread lifecycle
        let is_running_thread = self.is_running.clone();
        *is_running_thread.lock() = true;

        let input_callback = move |data: &[f32], _: &cpal::InputCallbackInfo| {
            for frame in data.chunks(input_channels) {
                // Averaging channels for better mono conversion
                let mono_sample = frame.iter().sum::<f32>() / input_channels as f32;
                let _ = prod_in.push(mono_sample);
            }
        };

        // Processing thread
        let current_effect = self.current_effect.clone();
        std::thread::spawn(move || {
            let mut active_effect_type = EffectType::None;
            let mut active_effect = create_effect_chain(active_effect_type);
            let mut out_buf = [0.0f32];

            while *is_running_thread.lock() {
                if let Some(sample) = cons_in.pop() {
                    // Check effect change
                    {
                        let et = *current_effect.lock();
                        if et != active_effect_type {
                            active_effect_type = et;
                            active_effect = create_effect_chain(active_effect_type);
                        }
                    }

                    active_effect.tick(&[sample], &mut out_buf);
                    let processed = out_buf[0];

                    // Block push if ring buffer is full to avoid stuttering
                    while prod_out.push(processed).is_err() {
                        if !*is_running_thread.lock() {
                            return;
                        }
                        std::thread::yield_now();
                    }

                    if let Some(ref mut p) = prod_mon {
                        let _ = p.push(processed);
                    }
                } else {
                    std::thread::sleep(std::time::Duration::from_micros(500));
                }
            }
        });

        let output_callback = move |data: &mut [f32], _: &cpal::OutputCallbackInfo| {
            for frame in data.chunks_mut(output_channels) {
                let sample = cons_out.pop().unwrap_or(0.0);
                for s in frame {
                    *s = sample;
                }
            }
        };

        let err_fn = |err| eprintln!("an error occurred on stream: {}", err);

        let input_stream = self.input_device.as_ref().unwrap().build_input_stream(
            &input_config,
            input_callback,
            err_fn,
            None,
        )?;

        let output_stream = self.output_device.as_ref().unwrap().build_output_stream(
            &output_config,
            output_callback,
            err_fn,
            None,
        )?;

        input_stream.play()?;
        output_stream.play()?;

        self.input_stream = Some(input_stream);
        self.output_stream = Some(output_stream);

        // Optional monitor stream
        if let Some(mut cons) = cons_mon {
            if let Some(ref monitor_name) = self.selected_monitor.lock().clone() {
                if let Some(monitor_dev) = self
                    .host
                    .output_devices()?
                    .find(|d| d.name().ok().as_ref() == Some(monitor_name))
                {
                    let mon_config: cpal::StreamConfig =
                        monitor_dev.default_output_config()?.into();
                    let mon_channels = mon_config.channels as usize;
                    let mon_stream = monitor_dev.build_output_stream(
                        &mon_config,
                        move |data: &mut [f32], _: &cpal::OutputCallbackInfo| {
                            for frame in data.chunks_mut(mon_channels) {
                                let sample = cons.pop().unwrap_or(0.0);
                                for s in frame {
                                    *s = sample;
                                }
                            }
                        },
                        err_fn,
                        None,
                    )?;
                    mon_stream.play()?;
                    self.monitor_stream = Some(mon_stream);
                }
            }
        }

        Ok(())
    }

    pub fn stop(&mut self) {
        self.input_stream = None;
        self.output_stream = None;
        self.monitor_stream = None;
        *self.is_running.lock() = false;
    }
}
