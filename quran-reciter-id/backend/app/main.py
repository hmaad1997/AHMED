"""
FastAPI Backend Server for Quran Reciter ID
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import logging
import tempfile
from typing import Optional

from .models import IdentificationResult, ReciterListResponse, ErrorResponse, ReciterInfo
from .ai_engine import VoiceRecognitionEngine
from .database import ReciterDatabase

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Quran Reciter ID API",
    description="AI-powered Quran reciter identification system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware (allow Flutter app to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances (loaded on startup)
ai_engine: Optional[VoiceRecognitionEngine] = None
database: Optional[ReciterDatabase] = None

# Paths
BASE_DIR = Path(__file__).parent.parent
EMBEDDINGS_PATH = BASE_DIR / "data" / "embeddings" / "reciter_database.json"
METADATA_PATH = BASE_DIR / "data" / "reciters_metadata.json"


@app.on_event("startup")
async def startup_event():
    """Initialize AI engine and database on server startup"""
    global ai_engine, database
    
    logger.info("="*60)
    logger.info("STARTING QURAN RECITER ID SERVER")
    logger.info("="*60)
    
    try:
        # Load AI engine
        logger.info("Initializing AI engine...")
        ai_engine = VoiceRecognitionEngine()
        
        # Load database
        logger.info("Loading reciter database...")
        database = ReciterDatabase(EMBEDDINGS_PATH, METADATA_PATH)
        
        # Show stats
        stats = database.get_stats()
        logger.info(f"✓ Database loaded: {stats['total_reciters']} reciters")
        logger.info(f"✓ Embedding dimension: {stats['embedding_dimension']}")
        logger.info(f"✓ Metadata available: {stats['has_metadata']}")
        
        logger.info("="*60)
        logger.info("✓ SERVER READY")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Failed to initialize server: {str(e)}")
        raise


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Quran Reciter ID API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    if ai_engine is None or database is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    stats = database.get_stats()
    
    return {
        "status": "healthy",
        "ai_engine": "loaded",
        "database": {
            "status": "loaded",
            "total_reciters": stats['total_reciters'],
            "embedding_dim": stats['embedding_dimension']
        }
    }


@app.post("/identify-reciter", response_model=IdentificationResult)
async def identify_reciter(audio_file: UploadFile = File(...)):
    """
    Identify a Quran reciter from an audio recording
    
    Parameters:
    - audio_file: Audio file (WAV, MP3, etc.) with minimum 3 seconds of recitation
    
    Returns:
    - Reciter information with confidence score
    """
    
    if ai_engine is None or database is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    logger.info(f"Received identification request: {audio_file.filename}")
    
    try:
        # Read audio file
        audio_bytes = await audio_file.read()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = Path(tmp_file.name)
        
        # Validate audio duration
        if not ai_engine.validate_audio_duration(tmp_path, min_duration_sec=3.0):
            tmp_path.unlink()
            raise HTTPException(
                status_code=400,
                detail="Audio too short. Please provide at least 3 seconds of recitation."
            )
        
        # Generate embedding
        logger.info("Generating voice embedding...")
        query_embedding = ai_engine.process_audio_file(tmp_path)
        
        # Clean up temp file
        tmp_path.unlink()
        
        # Search database
        logger.info("Searching for matching reciter...")
        results = database.search_similar(query_embedding, top_k=1)
        
        if not results:
            raise HTTPException(status_code=404, detail="No matching reciter found")
        
        # Get top match
        reciter_name, similarity_score = results[0]
        
        logger.info(f"Match found: {reciter_name} (similarity: {similarity_score:.4f})")
        
        # Get full metadata
        reciter_info = database.get_reciter_info(reciter_name)
        
        # Calculate confidence score (normalize similarity to 0-1 range)
        # Cosine similarity is already 0-1, but we can boost confidence for high scores
        confidence = min(similarity_score * 1.1, 1.0)  # Slight boost, cap at 1.0
        
        return IdentificationResult(
            success=True,
            reciter_name=reciter_info['name'],
            reciter_name_english=reciter_info['name_english'],
            confidence=confidence,
            country=reciter_info['country'],
            bio=reciter_info['bio'],
            birth_year=reciter_info['birth_year'],
            death_year=reciter_info.get('death_year'),
            image_url=reciter_info['image_url'],
            recitation_style=reciter_info['recitation_style'],
            similarity_score=similarity_score
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Identification failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Identification failed: {str(e)}")


@app.get("/list-reciters", response_model=ReciterListResponse)
async def list_reciters():
    """
    Get list of all 50 reciters in the database
    
    Returns:
    - List of all reciters with their information
    """
    
    if database is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        all_reciters = database.get_all_reciters()
        
        reciter_list = []
        for idx, reciter in enumerate(all_reciters, 1):
            reciter_list.append(ReciterInfo(
                id=reciter.get('id', idx),
                name=reciter['name'],
                name_english=reciter['name_english'],
                country=reciter['country'],
                bio=reciter['bio'],
                birth_year=reciter['birth_year'],
                death_year=reciter.get('death_year'),
                image_url=reciter['image_url'],
                recitation_style=reciter['recitation_style']
            ))
        
        return ReciterListResponse(
            success=True,
            total_reciters=len(reciter_list),
            reciters=reciter_list
        )
        
    except Exception as e:
        logger.error(f"Failed to list reciters: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list reciters: {str(e)}")


@app.get("/stats")
async def get_stats():
    """Get database statistics"""
    
    if database is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return database.get_stats()


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            success=False,
            error="Internal server error",
            detail=str(exc)
        ).dict()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
