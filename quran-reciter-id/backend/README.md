# Quran Reciter ID - Backend

## Setup Instructions

### 1. Install Python Requirements

```bash
cd backend
pip install -r requirements.txt
```

**Note:** You'll also need FFmpeg installed on your system:
- Windows: Download from https://ffmpeg.org/download.html
- Linux: `sudo apt-get install ffmpeg`
- Mac: `brew install ffmpeg`

### 2. Prepare Your Data

Place your 50 reciter videos in the `data/raw_videos/` directory.

**Naming Convention:**
- Name each file with the reciter's name
- Example: `عبد_الباسط_عبد_الصمد.mp4`

**Supported Formats:**
- MP4, AVI, MKV, MOV, FLV, WMV

### 3. Process the Data

Run the data processing pipeline:

```bash
cd backend
python scripts/process_data.py
```

**What This Does:**
1. Extracts audio from each video (saves to `data/processed_audio/`)
2. Segments audio into 30-second clips
3. Generates voice embeddings using SpeechBrain ECAPA-TDNN
4. Creates a database file at `data/embeddings/reciter_database.json`

**Expected Output:**
- Processing logs for each reciter
- Final database with 50 reciter "voice fingerprints"

### 4. Next Steps

After processing completes successfully, you'll be ready for Phase 3 (FastAPI server implementation).

## Troubleshooting

**Issue:** FFmpeg not found
- **Solution:** Install FFmpeg and add it to your system PATH

**Issue:** Out of memory during processing
- **Solution:** Process videos in batches or reduce segment duration

**Issue:** Some videos fail to process
- **Solution:** Check video file integrity and format
