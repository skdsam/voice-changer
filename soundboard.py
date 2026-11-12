"""Soundboard clip storage, validation, and processed audio import/export."""
import os
import re
import shutil
import numpy as np
from pedalboard import Resample
from pedalboard.io import AudioFile
from comparison import latency_frames

SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "sounds")
SUPPORTED_SOUND_EXTS = (".wav", ".mp3", ".flac", ".ogg", ".aiff")


def _safe_stem(text):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", (text or "").strip()).strip(". ")
    return (cleaned or "clip")[:80]


def inspect_audio_file(path):
    """Validate readability and return metadata {samplerate, channels, frames, duration_sec}."""
    with AudioFile(path) as reader:
        sr = int(reader.samplerate)
        channels = int(reader.num_channels)
        frames = int(reader.frames)
        if sr <= 0 or frames <= 0:
            raise ValueError("Audio file contains no audio samples.")
    return {
        "samplerate": sr,
        "channels": channels,
        "frames": frames,
        "duration_sec": frames / float(sr),
    }


def list_sound_clips(directory=None):
    """Return sorted soundboard clips in the sounds directory without creating empty folders."""
    folder = directory or SOUNDS_DIR
    if not os.path.isdir(folder):
        return []
    clips = []
    for entry in sorted(os.listdir(folder), key=str.lower):
        full = os.path.join(folder, entry)
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(entry)[1].lower()
        if ext not in SUPPORTED_SOUND_EXTS:
            continue
        try:
            meta = inspect_audio_file(full)
        except Exception:
            continue
        clips.append({
            "name": os.path.splitext(entry)[0],
            "filename": entry,
            "path": full,
            "ext": ext,
            "duration_sec": meta["duration_sec"],
            "samplerate": meta["samplerate"],
            "channels": meta["channels"],
            "size_kb": max(1, os.path.getsize(full) // 1024),
        })
    return clips


def import_sound_clip(src_path, directory=None, conflict="rename", clip_name=None):
    """Validate and copy a sound file (.wav/.mp3/.flac/.ogg/.aiff) into the local soundboard."""
    if not os.path.isfile(src_path):
        raise ValueError("Selected sound file does not exist.")
    ext = os.path.splitext(src_path)[1].lower()
    if ext not in SUPPORTED_SOUND_EXTS:
        raise ValueError(f"Unsupported audio format '{ext}'. Supported: {', '.join(SUPPORTED_SOUND_EXTS)}")
    meta = inspect_audio_file(src_path)
    folder = directory or SOUNDS_DIR
    os.makedirs(folder, exist_ok=True)
    stem = _safe_stem(clip_name if clip_name is not None else os.path.splitext(os.path.basename(src_path))[0])
    dest = os.path.join(folder, f"{stem}{ext}")
    if conflict != "overwrite":
        idx = 2
        while os.path.exists(dest):
            dest = os.path.join(folder, f"{stem} ({idx}){ext}")
            idx += 1
    shutil.copy2(src_path, dest)
    return {
        "name": os.path.splitext(os.path.basename(dest))[0],
        "filename": os.path.basename(dest),
        "path": dest,
        "ext": ext,
        "duration_sec": meta["duration_sec"],
        "samplerate": meta["samplerate"],
        "channels": meta["channels"],
        "size_kb": max(1, os.path.getsize(dest) // 1024),
    }


def export_sound_clip(src_path, dest_path):
    """Copy a soundboard clip to a user-chosen destination for sharing."""
    if not os.path.isfile(src_path):
        raise ValueError("Sound clip file could not be found.")
    dest_dir = os.path.dirname(os.path.abspath(dest_path)) or "."
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(src_path, dest_path)
    return dest_path


def delete_sound_clip(clip_path, directory=None):
    """Remove a clip stored inside the managed sounds directory."""
    folder = os.path.abspath(directory or SOUNDS_DIR)
    target = os.path.abspath(clip_path)
    if os.path.commonpath([folder, target]) != folder or not os.path.isfile(target):
        raise ValueError("Clip cannot be deleted outside the managed sounds folder.")
    os.unlink(target)


def export_processed_audio(src_path, voice_builder, dest_path, sample_rate=44100, blocksize=512):
    """Render an audio clip through a voice builder chain cleanly and write to dest_path."""
    from voice_effects import SoftCeilingLimiter
    with AudioFile(src_path) as reader:
        src_sr = int(reader.samplerate)
        audio = reader.read(reader.frames).astype(np.float32)
    if audio.shape[0] > 2:
        audio = audio[:2]
    if src_sr != sample_rate:
        audio = Resample(target_sample_rate=sample_rate)(audio, sample_rate=src_sr).astype(np.float32)

    board = voice_builder()
    channels = audio.shape[0]
    lead_latency = latency_frames(board, sample_rate)
    tail = int(sample_rate * 0.45)
    padded = np.concatenate((audio, np.zeros((channels, lead_latency + tail), dtype=np.float32)), axis=1)
    board.reset()
    limiter = SoftCeilingLimiter(threshold=0.75, ceiling=0.97)
    chunks = []
    for offset in range(0, padded.shape[1], blocksize):
        block = padded[:, offset:offset + blocksize]
        if block.shape[1] < blocksize:
            pad_n = blocksize - block.shape[1]
            block = np.concatenate((block, np.zeros((channels, pad_n), dtype=np.float32)), axis=1)
        out = board(block, sample_rate, reset=False) if len(board) > 0 else block
        out = limiter(out, sample_rate, reset=False)
        chunks.append(np.clip(np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0))

    rendered = np.concatenate(chunks, axis=1)
    start = min(lead_latency, max(0, rendered.shape[1] - audio.shape[1]))
    trimmed = rendered[:, start:start + audio.shape[1] + int(sample_rate * 0.25)]
    dest_dir = os.path.dirname(os.path.abspath(dest_path)) or "."
    os.makedirs(dest_dir, exist_ok=True)
    with AudioFile(dest_path, "w", samplerate=sample_rate, num_channels=channels) as writer:
        writer.write(trimmed.astype(np.float32))
    return dest_path

