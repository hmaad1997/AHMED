# API Documentation - Quran Reciter ID

## Base URL
```
http://localhost:8000
```

---

## Endpoints

### 1. Health Check

**GET** `/health`

Check if the server is running and ready.

**Response:**
```json
{
  "status": "healthy",
  "ai_engine": "loaded",
  "database": {
    "status": "loaded",
    "total_reciters": 50,
    "embedding_dim": 192
  }
}
```

---

### 2. Identify Reciter

**POST** `/identify-reciter`

Identify a Quran reciter from an audio recording.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body:
  - `audio_file`: Audio file (WAV, MP3, etc.)
  - Minimum duration: 3 seconds
  - Maximum size: 10MB (recommended)

**Example (cURL):**
```bash
curl -X POST "http://localhost:8000/identify-reciter" \
  -F "audio_file=@/path/to/recitation.wav"
```

**Example (Python):**
```python
import requests

with open('recitation.wav', 'rb') as f:
    files = {'audio_file': f}
    response = requests.post('http://localhost:8000/identify-reciter', files=files)
    print(response.json())
```

**Success Response (200):**
```json
{
  "success": true,
  "reciter_name": "عبد الباسط عبد الصمد",
  "reciter_name_english": "Abdul Basit Abdus Samad",
  "confidence": 0.94,
  "country": "مصر",
  "bio": "قارئ مصري شهير، يعتبر من أعظم قراء القرآن في العصر الحديث...",
  "birth_year": "1927",
  "death_year": "1988",
  "image_url": "https://example.com/images/abdul_basit.jpg",
  "recitation_style": "مجود",
  "similarity_score": 0.892
}
```

**Error Response (400):**
```json
{
  "detail": "Audio too short. Please provide at least 3 seconds of recitation."
}
```

**Error Response (503):**
```json
{
  "detail": "Service not initialized"
}
```

---

### 3. List All Reciters

**GET** `/list-reciters`

Get a list of all 50 reciters in the database.

**Response (200):**
```json
{
  "success": true,
  "total_reciters": 50,
  "reciters": [
    {
      "id": 1,
      "name": "عبد الباسط عبد الصمد",
      "name_english": "Abdul Basit Abdus Samad",
      "country": "مصر",
      "bio": "قارئ مصري شهير...",
      "birth_year": "1927",
      "death_year": "1988",
      "image_url": "https://example.com/images/abdul_basit.jpg",
      "recitation_style": "مجود"
    },
    {
      "id": 2,
      "name": "محمد صديق المنشاوي",
      "name_english": "Mohamed Siddiq Al-Minshawi",
      "country": "مصر",
      "bio": "قارئ مصري مشهور...",
      "birth_year": "1920",
      "death_year": "1969",
      "image_url": "https://example.com/images/minshawi.jpg",
      "recitation_style": "مرتل"
    }
  ]
}
```

---

### 4. Database Stats

**GET** `/stats`

Get statistics about the reciter database.

**Response (200):**
```json
{
  "total_reciters": 50,
  "embedding_dimension": 192,
  "has_metadata": true,
  "database_version": "1.0"
}
```

---

## Interactive Documentation

FastAPI provides automatic interactive API documentation:

1. **Swagger UI:** `http://localhost:8000/docs`
   - Try out endpoints directly in the browser
   - See request/response schemas

2. **ReDoc:** `http://localhost:8000/redoc`
   - Alternative documentation format
   - Better for reading and exploration

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (e.g., audio too short, invalid format) |
| 404 | Not Found (e.g., no matching reciter) |
| 500 | Internal Server Error |
| 503 | Service Unavailable (server not initialized) |

---

## Audio Requirements

### Supported Formats
- WAV (recommended)
- MP3
- FLAC
- OGG
- M4A

### Requirements
- **Minimum duration:** 3 seconds
- **Recommended duration:** 5-10 seconds
- **Maximum file size:** 10MB
- **Sample rate:** Any (auto-resampled to 16kHz)
- **Channels:** Mono or Stereo (auto-converted to mono)

### Tips for Best Results
1. Use clear audio with minimal background noise
2. Ensure the audio contains actual recitation (not silence or music)
3. 5-10 seconds of recitation is ideal
4. Higher quality audio = better accuracy

---

## Integration Examples

### Flutter/Dart
```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

Future<Map<String, dynamic>> identifyReciter(String audioPath) async {
  var uri = Uri.parse('http://localhost:8000/identify-reciter');
  var request = http.MultipartRequest('POST', uri);
  
  request.files.add(await http.MultipartFile.fromPath('audio_file', audioPath));
  
  var response = await request.send();
  var responseData = await response.stream.bytesToString();
  
  return json.decode(responseData);
}
```

### JavaScript/Fetch
```javascript
async function identifyReciter(audioFile) {
  const formData = new FormData();
  formData.append('audio_file', audioFile);
  
  const response = await fetch('http://localhost:8000/identify-reciter', {
    method: 'POST',
    body: formData
  });
  
  return await response.json();
}
```

---

## Rate Limiting

Currently, there are no rate limits. For production deployment, consider adding:
- Rate limiting middleware
- Authentication/API keys
- Request throttling

---

## CORS Configuration

The server currently allows requests from any origin (`*`). For production:

1. Edit `app/main.py`
2. Update the `allow_origins` list:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-flutter-app.com"],  # Specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
