from typing import List, Dict
from groq import AsyncGroq
from app.core.config import settings

async def generate_weekly_summary(entries_data: list) -> str:
    """
    Generate a personalized weekly summary using Groq API.
    """
    if not entries_data:
        return "You haven't recorded any journal entries this week. Take a moment to record your thoughts!"
        
    if not settings.GROQ_API_KEY:
        # Fallback if no API key
        return f"You've recorded {len(entries_data)} entries this week. Please set GROQ_API_KEY for AI summaries."

    # Format data for prompt
    context = "Weekly Journal Entries:\n"
    for entry in entries_data:
        # Some entries might not have a transcript yet if they are still processing
        if not entry.get("emotion_label"):
            continue
        context += f"- Date: {entry.get('created_at', '')}, Emotion: {entry.get('emotion_label', '')}, Valence: {entry.get('valence_score', 0)}, Content: '{entry.get('transcript', '')}'\n"

    prompt = """You are an empathetic, insightful mental health companion.
Write a short, uplifting paragraph (max 4 sentences) summarizing their week.
Focus on emotional patterns, validate their feelings, and offer a gentle piece of encouragement.
Address the user directly as "you". Do not use bullet points or formal sign-offs.
"""

    try:
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        response = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.4,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq API error: {e}")
        return f"You've had a reflective week with {len(entries_data)} entries. Keep journaling!"
