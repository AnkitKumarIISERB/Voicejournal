"""
Multi-modal Fusion Service.

Combines audio-level emotion (WavLM) with text-level sentiment (NLP)
to produce a confidence-weighted final emotion score.

This is the key differentiator — most apps do ONE modality. We do BOTH.
"""

from typing import Dict, Optional


# NLP Sentiment keywords with valence weights
SENTIMENT_KEYWORDS: Dict[str, Dict[str, float]] = {
    "positive": {
        "happy": 0.8, "great": 0.7, "amazing": 0.9, "wonderful": 0.9, "love": 0.8,
        "excited": 0.8, "grateful": 0.7, "blessed": 0.7, "fantastic": 0.9,
        "good": 0.5, "nice": 0.4, "better": 0.4, "proud": 0.6, "beautiful": 0.7,
        "peaceful": 0.6, "calm": 0.5, "joy": 0.9, "hopeful": 0.6, "inspired": 0.7,
    },
    "negative": {
        "sad": -0.7, "depressed": -0.9, "anxious": -0.7, "worried": -0.6,
        "stressed": -0.7, "angry": -0.8, "frustrated": -0.7, "lonely": -0.8,
        "scared": -0.7, "hurt": -0.6, "pain": -0.7, "terrible": -0.8,
        "awful": -0.8, "horrible": -0.9, "crying": -0.7, "exhausted": -0.6,
        "overwhelmed": -0.7, "hopeless": -0.9, "worthless": -0.9, "afraid": -0.7,
    },
}

# Map text sentiment to emotion labels
SENTIMENT_TO_EMOTION = {
    "very_positive": "happy",
    "positive": "calm",
    "neutral": "neutral",
    "negative": "sad",
    "very_negative": "fearful",
}


def analyze_text_sentiment(transcript: str) -> Dict:
    """
    Analyze the sentiment of transcript text using keyword-based NLP.
    Returns a dict with sentiment label, valence, and confidence.
    """
    if not transcript:
        return {"sentiment": "neutral", "valence": 0.0, "confidence": 0.0}

    words = transcript.lower().split()
    pos_score = 0.0
    neg_score = 0.0
    match_count = 0

    for word in words:
        # Strip punctuation
        clean = word.strip(".,!?;:'\"()-")
        if clean in SENTIMENT_KEYWORDS["positive"]:
            pos_score += SENTIMENT_KEYWORDS["positive"][clean]
            match_count += 1
        elif clean in SENTIMENT_KEYWORDS["negative"]:
            neg_score += abs(SENTIMENT_KEYWORDS["negative"][clean])
            match_count += 1

    # Calculate net valence (-1 to 1)
    total = pos_score + neg_score
    if total == 0:
        valence = 0.0
        confidence = 0.1  # Low confidence when no keywords match
    else:
        valence = (pos_score - neg_score) / max(total, 1)
        confidence = min(match_count / max(len(words), 1) * 5, 1.0)  # Scale up

    # Map to sentiment category
    if valence > 0.5:
        sentiment = "very_positive"
    elif valence > 0.1:
        sentiment = "positive"
    elif valence > -0.1:
        sentiment = "neutral"
    elif valence > -0.5:
        sentiment = "negative"
    else:
        sentiment = "very_negative"

    return {
        "sentiment": sentiment,
        "valence": round(valence, 4),
        "confidence": round(confidence, 4),
        "emotion": SENTIMENT_TO_EMOTION.get(sentiment, "neutral"),
    }


def fuse_modalities(
    audio_emotion: str,
    audio_valence: float,
    transcript: str,
    audio_confidence: float = 0.7,
) -> Dict:
    """
    Fuse audio emotion analysis with text sentiment analysis.

    Strategy:
    - When both agree → high confidence, use audio emotion (more nuanced)
    - When they disagree → weighted average favoring the higher-confidence modality
    - Audio typically gets 60% weight (voice tone is harder to fake)
    - Text gets 40% weight (explicit words matter too)
    """
    text_analysis = analyze_text_sentiment(transcript)

    audio_weight = 0.6
    text_weight = 0.4

    # Adjust weights based on confidence
    if text_analysis["confidence"] > audio_confidence:
        audio_weight = 0.4
        text_weight = 0.6

    # Fused valence
    fused_valence = (
        audio_valence * audio_weight + text_analysis["valence"] * text_weight
    )
    fused_valence = max(-1.0, min(1.0, fused_valence))

    # Check agreement
    audio_positive = audio_valence > 0
    text_positive = text_analysis["valence"] > 0
    modalities_agree = audio_positive == text_positive

    # Final emotion — prefer audio when they agree, use text hint when they disagree
    if modalities_agree:
        final_emotion = audio_emotion
        agreement = "aligned"
    else:
        # Disagreement: use the modality with higher confidence
        if audio_confidence >= text_analysis["confidence"]:
            final_emotion = audio_emotion
        else:
            final_emotion = text_analysis["emotion"]
        agreement = "conflicting"

    # Overall confidence
    if modalities_agree:
        fused_confidence = min((audio_confidence + text_analysis["confidence"]) / 1.5, 1.0)
    else:
        fused_confidence = max(audio_confidence, text_analysis["confidence"]) * 0.7

    return {
        "final_emotion": final_emotion,
        "final_valence": round(fused_valence, 4),
        "confidence": round(fused_confidence, 4),
        "agreement": agreement,
        "audio_analysis": {
            "emotion": audio_emotion,
            "valence": audio_valence,
            "weight": audio_weight,
        },
        "text_analysis": {
            "emotion": text_analysis["emotion"],
            "valence": text_analysis["valence"],
            "sentiment": text_analysis["sentiment"],
            "weight": text_weight,
        },
    }
