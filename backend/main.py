from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import auth, songs, playlists, analytics
from ml.embedding_service import get_bi_encoder, get_cross_encoder
from ml.sentiment import get_sentiment_pipeline

# Lifespan: Pre-warm PyTorch Neural Models into RAM on server startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Pre-warming PyTorch Neural Models into RAM...")
    get_bi_encoder()         # Pre-loads all-MiniLM-L6-v2
    get_cross_encoder()      # Pre-loads ms-marco Cross-Encoder
    get_sentiment_pipeline() # Pre-loads DistilBERT
    Base.metadata.create_all(bind=engine)
    print("MoodBeats PyTorch RAG API is ready!")
    yield

app = FastAPI(title="MoodBeats API", version="5.1.0", lifespan=lifespan)

# Enable CORS for Vue 3 frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(songs.router)
app.include_router(playlists.router)
app.include_router(analytics.router)

@app.get("/")
def root():
    return {"status": "online", "message": "Welcome to MoodBeats API (Database-Driven PyTorch RAG & Neural Reranker)"}