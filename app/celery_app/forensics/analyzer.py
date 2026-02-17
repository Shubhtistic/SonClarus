import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np


def generate_waveform_image(file_path: str, output_path: str):
    # why we did sr=None as librosa shrinks sample rate of file
    # we dont want to shrik sample rate so we do sr=None


    #Also mono = false .. avoid mono conversion
    y, sr = librosa.load(file_path, sr=None, mono=False)

    # Create a wide canvas (10x4 inches)
    plt.figure(figsize=(10, 4))
    # Draw the wave
    librosa.display.waveshow(y, sr=sr, color="blue")
    # Add Forensic Labels
    plt.title("Waveform Analysis") 
    plt.xlabel("Time (seconds)")
    plt.ylabel("Amplitude")

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()  # close immediately

    return output_path

    # tight_layout() -> remove white borders white borders.
    # savefig() -> write file to disk.
    # close() -> this is imp as matpltlib keeps the graph in memory so we need to close it or server will crash after multiple uploads


def generate_spectrogram_image(file_path: str, output_path: str):

    # Load audio again
    y, sr = librosa.load(file_path, sr=None)

    # Convert to Decibels (Loudness)
    D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)

    # The Math (Short-Time Fourier Transform)
    # reason ->  we need to un-mix the sound to see the frequencies

    # stft(y): Breaks sound into frequencies
    # abs(): Gets the strength of the frequency
    # amplitude_to_db: Converts computer numbers to Decibels (dB) because humans hear loudness logarithmically

    plt.figure(figsize=(10, 4))

    # draw heatmap with log scale (match human hearing)
    librosa.display.specshow(D, sr=sr, x_axis="time", y_axis="log")

    plt.colorbar(format="%+2.0f dB")
    plt.title("Spectrogram (Frequency Analysis)")
    plt.tight_layout()

    plt.savefig(output_path)
    plt.close()

    return output_path
