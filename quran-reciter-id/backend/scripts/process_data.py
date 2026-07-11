"""
Data Processing Pipeline for Quran Reciter ID
==============================================
This script processes the 50 reciter videos:
1. Extracts WAV audio from videos
2. Segments audio into 30s clips
3. Generates voice embeddings using SpeechBrain ECAPA-TDNN
4. Stores embeddings in a vector database

Usage:
    python process_data.py
"""

import os
import json
import numpy as np
import torch
import torchaudio
from pathlib import Path
from pydub import AudioSegment
import ffmpeg
from speechbrain.pretrained import EncoderClassifier
from typing import List, Dict, Tuple
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
RAW_VIDEOS_DIR = BASE_DIR / "data" / "raw_videos"
PROCESSED_AUDIO_DIR = BASE_DIR / "data" / "processed_audio"
EMBEDDINGS_DIR = BASE_DIR / "data" / "embeddings"

# Config
SAMPLE_RATE = 16000  # SpeechBrain models expect 16kHz
SEGMENT_DURATION_MS = 30000  # 30 seconds
MIN_AUDIO_LENGTH_MS = 15000  # Minimum 15 seconds for valid embedding


class ReciterProcessor:
    """Process reciter videos and generate voice embeddings"""
    
    def __init__(self):
        logger.info("Loading SpeechBrain ECAPA-TDNN model...")
        self.encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="pretrained_models/spkrec-ecapa-voxceleb"
        )
        logger.info("Model loaded successfully!")
        
        # Create directories if they don't exist
        PROCESSED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    
    def extract_audio_from_video(self, video_path: Path, output_audio_path: Path) -> bool:
        """Extract audio from video file and convert to WAV"""
        try:
            logger.info(f"Extracting audio from: {video_path.name}")
            
            # Use ffmpeg to extract audio
            (
                ffmpeg
                .input(str(video_path))
                .output(str(output_audio_path), 
                        acodec='pcm_s16le',  # WAV format
                        ac=1,  # Mono
                        ar=str(SAMPLE_RATE))  # 16kHz
                .overwrite_output()
                .run(quiet=True)
            )
            
            logger.info(f"Audio extracted successfully: {output_audio_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to extract audio from {video_path.name}: {str(e)}")
            return False
    
    def segment_audio(self, audio_path: Path) -> List[AudioSegment]:
        """Split audio into 30-second segments"""
        try:
            logger.info(f"Segmenting audio: {audio_path.name}")
            
            # Load audio
            audio = AudioSegment.from_wav(str(audio_path))
            
            # Calculate number of segments
            duration_ms = len(audio)
            segments = []
            
            # Split into 30s chunks
            for i in range(0, duration_ms, SEGMENT_DURATION_MS):
                segment = audio[i:i + SEGMENT_DURATION_MS]
                
                # Only keep segments that are at least MIN_AUDIO_LENGTH_MS
                if len(segment) >= MIN_AUDIO_LENGTH_MS:
                    segments.append(segment)
            
            logger.info(f"Created {len(segments)} segments from {audio_path.name}")
            return segments
            
        except Exception as e:
            logger.error(f"Failed to segment {audio_path.name}: {str(e)}")
            return []
    
    def generate_embedding(self, audio_segment: AudioSegment) -> np.ndarray:
        """Generate voice embedding from audio segment using SpeechBrain"""
        try:
            # Save segment to temporary file
            temp_path = PROCESSED_AUDIO_DIR / "temp_segment.wav"
            audio_segment.export(str(temp_path), format="wav")
            
            # Load with torchaudio
            signal, fs = torchaudio.load(str(temp_path))
            
            # Resample if needed
            if fs != SAMPLE_RATE:
                resampler = torchaudio.transforms.Resample(fs, SAMPLE_RATE)
                signal = resampler(signal)
            
            # Generate embedding
            with torch.no_grad():
                embedding = self.encoder.encode_batch(signal)
            
            # Convert to numpy and flatten
            embedding_np = embedding.squeeze().cpu().numpy()
            
            # Clean up temp file
            temp_path.unlink()
            
            return embedding_np
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return None
    
    def process_reciter(self, video_path: Path, reciter_name: str) -> Dict:
        """Process a single reciter's video"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing reciter: {reciter_name}")
        logger.info(f"{'='*60}")
        
        # Step 1: Extract audio
        audio_filename = f"{reciter_name.replace(' ', '_')}.wav"
        audio_path = PROCESSED_AUDIO_DIR / audio_filename
        
        if not self.extract_audio_from_video(video_path, audio_path):
            return None
        
        # Step 2: Segment audio
        segments = self.segment_audio(audio_path)
        if not segments:
            return None
        
        # Step 3: Generate embeddings for all segments
        embeddings = []
        for idx, segment in enumerate(segments):
            logger.info(f"Generating embedding for segment {idx + 1}/{len(segments)}")
            embedding = self.generate_embedding(segment)
            if embedding is not None:
                embeddings.append(embedding)
        
        if not embeddings:
            logger.warning(f"No valid embeddings generated for {reciter_name}")
            return None
        
        # Step 4: Average embeddings to create a single "voice fingerprint"
        avg_embedding = np.mean(embeddings, axis=0)
        
        logger.info(f"✓ Generated voice fingerprint for {reciter_name} (from {len(embeddings)} segments)")
        
        return {
            "reciter_name": reciter_name,
            "embedding": avg_embedding.tolist(),
            "num_segments": len(embeddings),
            "embedding_dim": len(avg_embedding)
        }
    
    def save_database(self, reciter_data: List[Dict]):
        """Save all embeddings to a JSON database"""
        output_file = EMBEDDINGS_DIR / "reciter_database.json"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Saving database with {len(reciter_data)} reciters...")
        
        database = {
            "version": "1.0",
            "num_reciters": len(reciter_data),
            "embedding_dim": reciter_data[0]["embedding_dim"] if reciter_data else 0,
            "reciters": reciter_data
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(database, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ Database saved to: {output_file}")
        logger.info(f"{'='*60}\n")


def main():
    """Main processing pipeline"""
    logger.info("="*60)
    logger.info("QURAN RECITER ID - DATA PROCESSING PIPELINE")
    logger.info("="*60)
    
    # Check if raw_videos directory exists and has files
    if not RAW_VIDEOS_DIR.exists():
        logger.error(f"Directory not found: {RAW_VIDEOS_DIR}")
        logger.error("Please create the directory and place your 50 reciter videos inside.")
        return
    
    # Get all video files
    video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv']
    video_files = [f for f in RAW_VIDEOS_DIR.iterdir() 
                   if f.is_file() and f.suffix.lower() in video_extensions]
    
    if not video_files:
        logger.error(f"No video files found in {RAW_VIDEOS_DIR}")
        logger.error(f"Supported formats: {', '.join(video_extensions)}")
        logger.error("\nPlease add your 50 reciter videos.")
        return
    
    logger.info(f"\nFound {len(video_files)} video files")
    logger.info(f"Target: 50 reciters\n")
    
    # Initialize processor
    processor = ReciterProcessor()
    
    # Process each video
    reciter_database = []
    
    for idx, video_path in enumerate(video_files, 1):
        # Extract reciter name from filename (without extension)
        reciter_name = video_path.stem
        
        logger.info(f"\n[{idx}/{len(video_files)}] Processing: {reciter_name}")
        
        result = processor.process_reciter(video_path, reciter_name)
        
        if result:
            reciter_database.append(result)
        else:
            logger.warning(f"⚠ Skipped {reciter_name} due to errors")
    
    # Save database
    if reciter_database:
        processor.save_database(reciter_database)
        
        logger.info("\n" + "="*60)
        logger.info("PROCESSING COMPLETE!")
        logger.info(f"✓ Successfully processed: {len(reciter_database)}/{len(video_files)} reciters")
        logger.info(f"✓ Database location: {EMBEDDINGS_DIR / 'reciter_database.json'}")
        logger.info("="*60)
    else:
        logger.error("\n⚠ No reciters were successfully processed!")


if __name__ == "__main__":
    main()
