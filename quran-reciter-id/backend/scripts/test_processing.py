"""
Quick Test Script to verify the processing pipeline works
===========================================================
This script tests the data processing with a single video file
before running the full batch of 50 reciters.

Usage:
    python test_processing.py <path_to_test_video.mp4>
"""

import sys
from pathlib import Path
from process_data import ReciterProcessor
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_single_video(video_path: str):
    """Test processing a single video"""
    
    video_file = Path(video_path)
    
    if not video_file.exists():
        logger.error(f"Video file not found: {video_path}")
        return False
    
    logger.info("="*60)
    logger.info("TESTING DATA PROCESSING PIPELINE")
    logger.info("="*60)
    logger.info(f"\nTest Video: {video_file.name}\n")
    
    # Initialize processor
    try:
        processor = ReciterProcessor()
    except Exception as e:
        logger.error(f"Failed to initialize processor: {str(e)}")
        logger.error("\nPossible issues:")
        logger.error("  1. Missing dependencies (check requirements.txt)")
        logger.error("  2. FFmpeg not installed")
        logger.error("  3. No internet connection (for model download)")
        return False
    
    # Process the test video
    reciter_name = video_file.stem
    result = processor.process_reciter(video_file, reciter_name)
    
    if result:
        logger.info("\n" + "="*60)
        logger.info("✓ TEST PASSED!")
        logger.info("="*60)
        logger.info(f"Reciter Name: {result['reciter_name']}")
        logger.info(f"Segments Processed: {result['num_segments']}")
        logger.info(f"Embedding Dimension: {result['embedding_dim']}")
        logger.info("\nYou can now run the full processing pipeline:")
        logger.info("  python scripts/process_data.py")
        return True
    else:
        logger.error("\n" + "="*60)
        logger.error("✗ TEST FAILED!")
        logger.error("="*60)
        logger.error("Check the error messages above for details.")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_processing.py <path_to_test_video.mp4>")
        print("\nExample:")
        print("  python test_processing.py ../data/raw_videos/test_reciter.mp4")
        sys.exit(1)
    
    success = test_single_video(sys.argv[1])
    sys.exit(0 if success else 1)
