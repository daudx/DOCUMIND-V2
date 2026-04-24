import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from routers import documents, chat
from services.vector_service import VectorService
from services.embedding_service import EmbeddingService
from utils.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global services
vector_service = None
embedding_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global vector_service, embedding_service
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Initialize embedding service
        embedding_service = EmbeddingService()
        await embedding_service.initialize()
        logger.info("Embedding service initialized")
        
        # Initialize vector service
        vector_service = VectorService()
        await vector_service.initialize()
        logger.info("Vector service initialized")
        
        # Store services in app state
        app.state.vector_service = vector_service
        app.state.embedding_service = embedding_service
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Cleanup on shutdown
    try:
        if vector_service:
            await vector_service.cleanup()
        logger.info("Services cleaned up")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Initialize FastAPI app
app = FastAPI(
    title="DocuMind API",
    description="AI-powered document interaction platform",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Vite default port
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(chat.router, prefix="/api", tags=["chat"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DocuMind API v2.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "DocuMind API",
        "version": "2.0.0",
        "features": {
            "llm": "Groq (Llama 3.1)",
            "embeddings": "SentenceTransformers",
            "vector_db": "Chroma",
            "supported_formats": ["PDF", "TXT", "DOCX"]
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        log_level="info"
    )