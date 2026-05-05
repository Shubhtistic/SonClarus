import gc
import torch
import torchaudio
from speechbrain.inference.separation import SepformerSeparation
from pathlib import Path


@torch.no_grad()
def run_separation(input_path: str, output_folder: Path):
    device_str = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = SepformerSeparation.from_hparams(
        source="speechbrain/sepformer-wsj02mix",
        savedir="pretrained_models/sepformer-wsj02mix",
        run_opts={"device": device_str},
    )

    # loads audio, resamples to 8khz
    audio, sr = torchaudio.load(input_path)
    if sr != 8000:
        audio = torchaudio.functional.resample(audio, orig_freq=sr, new_freq=8000)

    # Convert to mono if stereo
    if audio.shape[0] > 1:
        audio = torch.mean(audio, dim=0, keepdim=True)

    file_name = Path(input_path).stem

    out_paths = []
    output_folder.mkdir(parents=True, exist_ok=True)

    chunk_size = 120000
    chunks = torch.split(audio, chunk_size, dim=1)

    speaker_1_chunks = []
    speaker_2_chunks = []

    for chunk in chunks:
        chunk = chunk.to(device_str)
        sources = model.separate_batch(chunk)

        # sources.shape[-1] looks at the last dimension of the tensor (number of speaker -> 2)
        # Slice the tensor -> grab all batches, all time, but only speaker "i"
        # .detach().cpu() -> critical, pulls data from gpu's vram into system ram
        speaker_1_chunks.append(sources[0, :, 0].detach().cpu())
        speaker_2_chunks.append(sources[0, :, 1].detach().cpu())

        del chunk
        del sources
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Stitch the detached tensors back into full audio files
    speaker_1_full = torch.cat(speaker_1_chunks, dim=0).unsqueeze(0)
    speaker_2_full = torch.cat(speaker_2_chunks, dim=0).unsqueeze(0)

    out_path_1 = output_folder / f"{file_name}_speaker_1.wav"
    out_path_2 = output_folder / f"{file_name}_speaker_2.wav"

    # save the file, sepformers internal sample rate of 8khz
    torchaudio.save(str(out_path_1), speaker_1_full, sample_rate=8000)
    torchaudio.save(str(out_path_2), speaker_2_full, sample_rate=8000)

    out_paths.extend([str(out_path_1), str(out_path_2)])

    # Final cleanup
    model.to("cpu")
    del model
    del audio
    del speaker_1_full
    del speaker_2_full
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return out_paths
