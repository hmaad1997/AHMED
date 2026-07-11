"""
Pydantic Models for API Request/Response
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class ReciterInfo(BaseModel):
    """Basic reciter information"""
    id: int
    name: str
    name_english: str
    country: str
    bio: str
    birth_year: str
    death_year: Optional[str]
    image_url: str
    recitation_style: str


class IdentificationResult(BaseModel):
    """Response model for reciter identification"""
    success: bool
    reciter_name: str
    reciter_name_english: str
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    country: str
    bio: str
    birth_year: str
    death_year: Optional[str]
    image_url: str
    recitation_style: str
    similarity_score: float = Field(..., description="Raw cosine similarity score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "reciter_name": "عبد الباسط عبد الصمد",
                "reciter_name_english": "Abdul Basit Abdus Samad",
                "confidence": 0.94,
                "country": "مصر",
                "bio": "قارئ مصري شهير...",
                "birth_year": "1927",
                "death_year": "1988",
                "image_url": "https://example.com/images/abdul_basit.jpg",
                "recitation_style": "مجود",
                "similarity_score": 0.892
            }
        }


class ReciterListResponse(BaseModel):
    """Response model for listing all reciters"""
    success: bool
    total_reciters: int
    reciters: List[ReciterInfo]


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str
    detail: Optional[str] = None
