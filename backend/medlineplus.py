"""MedlinePlus topic search and sourced support for Groq-generated remarks."""

from functools import lru_cache
import re
import requests
import xml.etree.ElementTree as ET

from groq_service import SECTION_HEADINGS, format_assessment, generate_assessment

BASE_URL = "https://wsearch.nlm.nih.gov/ws/query"
HEADERS = {"User-Agent": "HealthRecordsAssessment/1.0 (MedlinePlus Web Service)"}
QUERIES = (("Glucose", "diabetes blood glucose"),
           ("Haemoglobin", "hemoglobin anemia blood test"),
           ("Cholesterol", "cholesterol blood test"))


def clean_text(value):
    """Flatten XML text and strip any residual markup before displaying it."""
    value = " ".join(value.split())
    return re.sub(r"<[^>]*>", "", value).strip()


@lru_cache(maxsize=32)
def search_topics(term):
    response = requests.get(BASE_URL, params={"db": "healthTopics", "term": term,
                              "retmax": 3, "rettype": "brief", "tool": "HealthPredictionApp"},
                            headers=HEADERS, timeout=8)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    topics = []
    for document in root.findall(".//document"):
        title_node = next((node for node in document.findall("content") if node.get("name") == "title"), None)
        if title_node is None:
            continue
        title = clean_text("".join(title_node.itertext()))
        url = document.get("url", "")
        if title and url.startswith("https://medlineplus.gov/"):
            topics.append({"title": title, "url": url})
    return topics


@lru_cache(maxsize=32)
def safe_search_topics(term):
    try:
        return search_topics(term), False
    except (requests.RequestException, ET.ParseError):
        return [], True


def get_medlineplus_topics():
    """Return separate supporting links; these are not AI interpretations."""
    results = []
    for label, query in QUERIES:
        topics, unavailable = safe_search_topics(query)
        if unavailable:
            results.append({"label": label, "unavailable": True})
        elif topics:
            results.extend({"label": label, **topic} for topic in topics[:2])
        else:
            results.append({"label": label, "unavailable": False, "empty": True})
    return results


def create_medlineplus_support():
    """Compatibility helper for plain-text presentation of the topic links."""
    lines = []
    for item in get_medlineplus_topics():
        if item.get("unavailable"):
            lines.append(f"{item['label']}: MedlinePlus information is currently unavailable.")
        elif item.get("empty"):
            lines.append(f"{item['label']}: No related MedlinePlus topic was returned.")
        else:
            lines.append(f"{item['label']}: {item['title']} — {item['url']}")
    return lines


def create_remarks(glucose, haemoglobin, cholesterol):
    """Return only the four-section Groq assessment for the Remarks field."""
    assessment, error = generate_assessment(glucose, haemoglobin, cholesterol)
    if assessment:
        return assessment
    return "\n\n".join((
        f"{SECTION_HEADINGS[0]}\nAssessment unavailable.",
        f"{SECTION_HEADINGS[1]}\nAssessment unavailable.",
        f"{SECTION_HEADINGS[2]}\nAssessment unavailable.",
        f"{SECTION_HEADINGS[3]}\nAssessment unavailable. Please try again and consult a healthcare professional.",
    ))
