"""Groq chat-completion client for cautious lab-value observations."""

import os
from pathlib import Path
import re

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"

SECTION_HEADINGS = (
    "Glucose",
    "Haemoglobin",
    "Cholesterol",
    "Overall Summary and Recommendation",
)

SYSTEM_PROMPT = """Assess the three numeric results and produce concise, patient-specific preliminary
observations. Only the three values are provided: units, fasting status, sex, symptoms, age, and
lab reference intervals are unknown. Use conventional units only conditionally: glucose and
total cholesterol in mg/dL, haemoglobin in g/dL. For glucose, values below 70 mg/dL may indicate
low blood glucose; 70-99 mg/dL is below the common fasting elevated-glucose threshold, fasting
values of 100-125 may indicate impaired fasting glucose, fasting values of 126 or higher merit
follow-up, and random values of 200 or higher are a concern that
needs clinical confirmation. Never diagnose diabetes from one value. Never call this patient's
test fasting or random, and never state a unit as known; phrase any unit-dependent interpretation
as conditional (for example, "If this is mg/dL..."). For haemoglobin in g/dL, common adult
reference intervals are approximately 13-18 for males and 12-16 for females; low values may be
consistent with anaemia and values above the relevant interval may need evaluation. Interpretation
depends on sex and the lab range. For total cholesterol, below 200 mg/dL is generally desirable,
200-239 may be borderline high and 240 or higher high; high total cholesterol can be associated with increased long-term heart and
stroke risk, but it is not enough to calculate an individual's risk. Assess the actual supplied
numbers against these conditional cues: do not just repeat numbers, and do not call a value
abnormal when its unit/context makes that unsupported. Do not invent a diagnosis or claim
certainty. Name a supported possible concern directly (for example, possible hyperglycemia for
elevated glucose, possible low blood glucose for a low result, possible anaemia for low
haemoglobin, or increased cardiovascular risk associated with high total cholesterol). Do not
state that the patient has any disease. Keep each of the first three sections to one concise
sentence naming the possible concern when supported. For values not crossing a concern threshold,
explain how that actual value relates to the nearest relevant threshold; do not use a generic
"no clear concern" statement by itself. Say "If expressed in mg/dL" before glucose thresholds,
"If expressed in g/dL" before haemoglobin thresholds and "If
this is total cholesterol in mg/dL" before cholesterol thresholds. In the final section use at
most two short sentences, mention once that units,
fasting status, sex, and lab ranges can change interpretation, then recommend professional
follow-up. Return only four sections with exactly these headings on separate lines: Glucose,
Haemoglobin, Cholesterol, Overall Summary and Recommendation. Include the corresponding supplied
number in each of the first three observations. Do not describe glucose as being in a fasting
range or as a random test because test timing is unknown. No preamble, extra heading, model label,
or link."""


def generate_assessment(glucose, haemoglobin, cholesterol):
    """Call Groq with lab values only; return (assessment, error_message)."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None, "AI assessment unavailable: GROQ_API_KEY is not configured."

    user_prompt = (
        "Assess these patient-specific test values using the required cautious rules.\n"
        f"Glucose: {glucose}\n"
        f"Haemoglobin: {haemoglobin}\n"
        f"Cholesterol: {cholesterol}"
    )
    try:
        response = requests.post(
            GROQ_CHAT_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "reasoning_effort": "low",
                "max_completion_tokens": 1200,
            },
            timeout=30,
        )
    except requests.Timeout:
        return None, "AI assessment unavailable: Groq did not respond before the request timed out."
    except requests.RequestException:
        return None, "AI assessment unavailable: Groq could not be reached. Please try again later."

    if response.status_code in (401, 403):
        return None, "AI assessment unavailable: Groq rejected the API key. Check GROQ_API_KEY in .env."
    if response.status_code == 429:
        return None, "AI assessment unavailable: Groq rate limit or quota was reached. Please try again later."
    if not response.ok:
        return None, f"AI assessment unavailable: Groq returned HTTP {response.status_code}."

    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        return None, "AI assessment unavailable: Groq returned an unexpected or empty response."

    if not isinstance(content, str) or not content.strip():
        return None, "AI assessment unavailable: Groq returned an empty assessment."
    formatted = format_assessment(content, glucose, haemoglobin, cholesterol)
    if formatted is None:
        return None, "Groq returned an incomplete assessment. Please try again."
    return formatted, None


def format_assessment(content, glucose, haemoglobin, cholesterol):
    """Normalize model output to exactly the four required sections, or return None."""
    content = re.sub(r"\*\*(.*?)\*\*", r"\1", content.strip())
    content = re.sub(r"(?m)^\s*#{1,6}\s*", "", content)
    aliases = {
        "glucose": "Glucose",
        "haemoglobin": "Haemoglobin",
        "cholesterol": "Cholesterol",
        "overall summary": "Overall Summary and Recommendation",
        "overall summary and recommendation": "Overall Summary and Recommendation",
    }
    sections = {}
    current = None
    for line in content.splitlines():
        heading_line = re.sub(r"^\s*(?:\d+[.)]\s*|[-*]\s*)", "", line.strip())
        match = re.match(
            r"^(Overall Summary and Recommendation|Overall Summary|Glucose|Haemoglobin|Cholesterol)\b\s*(?::|[-\u2013\u2014])?\s*(.*)$",
            heading_line.strip().strip("* "), re.IGNORECASE)
        candidate = match.group(1).casefold() if match else heading_line.strip().strip("* ").rstrip(":").strip().casefold()
        if candidate in aliases:
            current = aliases[candidate]
            sections.setdefault(current, [])
            if match and match.group(2).strip():
                sections[current].append(match.group(2).strip())
        elif current and line.strip():
            sections[current].append(line.strip())

    if any(heading not in sections for heading in SECTION_HEADINGS):
        return None
    bodies = {heading: " ".join(sections[heading]).strip() for heading in SECTION_HEADINGS}
    for heading in SECTION_HEADINGS[:3]:
        bodies[heading] = re.sub(
            rf"^{re.escape(heading)}\s*[:\u2013\u2014-]\s*", "", bodies[heading], flags=re.IGNORECASE)
    if any(not body for body in bodies.values()):
        return None
    if any(len(bodies[heading]) > 450 for heading in SECTION_HEADINGS[:3]) or len(bodies[SECTION_HEADINGS[3]]) > 650:
        return None
    if any(str(value) not in bodies[heading] for heading, value in zip(SECTION_HEADINGS[:3], (glucose, haemoglobin, cholesterol))):
        return None
    recommendation = bodies[SECTION_HEADINGS[3]].casefold()
    recommendation_terms = ("healthcare professional", "health professional", "medical professional",
                            "professional follow", "professional should review", "professional review",
                            "clinician", "doctor", "physician", "medical review")
    if not any(term in recommendation for term in recommendation_terms):
        return None
    return "\n\n".join(f"{heading}\n{bodies[heading]}" for heading in SECTION_HEADINGS)
