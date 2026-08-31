from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "MoodBeats API"
    SECRET_KEY: str = "moodbeats-super-secret-jwt-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7
    DATABASE_URL: str = "sqlite:///./moodbeats.db"

    # Local Ollama Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT_SECONDS: int = 35        # Timeout for local LLM cold-start
    OLLAMA_MAX_TOKENS: int = 250

    # PyTorch RAG & Neural Reranking Thresholds
    TOP_K: int = 10                          # Final number of results from RAG pipeline
    SIMILARITY_THRESHOLD: float = 0.30      # Minimum score threshold
    RERANKER_TOP_K: int = 15                # Candidates sent to Neural Cross-Encoder
    MAX_PLAYLIST_SONGS: int = 12            # Target library tracks in generated playlist
    MAX_NEW_DISCOVERIES: int = 50           # Large set of 50 new vibe tracks recommended by AI DJ

    # Query Planner Settings
    PLANNER_ENABLED: bool = True            # Enable/disable query decomposition
    PLANNER_TIMEOUT: int = 10               # Seconds before falling back to raw prompt

    # RRF (Reciprocal Rank Fusion) Settings
    RRF_K: int = 60                         # RRF constant — higher = less aggressive rank discounting

    # Diversity Settings (MMR)
    MMR_LAMBDA: float = 0.7                 # 0.0 = pure diversity, 1.0 = pure relevance

    # User Taste Profile Settings
    TASTE_WEIGHT: float = 0.3               # How much to bias results toward user taste (0.0-1.0)
    TASTE_HISTORY_LIMIT: int = 50           # Max recent songs to compute taste vector from

    class Config:
        env_file = ".env"

settings = Settings()