import gc
import torch
from faster_whisper import WhisperModel


@torch.no_grad()
def run_transcription(input_path: str, speaker_name: str):
    model = WhisperModel("base", device="cuda", compute_type="int8")
    segments, info = model.transcribe(input_path, beam_size=5)

    transcript_data = []

    for segment in segments:
        if segment.text.strip():
            transcript_data.append(
                {
                    "speaker": speaker_name,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                }
            )

    del model
    del segments
    del info
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return transcript_data
