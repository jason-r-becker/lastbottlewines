"""Wine scoring logic using LLM"""

import re
from typing import Optional, Dict
import google.genai as genai
from google.genai.types import GenerateContentConfig


def score_wine(prompt: str) -> Optional[int]:
    """
    Use an LLM to score wine based on user preferences.

    Args:
        prompt: The prompt to send to the LLM

    Returns:
        Score from 0-100, or None if no valid score found
    """
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=GenerateContentConfig(temperature=0.2),
    )

    # The last line of the response should be the median score
    response_text = response.text.strip()
    last_line = response_text.splitlines()[-1].strip()
    match = re.search(r"\b(\d{1,3})\b", last_line)
    if match:
        score = int(match.group(1))
        if 0 <= score <= 100:
            return score

    return None


def generate_wine_scoring_prompt(wine_name: str, config: Dict) -> str:
    """Generate a prompt for wine scoring based on user preferences"""

    # Extract preferences from config
    preferred_types = ", ".join(config.get("types", []))
    price_range = config.get("price_range", [None, None])
    type_specific_ranges = config.get("type_specific_price_ranges", {})
    always_notify = config.get("always_notify_for", [])
    never_notify = config.get("never_notify_for", [])
    profile = config.get("profile", "").strip()

    # Build the prompt
    prompt = f"""You are a wine expert evaluating a wine based on user preferences.
Think carefully and critically about how well this wine matches the user's
profile and preferences. Consider the grape variety, region, vintage,
production style, and how these align with what the user is looking for.

## User Wine Preferences:

{profile}

## Preferred Wine Types:
{preferred_types}

## Price Range Preference:
${price_range[0] if price_range[0] else "Any"} - ${price_range[1] if price_range[1] else "Any"}

## Type-Specific Price Ranges:
{format_type_specific_ranges(type_specific_ranges) if type_specific_ranges else "None specified"}

## Always notify (if the wine contains any of these names, score 100):
{", ".join(always_notify) if always_notify else "None specified"}

## Always avoid (if the wine matches any of these categories, score 0):
{", ".join(never_notify) if never_notify else "None specified"}

---

## Wine to Score:
{wine_name}

## Scoring guidelines:
- 90-100: Near-perfect match — wine type, style, region, and price all align
- 80-89: Strong match — most preferences met, minor gaps
- 70-79: Good match, worth considering
- 60-69: Moderate — some preferences met, notable gaps
- 50-59: Weak — few preferences met
- 0-49: Poor match for preferences

## Instructions:
1. Reason step by step about how well this wine matches the user's preferences.
2. Produce 5 independent scores (do not output them).
3. Output ONLY the median of those 5 scores as a single integer. No other text."""

    return prompt


def format_type_specific_ranges(type_ranges: Dict) -> str:
    """Format type-specific price ranges for display"""
    lines = []
    for wine_type, price_range in type_ranges.items():
        min_price = price_range[0] if price_range[0] else "Any"
        max_price = price_range[1] if price_range[1] else "Any"
        lines.append(f"  - {wine_type}: ${min_price} - ${max_price}")
    return "\n".join(lines)
