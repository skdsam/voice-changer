"""Repeatable offline audio audit. No microphone capture or saved speech required."""
import argparse,json,time
from pathlib import Path
import numpy as np
from engine import AudioEngine
from voices import VOICE_PRESETS,create_custom_voice


def stimulus(rate):
    rng=np.random.default_rng(73)
    t=np.arange(rate*3)/rate
    voiced=sum(np.sin(2*np.pi*145*k*t)/k for k in range(1,18)).astype('float32')
    voiced/=max(abs(voiced))
    envelope=.5+.5*np.sin(2*np.pi*3*t)**2
    signal=(voiced*.14+rng.normal(0,.009,len(t)))*envelope
    signal[:rate//2]*=.08
    signal[rate:rate+rate//3]*=3
    signal[rate*2:rate*2+rate//4]=0
    return np.pad(signal.astype('float32'),(0,rate*2))


def run_audit(directory):
    directory.mkdir(parents=True,exist_ok=True)
    factories={name:p['builder'] for name,p in VOICE_PRESETS.items()}
    stresses={
        'Boosted tone EQ':dict(warmth=9,presence=9,brightness=9),
        'Cut tone EQ':dict(warmth=-9,presence=-9,brightness=-9),
        'Telephone channel':dict(comms_mode=1,comms_drive=12),
        'Extreme pitch':dict(pitch_semitones=-12),
        'Extreme formant':dict(formant=6),
        'Strong ring':dict(ring_hz=500,ring_mix=1),
        'Low bit depth':dict(bitcrush_bits=4),
        'Strong distortion':dict(distortion_db=25),
        'Long reverb':dict(reverb_amount=1),
        'Strong doubler':dict(doubler_mix=1),
        'Two harmony layers':dict(harmony_pitch1=-12,harmony_pitch2=12,harmony_level1=1,harmony_level2=1,harmony_mix=1),
        'Maximum resonator decay':dict(resonator_decay=.85,resonator_mix=1),
        'Long feedback echo':dict(delay_ms=800,delay_feedback=.75,delay_mix=1),
        'Strong parallel saturation':dict(parallel_drive=30,parallel_mix=1),
        'Stacked effects':dict(pitch_semitones=-6,formant=-4,warmth=5,presence=5,doubler_mix=.4,
             ring_mix=.3,distortion_db=12,bitcrush_bits=8,harmony_mix=.5,resonator_mix=.4,delay_mix=.3,reverb_amount=.5),
        'Radio with texture':dict(comms_mode=2,comms_static=1,comms_click=1,comms_drive=18),
    }
    factories.update({'Stress / '+name:lambda params=params:create_custom_voice(**params) for name,params in stresses.items()})
    rows=[]
    for rate in (44100,48000):
        source=stimulus(rate)
        for channels in (1,2):
            for name,builder in factories.items():
                engine=AudioEngine(rate,512);engine.set_voice(builder())
                durations=[];peak=0.;prepeak=0.;late_energy=[];bad=0;clipped=0
                for offset in range(0,len(source),512):
                    block=np.repeat(source[offset:offset+512,None],channels,axis=1)
                    output=np.zeros_like(block)
                    start=time.perf_counter();engine._audio_callback(block,output,len(block),None,None)
                    durations.append((time.perf_counter()-start)*1000)
                    bad+=int(engine.last_error is not None or not np.isfinite(output).all())
                    clipped+=int(np.count_nonzero(abs(output)>=.999))
                    peak=max(peak,float(abs(output).max()));prepeak=max(prepeak,engine.pre_limiter_peak)
                    if offset>rate*4.8:late_energy.append(float(np.mean(output**2)))
                row=dict(voice=name,rate=rate,channels=channels,peak=peak,pre_limiter_peak=prepeak,
                    errors=bad,clipped_samples=clipped,sanitized_samples=engine.invalid_sample_count,p99_ms=float(np.percentile(durations,99)),budget_ms=512/rate*1000,
                    tail_db=float(10*np.log10(max(np.mean(late_energy),1e-12))),
                    pitch_underruns=engine.current_board.underruns)
                rows.append(row)
    (directory/'audio-audit.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    lines=['# Automated audio audit','',
        'Offline deterministic speech-like signal: quiet, normal and loud voiced sections, consonant-like noise, pauses and a two-second tail. This is not a listening score or an intelligibility measurement.','',
        '| Voice / effect | Worst p99 ms | Peak | Pre-limiter peak | Clipped samples | Errors | Sanitized samples | Pitch underruns |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name in factories:
        group=[r for r in rows if r['voice']==name]
        lines.append(f"| {name} | {max(r['p99_ms'] for r in group):.2f} | {max(r['peak'] for r in group):.3f} | {max(r['pre_limiter_peak'] for r in group):.3f} | {sum(r['clipped_samples'] for r in group)} | {sum(r['errors'] for r in group)} | {sum(r['sanitized_samples'] for r in group)} | {sum(r['pitch_underruns'] for r in group)} |")
    lines+=['','Each row combines mono/stereo at 44.1/48 kHz. A 512-frame callback allows 10.67 ms at 48 kHz; scheduling under game load is not covered. A bounded final peak does not mean the upstream chain is transparent. High pre-limiter peaks identify chains needing less input/effect gain. Long tails are intentional in echo/reverb stress cases.']
    (directory/'AUTOMATED_AUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    failures=[r for r in rows if r['errors'] or r['sanitized_samples'] or r['pitch_underruns'] or r['peak']>1.00001]
    print(f'{len(rows)} preset/effect configurations; {len(failures)} stability failures; report: {directory}')
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-dir',type=Path,default=Path('audit-results'))
    run_audit(parser.parse_args().report_dir)
