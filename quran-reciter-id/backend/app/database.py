"""
Vector Database Handler for Reciter Embeddings
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)


class ReciterDatabase:
    """Manages reciter embeddings and similarity search"""
    
    def __init__(self, embeddings_path: Path, metadata_path: Path):
        """
        Initialize the database
        
        Args:
            embeddings_path: Path to reciter_database.json
            metadata_path: Path to reciters_metadata.json
        """
        self.embeddings_path = embeddings_path
        self.metadata_path = metadata_path
        
        self.embeddings_data = None
        self.metadata_data = None
        self.reciter_vectors = {}  # {reciter_name: embedding_vector}
        self.reciter_metadata = {}  # {reciter_name: metadata_dict}
        
        self._load_database()
    
    def _load_database(self):
        """Load embeddings and metadata from disk"""
        
        # Load embeddings
        if not self.embeddings_path.exists():
            raise FileNotFoundError(
                f"Embeddings database not found at {self.embeddings_path}. "
                "Please run scripts/process_data.py first."
            )
        
        logger.info(f"Loading embeddings from {self.embeddings_path}")
        with open(self.embeddings_path, 'r', encoding='utf-8') as f:
            self.embeddings_data = json.load(f)
        
        # Parse embeddings into numpy arrays
        for reciter in self.embeddings_data['reciters']:
            name = reciter['reciter_name']
            embedding = np.array(reciter['embedding'])
            self.reciter_vectors[name] = embedding
        
        logger.info(f"Loaded {len(self.reciter_vectors)} reciter embeddings")
        
        # Load metadata
        if self.metadata_path.exists():
            logger.info(f"Loading metadata from {self.metadata_path}")
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self.metadata_data = json.load(f)
            
            # Create a lookup dictionary
            for reciter in self.metadata_data['reciters']:
                # Try to match by name (flexible matching)
                self.reciter_metadata[reciter['name']] = reciter
                # Also store by English name for fallback
                self.reciter_metadata[reciter['name_english']] = reciter
            
            logger.info(f"Loaded metadata for {len(self.metadata_data['reciters'])} reciters")
        else:
            logger.warning(f"Metadata file not found at {self.metadata_path}")
            logger.warning("Will return basic info only")
    
    def search_similar(self, query_embedding: np.ndarray, top_k: int = 1) -> List[Tuple[str, float]]:
        """
        Find the most similar reciter(s) to the query embedding
        
        Args:
            query_embedding: The voice embedding to search for
            top_k: Number of top matches to return
        
        Returns:
            List of (reciter_name, similarity_score) tuples, sorted by similarity
        """
        
        if len(self.reciter_vectors) == 0:
            raise ValueError("Database is empty. Please process reciter data first.")
        
        # Reshape query for sklearn
        query_vector = query_embedding.reshape(1, -1)
        
        # Calculate cosine similarity with all reciters
        similarities = []
        
        for reciter_name, reciter_vector in self.reciter_vectors.items():
            reciter_vec_reshaped = reciter_vector.reshape(1, -1)
            similarity = cosine_similarity(query_vector, reciter_vec_reshaped)[0][0]
            similarities.append((reciter_name, float(similarity)))
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def get_reciter_info(self, reciter_name: str) -> Optional[Dict]:
        """
        Get full metadata for a reciter
        
        Args:
            reciter_name: Name of the reciter
        
        Returns:
            Dictionary with reciter metadata, or None if not found
        """
        
        # Try exact match first
        if reciter_name in self.reciter_metadata:
            return self.reciter_metadata[reciter_name]
        
        # Try fuzzy matching (case-insensitive, underscore/space flexible)
        normalized_query = reciter_name.replace('_', ' ').strip().lower()
        
        for key, metadata in self.reciter_metadata.items():
            normalized_key = key.replace('_', ' ').strip().lower()
            if normalized_query == normalized_key:
                return metadata
        
        # If no metadata found, return basic info from embeddings
        logger.warning(f"No metadata found for {reciter_name}, using basic info")
        return {
            "name": reciter_name,
            "name_english": reciter_name,
            "country": "غير معروف",
            "bio": "لا توجد معلومات متاحة",
            "birth_year": "N/A",
            "death_year": None,
            "image_url": "",
            "recitation_style": "غير محدد"
        }
    
    def get_all_reciters(self) -> List[Dict]:
        """Get list of all reciters with their metadata"""
        
        all_reciters = []
        
        # Start with embeddings data (the source of truth)
        for reciter_name in self.reciter_vectors.keys():
            info = self.get_reciter_info(reciter_name)
            if info:
                all_reciters.append(info)
        
        return all_reciters
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        return {
            "total_reciters": len(self.reciter_vectors),
            "embedding_dimension": self.embeddings_data.get('embedding_dim', 0) if self.embeddings_data else 0,
            "has_metadata": self.metadata_data is not None,
            "database_version": self.embeddings_data.get('version', 'unknown') if self.embeddings_data else 'unknown'
        }
