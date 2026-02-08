"""Wine scoring logic using LLM"""

import re
from typing import Optional, Dict
import google.genai as genai


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
        model="gemini-2.5-flash-lite", contents=prompt
    )

    # Extract the score from the response
    response_text = response.text.strip()
    scores = re.findall(r"\b([0-9]{1,3})\b", response_text)
    for score_str in scores:
        score = int(score_str)
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
    prompt = f"""

You are a wine expert evaluating a wine based on user preferences.
Think deeply and critically about how well this wine matches the user's
profile and preferences. Based on the following wine preferences, 
evaluate and score a wine on a scale of 0-100.

## User Wine Preferences:

{profile}

## Preferred Wine Types:
{preferred_types}

## Price Range Preference:
${price_range[0] if price_range[0] else "Any"} - ${price_range[1] if price_range[1] else "Any"}

## Type-Specific Price Ranges:
{format_type_specific_ranges(type_specific_ranges) if type_specific_ranges else "None specified"}

## Always a perfect score of 100 (regardless of other factors):
{", ".join(always_notify) if always_notify else "None specified"}

## Always Avoid (Red Flags):
{", ".join(never_notify) if never_notify else "None specified"}

---

## Wine to Score:
{wine_name}
Please provide:

1. A score from 0-100 based on how well this wine matches the user's preferences

Scoring guidelines:
- 90-100: Perfect match for preferences
- 80-89: Excellent fit, highly recommended
- 70-79: Good match, worth trying
- 60-69: Acceptable but some concerns
- 50-59: Mixed - some elements good, others not ideal
- 0-49: Poor match for preferences

Return only the score as a integer number between 0, and 100, with
no other text or explanation.
"""

    return prompt


def format_type_specific_ranges(type_ranges: Dict) -> str:
    """Format type-specific price ranges for display"""
    lines = []
    for wine_type, price_range in type_ranges.items():
        min_price = price_range[0] if price_range[0] else "Any"
        max_price = price_range[1] if price_range[1] else "Any"
        lines.append(f"  - {wine_type}: ${min_price} - ${max_price}")
    return "\n".join(lines)
