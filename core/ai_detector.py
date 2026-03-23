import re
import math
from .llm_client import _call_openrouter_sync, _parse_json

def compute_statistical_ai_score(text: str) -> dict:
    """
    Returns a probability score 0–100 that text is AI-generated.
    Higher = more likely AI.
    """
    words = text.split()
    word_count = len(words)
    
    # FIX: If text is too short, statistical analysis is unreliable.
    # Return 50% (neutral) to avoid false positives on short texts.
    if word_count < 100:
        return {
            "statistical_ai_probability": 50.0,
            "features": {"note": "Text too short for reliable statistical analysis"}
        }

    sentences = re.split(r"[.!?]+", text)
    lengths = [len(s.split()) for s in sentences if len(s.split()) > 2]
    
    if len(lengths) < 3:
        return {"statistical_ai_probability": 50.0, "features": {"note": "Not enough sentences"}}

    mean = sum(lengths) / len(lengths)
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    std = math.sqrt(variance)
    
    # Burstiness calculation
    if (std + mean) == 0: burstiness = 0.0
    else: burstiness = (std - mean) / (std + mean)
    
    # Low burstiness implies AI. 
    # Adjusted threshold: only penalize if extremely uniform (burstiness < -0.2)
    # Humans writing lists often have low burstiness too.
    burstiness_score = max(0, (-0.2 - burstiness) / 0.5) * 25 
    
    raw_score = 50 + burstiness_score # Start at neutral 50
    probability = min(95, max(5, raw_score))

    return {
        "statistical_ai_probability": round(probability, 1),
        "features": {"burstiness": round(burstiness, 3)}
    }

AI_DETECT_SYSTEM = """You are an expert forensic linguist. Analyze the text.
Is it AI-generated or Human-written?

Output JSON:
{
  "llm_probability": <0-100>,
  "confidence": "<HIGH|MEDIUM|LOW>",
  "assessment": "<1 sentence reason>"
}"""

def detect_ai_text(text: str) -> dict:
    stat_result = compute_statistical_ai_score(text)
    
    # LLM Analysis (use first 2000 chars)
    sample = text[:2000]
    try:
        raw = _call_openrouter_sync(AI_DETECT_SYSTEM, f"Analyze:\n\n{sample}", temperature=0.0)
        llm_result = _parse_json(raw)
    except Exception:
        llm_result = {"llm_probability": 50}
    
    # ENSEMBLE: Weight LLM higher (70%) because stats are unreliable on short texts
    llm_prob = llm_result.get("llm_probability", 50)
    stat_prob = stat_result["statistical_ai_probability"]
    
    ensemble_prob = round(0.7 * llm_prob + 0.3 * stat_prob, 1)
    
    # Label logic
    if ensemble_prob >= 80: label = "Likely AI-Generated"
    elif ensemble_prob >= 60: label = "Possibly AI-Generated"
    elif ensemble_prob >= 40: label = "Likely Human-Written"
    else: label = "Very Likely Human-Written"

    return {
        "ensemble_probability": ensemble_prob,
        "label": label,
        "statistical": stat_result,
        "llm_analysis": llm_result
    }