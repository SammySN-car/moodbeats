# =============================================================================
# QUERY PLANNER — Decomposes user prompts into structured search plans
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


def decompose_query(user_prompt: str) -> dict:
    """
    Use Ollama to decompose a user prompt into a structured search plan.

    Returns a dict with:
      - hyde_description: A hypothetical ideal track description for embedding
      - expanded_queries: 3-5 semantically varied search queries
      - mood: Extracted mood label (happy, sad, energetic, chill, romantic)
      - tempo_range: [min, max] BPM range
      - energy_range: [min, max] energy range (0.0-1.0)
      - keywords: Important keywords extracted from the prompt
      - search_paths: Which retrieval paths to use

    Falls back to DEFAULT_PLAN if Ollama is unavailable.
    """

    print(f"[QueryPlanner] Decomposing: \"{user_prompt}\"")

    # ---------------------------------------------------------------
    # Step 1: Build the decomposition prompt for Ollama
    # ---------------------------------------------------------------
    # We ask Ollama to return structured JSON with specific fields.
    # This is similar to how SoulTuner's Planner works — the LLM
    # plans HOW to search, not WHAT results to return.
    # ---------------------------------------------------------------

    planner_prompt = f"""You are a music search planner. Analyze the user's request and decompose it into a structured search plan.

User request: "{user_prompt}"

Analyze the request and return a JSON object with these fields:
{{
  "hyde_description": "A detailed 2-3 sentence description of an ideal track matching this vibe. Write it as if describing a real song — include mood, tempo feel, instrumentation, atmosphere. This will be used for semantic similarity search.",
  "expanded_queries": ["query1", "query2", "query3"],
  "mood": "one of: happy, sad, energetic, chill, romantic, or null if unclear",
  "tempo_range": [min_bpm, max_bpm],
  "energy_range": [min_energy, max_energy],
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "search_paths": ["list of: mood_filter, tempo_filter, energy_filter, semantic"]
}}

Rules for hyde_description:
- Write it as a music journalist describing a real track
- Include specific musical qualities (tempo feel, instruments, atmosphere)
- Example: "A slow atmospheric track with warm synth pads, gentle rain ambience, melancholic melody, perfect for late night driving"

Rules for expanded_queries:
- Generate 3-5 queries that capture different angles of the request
- Mix abstract mood queries with concrete music terms
- Example for "rainy night vibes": ["melancholic atmospheric ambient", "slow tempo synth for night driving", "rainy mood chill tracks", "late night lo-fi beats"]

Rules for tempo_range and energy_range:
- If the user specifies or implies tempo/energy, use tight ranges
- If vague, use wide ranges
- Example: "gym workout" -> tempo_range: [120, 160], energy_range: [0.7, 1.0]

Respond in valid JSON ONLY."""

    # ---------------------------------------------------------------
    # Step 2: Call Ollama to get the structured plan
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
                    "num_predict": 400,
                    "temperature": 0.3  # Low temp for structured output
                }
            },
            timeout=settings.OLLAMA_TIMEOUT_SECONDS
        )

        if resp.status_code == 200:
            raw_response = resp.json().get("response", "{}")
            plan = json.loads(raw_response)

            # ---------------------------------------------------------------
            # Step 3: Validate and fill defaults for missing fields
            # ---------------------------------------------------------------
            # Ollama might not return all fields. We fill defaults
            # to ensure the pipeline never breaks.
            # ---------------------------------------------------------------

            validated_plan = {
                "hyde_description": plan.get("hyde_description", ""),
                "expanded_queries": plan.get("expanded_queries", []),
                "mood": plan.get("mood"),
                "tempo_range": plan.get("tempo_range", [0, 200]),
                "energy_range": plan.get("energy_range", [0.0, 1.0]),
                "keywords": plan.get("keywords", []),
                "search_paths": plan.get("search_paths", ["semantic"])
            }

            # Validate tempo_range is a list of 2 numbers
            tr = validated_plan["tempo_range"]
            if not isinstance(tr, list) or len(tr) != 2:
                validated_plan["tempo_range"] = [0, 200]

            # Validate energy_range is a list of 2 floats
            er = validated_plan["energy_range"]
            if not isinstance(er, list) or len(er) != 2:
                validated_plan["energy_range"] = [0.0, 1.0]

            # Ensure expanded_queries is a list
            if not isinstance(validated_plan["expanded_queries"], list):
                validated_plan["expanded_queries"] = []

            # Ensure keywords is a list
            if not isinstance(validated_plan["keywords"], list):
                validated_plan["keywords"] = []

            print(f"[QueryPlanner] Mood: {validated_plan['mood']}")
            print(f"[QueryPlanner] Tempo: {validated_plan['tempo_range']}")
            print(f"[QueryPlanner] Energy: {validated_plan['energy_range']}")
            print(f"[QueryPlanner] Keywords: {validated_plan['keywords']}")
            print(f"[QueryPlanner] Expanded queries: {len(validated_plan['expanded_queries'])} queries")
            print(f"[QueryPlanner] Search paths: {validated_plan['search_paths']}")
            print(f"[QueryPlanner] HyDE description: {validated_plan['hyde_description'][:80]}...")

            return validated_plan

    except Exception as e:
        print(f"[QueryPlanner] Ollama call failed: {e}")

    # ---------------------------------------------------------------
    # Step 4: Fallback — build a basic plan from the raw prompt
    # ---------------------------------------------------------------
    # If Ollama is down or times out, we construct a simple plan
    # from the raw prompt. This ensures the pipeline always works.
    # ---------------------------------------------------------------

    print("[QueryPlanner] Using fallback plan from raw prompt")
    words = [w for w in re.sub(r'[^\w\s]', '', user_prompt).split() if len(w) > 2]

    fallback = dict(DEFAULT_PLAN)
    fallback["hyde_description"] = f"A track that matches the vibe: {user_prompt}"
    fallback["expanded_queries"] = [
        user_prompt,
        f"{words[0]} music" if words else "music",
        f"{words[0]} {words[-1]}" if len(words) > 1 else user_prompt
    ]
    fallback["keywords"] = words[:5]

    return fallback