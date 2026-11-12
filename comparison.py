"""Local, level-matched A/B rendering. No audio is saved automatically."""
import numpy as np
from engine import AudioEngine
from voice_effects import Harmony, FormantShift, Vocoder


def latency_frames(board, rate):
    if hasattr(board, 'latency_frames'):
        return int(board.latency_frames(rate))
    total = 0
    for stage in getattr(board, 'stages', []):
        if isinstance(stage, float) and abs(stage) > .05:
            total += int(rate * .075)
        elif hasattr(stage, 'latency_frames'):
            total += int(stage.latency_frames(rate))
        elif isinstance(stage, Harmony):
            total += int(rate * .075)
        elif isinstance(stage, FormantShift):
            total += 1024
        elif isinstance(stage, Vocoder):
            total += 512
    return total


def level_match(original,processed,rate):
    # Use the same active speech windows for both signals; retain crest factor.
    hop=max(1,int(rate*.02))
    active=np.zeros(len(original),dtype=bool)
    for start in range(0,len(original),hop):
        frame=original[start:start+hop]
        if np.sqrt(np.mean(frame**2))>10**(-50/20):
            active[start:start+hop]=True
    if not active.any():
        return original.copy(),processed.copy(),'Sample is too quiet for reliable level matching.'
    note='RMS level matched using active speech; not a LUFS measurement.'
    if float(np.sqrt(np.mean(processed[active]**2)))<1e-7:
        note='Processed sample is nearly silent. Check the gate threshold and effect settings.'
    result=[]
    for audio in (original,processed):
        rms=float(np.sqrt(np.mean(audio[active]**2)))
        gain=min(12.,10**(-23/20)/max(rms,1e-8))
        result.append(audio*gain)
    peak=max(float(np.max(abs(x))) for x in result)
    reduction=min(1.,.89/max(peak,1e-8))
    return *(np.asarray(x*reduction,dtype=np.float32) for x in result), note


def render_comparison(raw,rate,builder):
    raw=np.asarray(raw,dtype=np.float32).reshape(-1)
    if len(raw)<int(rate*.25):
        raise ValueError('Record at least a quarter of a second.')
    if not np.isfinite(raw).all():
        raise ValueError('Recording contains invalid samples.')
    engine=AudioEngine(sample_rate=rate,blocksize=512)
    board=builder()
    engine.set_voice(board)
    latency=latency_frames(board,rate)
    original=np.pad(raw,(0,int(rate*2)))
    source=np.pad(original,(0,latency))
    chunks=[]
    for offset in range(0,len(source),512):
        block=source[offset:offset+512,None]
        out=np.zeros_like(block)
        engine._audio_callback(block,out,len(block),None,None)
        if engine.last_error:
            raise RuntimeError(engine.last_error)
        chunks.append(out[:,0])
    processed=np.concatenate(chunks)[latency:latency+len(original)]
    return level_match(original,processed,rate)
