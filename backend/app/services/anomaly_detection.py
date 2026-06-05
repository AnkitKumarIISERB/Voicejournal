"""
Anomaly Detection & Crisis Alert Service.

Monitors mood patterns for sudden drops and prolonged negative trends.
Triggers helpline information when crisis indicators are detected.

This is an ethical AI feature that shows responsibility in design.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.journal import JournalEntry


# Crisis helpline numbers (India-focused, add more for deployment)
CRISIS_HELPLINES = {
    "india": {
        "name": "iCall",
        "number": "9152987821",
        "description": "Professional counseling helpline (Mon-Sat, 8am-10pm IST)",
    },
    "vandrevala": {
        "name": "Vandrevala Foundation",
        "number": "1860-2662-345",
        "description": "24/7 mental health helpline",
    },
    "international": {
        "name": "Crisis Text Line",
        "number": "Text HOME to 741741",
        "description": "Free 24/7 crisis counseling via text",
    },
}


def check_mood_anomaly(
    db: Session, user_id: int, current_valence: float, current_emotion: str
) -> Dict:
    """
    Check if the user's current mood entry represents an anomaly
    compared to their recent patterns.

    Triggers:
    1. Sudden Drop: Current valence is > 0.5 below 7-day average
    2. Sustained Low: Last 3+ entries are all below -0.3
    3. Crisis Keywords: Emotion is 'fearful' or valence < -0.7
    """
    # Get last 7 days of entries
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent_entries = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == user_id,
            JournalEntry.created_at >= cutoff,
            JournalEntry.valence_score.isnot(None),
        )
        .order_by(JournalEntry.created_at.desc())
        .all()
    )

    result = {
        "is_anomaly": False,
        "alert_level": "none",  # none, mild, moderate, crisis
        "triggers": [],
        "message": None,
        "helplines": None,
        "recommendations": [],
    }

    if len(recent_entries) < 2:
        return result

    valences = [e.valence_score for e in recent_entries]
    avg_valence = sum(valences) / len(valences)

    # Check 1: Sudden Drop
    drop = avg_valence - current_valence
    if drop > 0.5:
        result["is_anomaly"] = True
        result["triggers"].append(f"sudden_drop ({drop:.2f} below your average)")
        result["alert_level"] = "moderate"

    # Check 2: Sustained Low (last 3 entries all negative)
    last_3 = valences[:3] + [current_valence]
    if all(v < -0.3 for v in last_3[:3]):
        result["is_anomaly"] = True
        result["triggers"].append("sustained_low (3+ consecutive negative entries)")
        result["alert_level"] = "moderate"

    # Check 3: Crisis level
    if current_valence < -0.7 or current_emotion in ("fearful", "disgust"):
        result["is_anomaly"] = True
        result["triggers"].append("crisis_indicator (very low valence or distress emotion)")
        result["alert_level"] = "crisis"

    # Build response based on alert level
    if result["alert_level"] == "crisis":
        result["message"] = (
            "We noticed you might be going through a really tough time. "
            "You're not alone — reaching out is a sign of strength. "
            "Here are some resources that can help:"
        )
        result["helplines"] = CRISIS_HELPLINES
        result["recommendations"] = [
            "Consider talking to someone you trust",
            "Take a few deep breaths — 4 seconds in, 7 seconds hold, 8 seconds out",
            "Remember: this feeling is temporary, and help is available",
        ]
    elif result["alert_level"] == "moderate":
        result["message"] = (
            "Your mood has been lower than usual recently. "
            "It's okay to have tough days. Here are some things that might help:"
        )
        result["recommendations"] = [
            "Try a short walk or gentle exercise",
            "Write down 3 things you're grateful for",
            "Reach out to a friend or family member",
            "Consider speaking with a counselor if this persists",
        ]
        result["helplines"] = {"vandrevala": CRISIS_HELPLINES["vandrevala"]}

    return result


def get_mood_streak(db: Session, user_id: int) -> Dict:
    """
    Calculate the user's journaling streak and mood patterns.
    Used for gamification features.
    """
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user_id)
        .order_by(JournalEntry.created_at.desc())
        .all()
    )

    if not entries:
        return {"current_streak": 0, "longest_streak": 0, "total_entries": 0}

    # Calculate streak (consecutive days with entries)
    today = datetime.now(timezone.utc).date()
    dates_with_entries = set()
    for e in entries:
        dates_with_entries.add(e.created_at.date())

    current_streak = 0
    check_date = today
    while check_date in dates_with_entries:
        current_streak += 1
        check_date -= timedelta(days=1)

    # Calculate longest streak
    sorted_dates = sorted(dates_with_entries)
    longest_streak = 1
    temp_streak = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            temp_streak += 1
            longest_streak = max(longest_streak, temp_streak)
        else:
            temp_streak = 1

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "total_entries": len(entries),
        "total_days": len(dates_with_entries),
    }
