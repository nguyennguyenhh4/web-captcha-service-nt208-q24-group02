# CAPTCHA Service - Backend

Python Flask backend for image-based CAPTCHA verification with bot detection.

## 📋 Features

- **Challenge Generation**: Creates random puzzle positions with unique tokens
- **Verification Engine**: Analyzes user behavior to detect bots
- **Bot Detection**: 
  - Event timing analysis (regularity detection)
  - Movement pattern analysis (velocity consistency)
  - Canvas drawing behavior (stroke analysis)
  - Hesitation pattern detection
- **Scoring System**: Weighted multi-factor bot detection (0-1 score)
- **Statistics API**: Track success rates and bot blocking metrics

## 🗂️ File Structure

```
Backend/
├── app.py                 # Main Flask application & endpoints
├── config.py              # Configuration & constants
├── scoring_logic.py       # Bot detection algorithm
├── utils.py               # Database utilities & helpers
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## ⚙️ Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. **Install dependencies**
```bash
pip install -r requirements.txt
```

2. **Run the application**
```bash
python app.py
```

The server will start at `http://127.0.0.1:5000`

## 🔌 API Endpoints

### 1. Initialize Challenge
```http
GET /captcha/init
```

**Response:**
```json
{
  "status": "ok",
  "token": "mXk9q7_R8vP2L",
  "target_x": 234,
  "target_y": 145
}
```

### 2. Verify Response
```http
POST /captcha/verify
Content-Type: application/json
```

**Request Body:**
```json
{
  "token": "mXk9q7_R8vP2L",
  "user_x": 235,
  "startTime": 1234567890,
  "device": "desktop",
  "expectedShape": "vuông",
  "events": [
    {
      "type": "move",
      "area": "puzzle",
      "x": 100,
      "y": 145,
      "timestamp": 1234567900
    }
  ]
}
```

**Response (Passed):**
```json
{
  "passed": true,
  "bot_score": 0.32,
  "status": "passed",
  "message": "Verification passed ✓",
  "details": {
    "puzzle_offset": 1,
    "event_count": 18,
    "event_score": 0.25,
    "canvas_score": 0.35,
    "timing_score": 0.38,
    "bot_score": 0.32
  }
}
```

**Response (Failed):**
```json
{
  "passed": false,
  "bot_score": 0.85,
  "status": "bot_blocked",
  "message": "Verification failed (bot detected)",
  "details": {
    "puzzle_offset": 2,
    "event_count": 8,
    "event_score": 0.90,
    "canvas_score": 0.88,
    "timing_score": 0.75,
    "bot_score": 0.85
  }
}
```

### 3. Get Statistics
```http
GET /api/stats
```

**Response:**
```json
{
  "status": "ok",
  "total": 156,
  "passed": 142,
  "failed": 10,
  "bot_blocked": 4,
  "success_rate": 91.03
}
```

### 4. List Sessions (Debug)
```http
GET /api/sessions
```

**Response:**
```json
{
  "status": "ok",
  "count": 10,
  "sessions": [
    {
      "token": "mXk9q7_R8vP2L",
      "target_x": 234,
      "target_y": 145,
      "created_at": "2026-05-07T14:32:15.123456",
      "status": "passed"
    }
  ]
}
```

### 5. Health Check
```http
GET /health
```

## 🤖 Bot Detection Algorithm

The scoring system analyzes three main factors:

### 1. Event Analysis (40% weight)
- **Regularity Detection**: Uniform intervals indicate bots
- **Movement Variation**: Constant velocity is suspicious
- **Hesitation Patterns**: Lack of corrections suggests bot

### 2. Canvas Drawing (35% weight)
- **Stroke Count**: Minimum 3 strokes required
- **Drawing Speed**: Too fast (< 2s) is suspicious
- **Stroke Consistency**: Too uniform suggests automation

### 3. Timing Analysis (25% weight)
- **Session Duration**: Should take 5-10 seconds minimum
- **Inter-event Timing**: Uniform spacing is suspicious

**Bot Score Thresholds:**
- **< 0.60**: Human (Passed ✓)
- **0.60 - 0.80**: Failed (needs review)
- **> 0.80**: Bot Blocked (clear bot signature)

## 💾 Database

SQLite database (`captcha.db`) with three main tables:

### `sessions`
- Token, puzzle coordinates, timestamps, status, results

### `verification_results`
- Detailed analysis: bot_score, event_score, canvas_score, etc.

### `statistics`
- Daily aggregated stats: total attempts, pass rate, etc.

## 🔧 Configuration

Edit `config.py` to adjust:

```python
PUZZLE_PIECE_SIZE = 50              # Puzzle piece dimensions
MIN_CANVAS_DURATION = 5000          # Minimum drawing time (ms)
BOT_SCORE_THRESHOLD = 0.6           # Bot detection threshold
MIN_EVENTS_COUNT = 6                # Minimum behavior events
SNAP_THRESHOLD = 10                 # Puzzle snap tolerance (px)
```

## 📊 Development

### Enable Debug Mode
```python
# config.py
DEBUG = True
```

### Test with curl

```bash
# Initialize challenge
curl http://127.0.0.1:5000/captcha/init

# Verify response
curl -X POST http://127.0.0.1:5000/captcha/verify \
  -H "Content-Type: application/json" \
  -d '{"token":"...", "user_x":100, "events":[], ...}'

# Get stats
curl http://127.0.0.1:5000/api/stats
```

## 🚀 Production Deployment

1. Set environment variables:
```bash
export FLASK_ENV=production
export SECRET_KEY=your-secure-key
export DATABASE=/path/to/captcha.db
```

2. Use a production server (Gunicorn):
```bash
pip install gunicorn
gunicorn -w 4 app:app
```

3. Configure CORS for your domain:
```python
CORS(app, resources={
    r"/*": {"origins": ["https://yourdomain.com"]}
})
```

## 📝 License

See LICENSE file

## 👨‍💻 Author

CAPTCHA Service Team
