# =============================================================================
# QUERY PLANNER - Decomposes user prompts into structured search plans
# =============================================================================
# Why: Raw prompts like "rainy night vibes" lose nuance when embedded directly.
# The planner uses Ollama to:
#   1. Generate a HyDE (Hypothetical Document Embedding) description
#   2. Expand into multiple semantically varied search queries
#   3. Extract structured metadata (mood, tempo, energy ranges)
#   4. Identify search paths (mood filter, tempo filter, semantic)
# =============================================================================

import json
import requests
import re
import time
import hashlib
from config import settings


# ----- Default plan when Ollama is unavailable -----
DEFAULT_PLAN = {
    "hyde_description": "",
    "expanded_queries": [],
    "mood": None,
    "tempo_range": [0, 200],
    "energy_range": [0.0, 1.0],
    "keywords": [],
    "search_paths": ["semantic"]
}

# ----- Mood normalization map -----
MOOD_MAP = {
    "happy": "euphoric", "joyful": "euphoric", "upbeat": "euphoric", "cheerful": "euphoric",
    "fun": "euphoric", "party": "euphoric", "dance": "euphoric", "euphoric": "euphoric",
    "bright": "euphoric", "sunny": "euphoric", "feel-good": "euphoric", "feel good": "euphoric",
    "summer": "euphoric", "pop": "euphoric",
    "sad": "sad", "melancholic": "sad", "melancholy": "sad", "sorrowful": "sad",
    "heartbroken": "sad", "depressing": "sad", "dark": "sad", "gloomy": "sad",
    "somber": "sad", "bittersweet": "sad", "nostalgic": "sad", "emo": "sad",
    "emotional": "sad", "tearful": "sad", "lonely": "sad",
    "energetic": "energetic", "aggressive": "energetic", "intense": "energetic",
    "hard": "energetic", "powerful": "energetic", "explosive": "energetic",
    "hype": "energetic", "banger": "energetic", "pump": "energetic",
    "drill": "energetic", "phonk": "energetic", "drift": "energetic",
    "workout": "energetic", "gym": "energetic", "festival": "energetic",
    "rave": "energetic", "edm": "energetic", "dubstep": "energetic",
    "bass": "energetic", "distortion": "energetic", "metal": "energetic",
    "boss fight": "energetic",
    "chill": "chill", "calm": "chill", "relaxed": "chill", "mellow": "chill",
    "lo-fi": "chill", "lofi": "chill", "study": "chill", "ambient": "chill",
    "atmospheric": "chill", "dreamy": "chill", "soft": "chill", "gentle": "chill",
    "peaceful": "chill", "serene": "chill", "cozy": "chill", "rainy": "chill",
    "night": "chill", "late night": "chill", "driving": "chill",
    "romantic": "chill", "love": "chill", "intimate": "chill",
    "sensual": "chill", "passionate": "chill", "tender": "chill",
    "sweet": "chill", "dinner": "chill", "wedding": "chill",
}


def normalize_mood(raw_mood: str) -> str:
    """Map a raw mood string to one of our 5 canonical moods."""
    if not raw_mood:
        return None
    mood_lower = raw_mood.lower().strip()
    if mood_lower in MOOD_MAP:
        return MOOD_MAP[mood_lower]
    for key, val in MOOD_MAP.items():
        if key in mood_lower or mood_lower in key:
            return val
    return None


# --- Keyword-based mood override ---
# When Ollama returns the wrong mood, these rules override it.
# This handles the KV-cache poisoning bug where Ollama reuses
# the previous query's mood for a completely different query.

OVERRIDE_RULES = [
    # (keywords_in_prompt, correct_mood)
    # Order matters: more specific rules first
    # Energetic overrides (highest priority for party/workout)
    (["phonk", "drift", "gym", "workout", "metal", "dubstep", "drill", "bass", "boss"], "energetic"),
    (["edm", "festival", "rave", "hype", "banger"], "energetic"),
    # Euphoric overrides
    (["party", "dance", "fun", "upbeat", "summer", "pop", "summer party", "dance pop"], "euphoric"),
    # Romantic overrides (before chill, so "romantic dinner" stays romantic)
    (["romantic", "love song", "dinner", "wedding", "date night", "candlelit"], "chill"),
    # Sad overrides
    (["sad", "heartbreak", "loss", "cry", "tears", "lonely", "breakup"], "sad"),
    # Chill overrides (only if no romantic keywords present)
    (["lo-fi", "lofi", "study", "ambient", "sleep", "relax", "calm"], "chill"),
]


def _override_mood_from_keywords(user_prompt: str, ollama_mood: str) -> str:
    """
    Check if keywords in the user prompt contradict Ollama's mood.
    If so, override with the correct mood.
    This fixes the KV-cache poisoning bug.
    """
    prompt_lower = user_prompt.lower()

    for keywords, correct_mood in OVERRIDE_RULES:
        for kw in keywords:
            if kw in prompt_lower:
                if ollama_mood != correct_mood:
                    print(f"[QueryPlanner] Override: keyword '{kw}' detected, changing mood from '{ollama_mood}' to '{correct_mood}'")
                    return correct_mood

    return ollama_mood


def _detect_stale_response(plan: dict, user_prompt: str) -> bool:
    """
    Detect if Ollama returned a stale/cached response from a previous query.
    Returns True if the response looks wrong for this query.
    """
    hyde = plan.get("hyde_description", "").lower()
    prompt_lower = user_prompt.lower()

    # Check 1: If HyDE contains words that contradict the prompt
    # e.g., "romantic" in HyDE but "party" in prompt
    romantic_words = ["romantic", "tender", "ballad", "candlelit", "intimate", "wedding"]
    party_words = ["party", "dance", "summer", "upbeat", "fun", "banger"]

    has_romantic_hyde = any(w in hyde for w in romantic_words)
    has_party_prompt = any(w in prompt_lower for w in party_words)

    if has_romantic_hyde and has_party_prompt:
        print(f"[QueryPlanner] Stale response detected: romantic HyDE for party prompt")
        return True

    # Check 2: If mood is romantic but prompt has energetic/happy keywords
    mood = plan.get("mood", "")
    energetic_kw = ["phonk", "drift", "gym", "workout", "edm", "festival", "metal"]
    happy_kw = ["party", "dance", "fun", "summer", "pop"]

    if mood == "romantic":
        if any(w in prompt_lower for w in energetic_kw + happy_kw):
            print(f"[QueryPlanner] Stale response detected: romantic mood for energetic/happy prompt")
            return True

    return False


def decompose_query(user_prompt: str) -> dict:
    """
    Use Ollama to decompose a user prompt into a structured search plan.
    Falls back to DEFAULT_PLAN if Ollama is unavailable.
    """

    # ---------------------------------------------------------------
    # Build the decomposition prompt for Ollama
    # ---------------------------------------------------------------

    # Random padding to break KV-cache (unique per call)
    _nonce = hashlib.md5(f"{user_prompt}_{time.time_ns()}".encode()).hexdigest()[:8]

    planner_prompt = f"""You are a music search planner. Analyze the user's request and decompose it into a structured search plan.
NONCE: {_nonce}

User request: "{user_prompt}"

Analyze the request and return a JSON object with these fields:
{{
  "hyde_description": "A detailed 2-3 sentence description of an ideal track matching this vibe. Write it as if describing a real song - include mood, tempo feel, instrumentation, atmosphere. This will be used for semantic similarity search.",
  "expanded_queries": ["query1", "query2", "query3"],
  "mood": "one of: euphoric, sad, energetic, chill, or null if unclear",
  "tempo_range": [min_bpm, max_bpm],
  "energy_range": [min_energy, max_energy],
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "search_paths": ["list of: mood_filter, tempo_filter, energy_filter, semantic"]
}}

Rules for mood:
- MUST be one of exactly: euphoric, sad, energetic, chill, or null
- "phonk", "drift", "gym", "workout", "EDM", "festival", "metal", "bass", "drill" = energetic
- "lo-fi", "study", "rainy", "night", "ambient", "dreamy" = chill
- "party", "dance", "fun", "upbeat", "summer", "pop" = euphoric
- "love", "romantic", "dinner", "wedding" = chill
- "sad", "heartbreak", "loss", "emo", "emotional" = sad

Rules for hyde_description:
- CRITICAL: This MUST match the user's request. Do NOT reuse descriptions from other queries.
- Write it as a music journalist describing a real track
- Include specific musical qualities (tempo feel, instruments, atmosphere)
- For lo-fi/study: "A soft lo-fi beat with vinyl crackle, mellow piano chords, slow tempo, perfect for focused studying"
- For romantic: "A tender acoustic ballad with gentle fingerpicked guitar, warm vocals, intimate atmosphere for a candlelit dinner"
- For phonk/gym: "A driving phonk track with heavy 808 cowbells, distorted bass, aggressive tempo around 130 BPM"
- For sad: "A melancholic piano ballad with reverb-drenched vocals, slow tempo, emotional atmosphere"
- For party: "An upbeat pop anthem with catchy hooks, bright synths, danceable groove, summer vibes"

Rules for tempo_range and energy_range:
- "gym", "workout", "festival", "EDM" -> tempo_range: [120, 160], energy_range: [0.7, 1.0]
- "chill", "study", "lo-fi", "ambient" -> tempo_range: [70, 110], energy_range: [0.2, 0.7]
- "romantic", "dinner" -> tempo_range: [60, 100], energy_range: [0.2, 0.6]
- "sad", "emotional" -> tempo_range: [60, 110], energy_range: [0.2, 0.7]
- "party", "pop" -> tempo_range: [100, 140], energy_range: [0.6, 1.0]

Respond in valid JSON ONLY."""

    # ---------------------------------------------------------------
    # Call Ollama to get the structured plan
    # ---------------------------------------------------------------

    try:
        resp = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": planner_prompt,
                "format": "json",
                "stream": False,
                "options": {
                    "num_predict": 500,
                    "temperature": 0.5,
                    "repeat_penalty": 1.2  # Penalize repeated tokens to prevent stale output
                }
            },
            timeout=settings.OLLAMA_TIMEOUT_SECONDS
        )

        if resp.status_code == 200:
            raw_response = resp.json().get("response", "{}")
            plan = json.loads(raw_response)

            validated_plan = {
                "hyde_description": plan.get("hyde_description", ""),
                "expanded_queries": plan.get("expanded_queries", []),
                "mood": normalize_mood(plan.get("mood")),
                "tempo_range": plan.get("tempo_range", [0, 200]),
                "energy_range": plan.get("energy_range", [0.0, 1.0]),
                "keywords": plan.get("keywords", []),
                "search_paths": plan.get("search_paths", ["semantic"])
            }

            # Validate ranges
            tr = validated_plan["tempo_range"]
            if not isinstance(tr, list) or len(tr) != 2:
                validated_plan["tempo_range"] = [0, 200]
            er = validated_plan["energy_range"]
            if not isinstance(er, list) or len(er) != 2:
                validated_plan["energy_range"] = [0.0, 1.0]
            if not isinstance(validated_plan["expanded_queries"], list):
                validated_plan["expanded_queries"] = []
            if not isinstance(validated_plan["keywords"], list):
                validated_plan["keywords"] = []

            # ---------------------------------------------------------------
            # Sanity check: detect and fix stale/cached responses
            # ---------------------------------------------------------------

            # Check 1: Detect stale response from KV-cache
            if _detect_stale_response(validated_plan, user_prompt):
                print("[QueryPlanner] Retrying with fresh nonce...")
                # Retry once with higher temperature
                try:
                    _nonce2 = hashlib.md5(f"{user_prompt}_{time.time_ns()}_retry".encode()).hexdigest()[:8]
                    retry_prompt = planner_prompt.replace(_nonce, _nonce2)
                    resp2 = requests.post(
                        f"{settings.OLLAMA_BASE_URL}/api/generate",
                        json={
                            "model": settings.OLLAMA_MODEL,
                            "prompt": retry_prompt,
                            "format": "json",
                            "stream": False,
                            "options": {
                                "num_predict": 500,
                                "temperature": 0.6,  # Higher temp on retry
                                "repeat_penalty": 1.5
                            }
                        },
                        timeout=settings.OLLAMA_TIMEOUT_SECONDS
                    )
                    if resp2.status_code == 200:
                        raw2 = resp2.json().get("response", "{}")
                        plan2 = json.loads(raw2)
                        validated_plan = {
                            "hyde_description": plan2.get("hyde_description", validated_plan["hyde_description"]),
                            "expanded_queries": plan2.get("expanded_queries", validated_plan["expanded_queries"]),
                            "mood": normalize_mood(plan2.get("mood")) or validated_plan["mood"],
                            "tempo_range": plan2.get("tempo_range", validated_plan["tempo_range"]),
                            "energy_range": plan2.get("energy_range", validated_plan["energy_range"]),
                            "keywords": plan2.get("keywords", validated_plan["keywords"]),
                            "search_paths": plan2.get("search_paths", validated_plan["search_paths"])
                        }
                        print(f"[QueryPlanner] Retry succeeded, mood: {validated_plan['mood']}")
                except Exception as e:
                    print(f"[QueryPlanner] Retry failed: {e}")

            # Check 2: Override mood based on keywords in prompt
            validated_plan["mood"] = _override_mood_from_keywords(
                user_prompt, validated_plan["mood"]
            )

            # If mood was overridden, fix HyDE if it contradicts the new mood
            hyde_lower = validated_plan.get("hyde_description", "").lower()
            corrected_mood = validated_plan["mood"]
            if corrected_mood == "euphoric" and any(w in hyde_lower for w in ["romantic", "tender", "ballad", "candlelit", "intimate"]):
                validated_plan["hyde_description"] = "An upbeat pop anthem with catchy hooks, bright synths, danceable groove for: " + user_prompt
            elif corrected_mood == "energetic" and any(w in hyde_lower for w in ["romantic", "tender", "ballad", "soft", "mellow"]):
                validated_plan["hyde_description"] = "A high-energy track with driving beats, powerful bass, intense atmosphere for: " + user_prompt
            elif corrected_mood == "sad" and any(w in hyde_lower for w in ["upbeat", "dance", "party", "fun", "bright"]):
                validated_plan["hyde_description"] = "A melancholic song with emotional vocals, slow tempo, minor key, introspective atmosphere for: " + user_prompt

            return validated_plan

    except Exception as e:
        print(f"[QueryPlanner] Ollama call failed: {e}")

    # ---------------------------------------------------------------
    # Fallback - build a basic plan from the raw prompt
    # ---------------------------------------------------------------

    print("[QueryPlanner] Using fallback plan from raw prompt")
    words = [w for w in re.sub(r'[^\w\s]', '', user_prompt).split() if len(w) > 2]

    fallback_mood = None
    for word in words:
        if word.lower() in MOOD_MAP:
            fallback_mood = MOOD_MAP[word.lower()]
            break

    # Apply keyword override to fallback too
    fallback_mood = _override_mood_from_keywords(user_prompt, fallback_mood)

    fallback = dict(DEFAULT_PLAN)
    fallback["hyde_description"] = f"A track that matches the vibe: {user_prompt}"
    fallback["expanded_queries"] = [
        user_prompt,
        f"{words[0]} music" if words else "music",
        f"{words[0]} {words[-1]}" if len(words) > 1 else user_prompt
    ]
    fallback["keywords"] = words[:5]
    fallback["mood"] = fallback_mood

    return fallback