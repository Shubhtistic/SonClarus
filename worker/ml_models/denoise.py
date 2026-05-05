from df.enhance import enhance, init_df, save_audio, load_audio
import torch
from pathlib import Path
import gc


@torch.no_grad()
def run_denoise(input_path: str, output_folder: Path):

    model, df_state, _ = init_df()
    # load the pre trained model
    # return three values
    # model -> the model itself, df_state -> settings like sample rate , chunk size
    # _ -> 3rd value which we dont need

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    # this moves the model from ram to gpu's vram
    model.to(device)

    audio, info = load_audio(input_path, sr=df_state.sr())
    # reads the file and convert to tensor (a big array of 0's and 1's)
    # sr -> forces to load at exact sample rate -> deepfilter needs 48khz
    # if diff sr is used o/p may be bad

    enhanced_audio = enhance(model=model, df_state=df_state, audio=audio)
    # this is actual work -> sends the noisy network through neural network

    file_name = Path(input_path).stem
    output_path = output_folder / f"{file_name}_cleaned.wav"
    output_folder.mkdir(parents=True, exist_ok=True)
    save_audio(str(output_path), enhanced_audio, df_state.sr())

    model.to("cpu")
    if isinstance(audio, torch.Tensor):
        audio = audio.to("cpu")
    if isinstance(enhanced_audio, torch.Tensor):
        enhanced_audio = enhanced_audio.to("cpu")

    del model
    del df_state
    del audio
    del enhanced_audio
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # return path so next steps know which file to use
    return str(output_path)
