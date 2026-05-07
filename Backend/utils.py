"""
Utility functions for database and general operations.
"""

import sqlite3
import os
from flask import g
from config import Config

# ─────────────────────────────────────────────────────────────────────────────
# Database Connection
# ─────────────────────────────────────────────────────────────────────────────

def get_db():
    """Get database connection."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(Config.DATABASE)
        db.row_factory = sqlite3.Row
    return db

def close_db(e=None):
    """Close database connection."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# ─────────────────────────────────────────────────────────────────────────────
# Database Initialization
# ─────────────────────────────────────────────────────────────────────────────

def init_db(app):
    """Initialize database schema."""
    
    # Register teardown
    app.teardown_appcontext(close_db)
    
    # Create tables if they don't exist
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                target_x INTEGER NOT NULL,
                target_y INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                verified_at TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Verification results table (for detailed analysis)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                token TEXT UNIQUE NOT NULL,
                passed BOOLEAN,
                bot_score REAL,
                event_count INTEGER,
                event_score REAL,
                canvas_score REAL,
                timing_score REAL,
                verified_at TEXT,
                created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        # Statistics table (aggregated)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                total_attempts INTEGER DEFAULT 0,
                passed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                bot_blocked_count INTEGER DEFAULT 0,
                avg_bot_score REAL,
                success_rate REAL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_token 
            ON sessions(token)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_status 
            ON sessions(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_created 
            ON sessions(created_timestamp)
        """)
        
        db.commit()
        print("[✓] Database initialized successfully")

# ─────────────────────────────────────────────────────────────────────────────
# Query Helpers
# ─────────────────────────────────────────────────────────────────────────────

def query_session(token):
    """Query a single session by token."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM sessions WHERE token = ?", (token,))
    return cursor.fetchone()

def query_sessions(limit=50, status=None):
    """Query multiple sessions."""
    db = get_db()
    cursor = db.cursor()
    
    if status:
        cursor.execute(
            "SELECT * FROM sessions WHERE status = ? ORDER BY created_timestamp DESC LIMIT ?",
            (status, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM sessions ORDER BY created_timestamp DESC LIMIT ?",
            (limit,)
        )
    
    return cursor.fetchall()

def query_stats(days=7):
    """Query statistics for the last N days."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM statistics WHERE date >= date('now', ? || ' days') ORDER BY date DESC",
        (f"-{days}",)
    )
    return cursor.fetchall()

# ─────────────────────────────────────────────────────────────────────────────
# Data Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_token_format(token):
    """Validate token format."""
    if not token or not isinstance(token, str):
        return False
    if len(token) < 10 or len(token) > 32:
        return False
    return True

def validate_coordinates(x, y, width=Config.CONTAINER_WIDTH, height=Config.CONTAINER_HEIGHT):
    """Validate puzzle coordinates."""
    piece_size = Config.PUZZLE_PIECE_SIZE
    
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return False
    
    if x < 0 or x > (width - piece_size):
        return False
    
    if y < 0 or y > (height - piece_size):
        return False
    
    return True

def validate_events(events):
    """Validate events list."""
    if not isinstance(events, list):
        return False
    
    if len(events) < Config.MIN_EVENTS_COUNT:
        return False
    
    for event in events:
        if not isinstance(event, dict):
            return False
        if 'timestamp' not in event:
            return False
    
    return True

# ─────────────────────────────────────────────────────────────────────────────
# Cleanup & Maintenance
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_old_sessions(days=7):
    """Delete sessions older than N days."""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        DELETE FROM sessions 
        WHERE created_timestamp < datetime('now', ? || ' days')
    """, (f"-{days}",))
    
    db.commit()
    return cursor.rowcount

def generate_daily_stats():
    """Generate daily statistics."""
    db = get_db()
    cursor = db.cursor()
    today = datetime.now().date().isoformat()
    
    # Count today's sessions
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN status = 'bot_blocked' THEN 1 ELSE 0 END) as blocked,
            AVG(CAST(result -> '$.details.bot_score' as REAL)) as avg_bot_score
        FROM sessions 
        WHERE DATE(created_timestamp) = ?
    """, (today,))
    
    row = cursor.fetchone()
    
    if row and row['total'] > 0:
        passed = row['passed'] or 0
        total = row['total']
        success_rate = (passed / total) * 100
        
        cursor.execute("""
            INSERT OR REPLACE INTO statistics 
            (date, total_attempts, passed_count, failed_count, bot_blocked_count, avg_bot_score, success_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            today,
            total,
            passed,
            row['failed'] or 0,
            row['blocked'] or 0,
            row['avg_bot_score'] or 0.5,
            success_rate
        ))
        
        db.commit()

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def format_timestamp(dt_string):
    """Format timestamp for display."""
    from datetime import datetime
    if not dt_string:
        return None
    try:
        dt = datetime.fromisoformat(dt_string)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return dt_string

def calculate_session_duration(start_time, end_time):
    """Calculate duration between two timestamps in seconds."""
    from datetime import datetime
    try:
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
        return (end - start).total_seconds()
    except:
        return None

# Import datetime for generate_daily_stats
from datetime import datetime
