import hashlib
import os
import soundfile as sf


def compute_sha256(file_path: str) -> str:
    """
    We read a file in 4kb chunsk to avoid server crash
    Why chunks?
    If a user uploads a 2gb file, reading it all at once (f.read())
    would crash the server's RAM. Chunks allow us to process file of any size
    """
    sha256_hash = hashlib.sha256()

    # rb -> audio files are bytes
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def get_audio_metadata(file_path: str) -> dict:
    """
    reads the audio files headers
    Audio headers are data blocks at the beginning of audio files (like MP3, WAV, AU)
    containing essential metadata—format, bitrate, sample rate,
    and channels—that allow players to interpret and play the sound correctly.
    """

    info = sf.info(file_path)

    file_size_bytes = os.path.getsize(file_path)

    return {
        "filename": os.path.basename(file_path),
        "filesize_mb": round(file_size_bytes / (1024 * 1024), 2),
        "duration_sec": round(info.duration, 2),
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "format": info.format,
        "subtype": info.subtype,
    }
