"""Render every preset on one recording for repeatable listening comparisons.
Usage: python render_previews.py path/to/speech.wav --output previews
"""
import argparse
from pathlib import Path
import re
import wave
import numpy as np
from pedalboard.io import AudioFile
from engine import AudioEngine
from voices import VOICE_PRESETS


def render(source, output):
    output.mkdir(parents=True, exist_ok=True)
    with AudioFile(str(source)) as file:
        rate = int(file.samplerate)
        audio = file.read(file.frames).mean(axis=0)
    # Allow delayed speech and short ambience tails to finish.
    audio = np.pad(audio, (0, rate * 2))
    for name, preset in VOICE_PRESETS.items():
        engine = AudioEngine(sample_rate=rate, blocksize=512)
        engine.set_voice(preset['builder']())
        blocks = []
        for offset in range(0, len(audio), 512):
            block = audio[offset:offset+512, None].astype(np.float32)
            result = np.zeros_like(block)
            engine._audio_callback(block, result, len(block), None, None)
            if engine.last_error:
                raise RuntimeError(f'{name}: {engine.last_error}')
            blocks.append(result[:, 0])
        result = np.concatenate(blocks)
        path = output / (re.sub(r'[^\w-]+', '_', name).strip('_') + '.wav')
        with wave.open(str(path), 'wb') as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(rate)
            target.writeframes((np.clip(result, -1, 1) * 32767).astype('<i2').tobytes())
        print(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path('previews'))
    args = parser.parse_args()
    render(args.source, args.output)
