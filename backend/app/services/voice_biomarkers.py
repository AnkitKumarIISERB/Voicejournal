"""
Voice Biomarker Extraction Service.

Extracts clinical-grade voice features from audio:
- Pitch (F0): Fundamental frequency — correlates with emotional arousal
- Energy (RMS): Volume/intensity — low energy → depression indicator
- Speaking Rate: Words per minute — fast → anxiety, slow → depression
- Pause Duration: Silence ratio — more pauses → cognitive load or sadness
- Jitter/Shimmer: Voice stability — instability → stress indicators

These are the SAME features used in real clinical depression screening tools.
"""

import numpy as np
import librosa
from typing import Dict, Optional


def extract_biomarkers(audio_path: str, transcript: Optional[str] = None) -> Dict:
    """
    Extract voice biomarkers from an audio file.
    
    Args:
        audio_path: Path to the audio file (WAV, MP3, etc.)
        transcript: Optional transcript for speaking rate calculation
    
    Returns:
        Dictionary of biomarker values with clinical interpretations
    """
    try:
        # Load audio
        y, sr = librosa.load(audio_path, sr=16000)
        duration = librosa.get_duration(y=y, sr=sr)
        
        if duration < 1.0:
            return _empty_biomarkers("Audio too short for analysis")
        
        # 1. Pitch (F0) Analysis
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y, fmin=60, fmax=500, sr=sr
        )
        f0_clean = f0[~np.isnan(f0)] if f0 is not None else np.array([])
        
        pitch_mean = float(np.mean(f0_clean)) if len(f0_clean) > 0 else 0.0
        pitch_std = float(np.std(f0_clean)) if len(f0_clean) > 0 else 0.0
        pitch_range = float(np.ptp(f0_clean)) if len(f0_clean) > 0 else 0.0
        
        # 2. Energy (RMS) Analysis
        rms = librosa.feature.rms(y=y)[0]
        energy_mean = float(np.mean(rms))
        energy_std = float(np.std(rms))
        energy_max = float(np.max(rms))
        
        # 3. Speaking Rate (requires transcript)
        word_count = len(transcript.split()) if transcript else 0
        speaking_rate = (word_count / duration) * 60 if duration > 0 and transcript else 0.0  # WPM
        
        # 4. Pause Analysis
        # Detect silence periods (below 20% of mean energy)
        silence_threshold = energy_mean * 0.2
        is_silence = rms < silence_threshold
        silence_ratio = float(np.mean(is_silence))
        
        # Count distinct pauses
        pause_transitions = np.diff(is_silence.astype(int))
        num_pauses = int(np.sum(pause_transitions == 1))
        
        # 5. Jitter (pitch perturbation) — voice stability
        jitter = 0.0
        if len(f0_clean) > 1:
            diffs = np.abs(np.diff(f0_clean))
            jitter = float(np.mean(diffs) / np.mean(f0_clean)) if np.mean(f0_clean) > 0 else 0.0
        
        # 6. Shimmer (amplitude perturbation)
        shimmer = 0.0
        if len(rms) > 1:
            amp_diffs = np.abs(np.diff(rms))
            shimmer = float(np.mean(amp_diffs) / np.mean(rms)) if np.mean(rms) > 0 else 0.0
        
        # 7. Spectral features
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spectral_mean = float(np.mean(spectral_centroid))
        
        # Clinical interpretations
        interpretations = _interpret_biomarkers(
            pitch_mean, pitch_std, energy_mean, speaking_rate,
            silence_ratio, jitter, shimmer
        )
        
        return {
            "duration_seconds": round(duration, 2),
            "pitch": {
                "mean_hz": round(pitch_mean, 2),
                "std_hz": round(pitch_std, 2),
                "range_hz": round(pitch_range, 2),
                "interpretation": interpretations["pitch"],
            },
            "energy": {
                "mean": round(energy_mean, 6),
                "std": round(energy_std, 6),
                "max": round(energy_max, 6),
                "interpretation": interpretations["energy"],
            },
            "speaking_rate": {
                "wpm": round(speaking_rate, 1),
                "word_count": word_count,
                "interpretation": interpretations["speaking_rate"],
            },
            "pauses": {
                "count": num_pauses,
                "silence_ratio": round(silence_ratio, 4),
                "interpretation": interpretations["pauses"],
            },
            "voice_quality": {
                "jitter": round(jitter, 6),
                "shimmer": round(shimmer, 6),
                "interpretation": interpretations["voice_quality"],
            },
            "spectral": {
                "centroid_mean": round(spectral_mean, 2),
            },
            "overall_assessment": interpretations["overall"],
        }
        
    except Exception as e:
        return _empty_biomarkers(f"Analysis error: {str(e)}")


def _interpret_biomarkers(
    pitch_mean: float, pitch_std: float, energy_mean: float,
    speaking_rate: float, silence_ratio: float, jitter: float, shimmer: float
) -> Dict[str, str]:
    """Generate clinical-style interpretations of biomarker values."""
    
    interpretations = {}
    flags = []
    
    # Pitch interpretation
    if pitch_mean < 100:
        interpretations["pitch"] = "Low pitch — may indicate low energy or sadness"
        flags.append("low_pitch")
    elif pitch_mean > 250:
        interpretations["pitch"] = "High pitch — may indicate excitement or anxiety"
        flags.append("high_pitch")
    elif pitch_std < 20:
        interpretations["pitch"] = "Monotone speech — limited emotional expression"
        flags.append("monotone")
    else:
        interpretations["pitch"] = "Normal pitch variation — healthy emotional expression"
    
    # Energy interpretation
    if energy_mean < 0.01:
        interpretations["energy"] = "Very low energy — may indicate fatigue or depression"
        flags.append("low_energy")
    elif energy_mean > 0.1:
        interpretations["energy"] = "High energy — may indicate excitement or agitation"
    else:
        interpretations["energy"] = "Normal energy levels"
    
    # Speaking rate
    if speaking_rate > 0:
        if speaking_rate < 100:
            interpretations["speaking_rate"] = "Slow speech — may indicate depression or careful thought"
            flags.append("slow_speech")
        elif speaking_rate > 180:
            interpretations["speaking_rate"] = "Fast speech — may indicate anxiety or excitement"
            flags.append("fast_speech")
        else:
            interpretations["speaking_rate"] = "Normal speaking rate (120-150 WPM typical)"
    else:
        interpretations["speaking_rate"] = "Speaking rate unavailable (no transcript)"
    
    # Pause analysis
    if silence_ratio > 0.5:
        interpretations["pauses"] = "Frequent pauses — may indicate cognitive load or hesitancy"
        flags.append("many_pauses")
    elif silence_ratio < 0.1:
        interpretations["pauses"] = "Very few pauses — rapid, continuous speech"
    else:
        interpretations["pauses"] = "Normal pause patterns"
    
    # Voice quality
    if jitter > 0.02 or shimmer > 0.1:
        interpretations["voice_quality"] = "Voice instability detected — may indicate stress or emotional distress"
        flags.append("voice_instability")
    else:
        interpretations["voice_quality"] = "Stable voice quality"
    
    # Overall assessment
    if len(flags) >= 3:
        interpretations["overall"] = "Multiple indicators suggest emotional distress. Consider checking in."
    elif len(flags) >= 1:
        interpretations["overall"] = "Some indicators of emotional variation detected."
    else:
        interpretations["overall"] = "Voice patterns appear within normal ranges."
    
    return interpretations


def _empty_biomarkers(reason: str) -> Dict:
    """Return empty biomarker structure with error reason."""
    return {
        "error": reason,
        "duration_seconds": 0,
        "pitch": {"mean_hz": 0, "std_hz": 0, "range_hz": 0, "interpretation": "N/A"},
        "energy": {"mean": 0, "std": 0, "max": 0, "interpretation": "N/A"},
        "speaking_rate": {"wpm": 0, "word_count": 0, "interpretation": "N/A"},
        "pauses": {"count": 0, "silence_ratio": 0, "interpretation": "N/A"},
        "voice_quality": {"jitter": 0, "shimmer": 0, "interpretation": "N/A"},
        "spectral": {"centroid_mean": 0},
        "overall_assessment": reason,
    }
