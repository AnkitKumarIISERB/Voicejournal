import librosa
import numpy as np

def extract_acoustic_features(audio_path: str):
    """
    Deterministically extracts clinically relevant acoustic features.
    These features act as explainable markers for depression/mood state.
    """
    try:
        y, sr = librosa.load(audio_path, sr=16000)
        
        # 1. Pitch Variance (F0)
        # Flat affect (low pitch variance) is a strong marker of depression.
        # Use pyin for accurate fundamental frequency extraction
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        valid_f0 = f0[voiced_flag]
        pitch_variance = float(np.var(valid_f0)) if len(valid_f0) > 0 else 0.0
        
        # 2. Energy Variance (RMS)
        # Lethargy often manifests as low variance in vocal energy
        rms = librosa.feature.rms(y=y)[0]
        energy_variance = float(np.var(rms))
        
        # 3. Estimated Speech Rate
        # A simple heuristic: count energy peaks as syllables to estimate rate
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        peaks = librosa.util.peak_pick(onset_env, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.5, wait=10)
        duration = librosa.get_duration(y=y, sr=sr)
        speech_rate = float(len(peaks) / duration) if duration > 0 else 0.0
        
        return {
            "pitch_variance": round(pitch_variance, 4),
            "energy_variance": round(energy_variance, 6),
            "speech_rate": round(speech_rate, 4)
        }
    except Exception as e:
        print(f"Error extracting DSP features: {e}")
        return {
            "pitch_variance": 0.0,
            "energy_variance": 0.0,
            "speech_rate": 0.0
        }
