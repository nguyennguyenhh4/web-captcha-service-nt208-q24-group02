"""
CAPTCHA Service - Backend
Main Flask application with endpoints for challenge generation and verification.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import json
import secrets
import sqlite3
import os

from config import Config
from scoring_logic import verify_response, calculate_success_rate
from utils import get_db, init_db

# ─────────────────────────────────────────────────────────────────────────────
# Flask App Setup
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Initialize database
init_db(app)

# ─────────────────────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────────────────────

def generate_token():
    """Generate a unique session token."""
    return secrets.token_urlsafe(16)

def generate_challenge():
    """Generate random puzzle target position."""
    import random
    target_x = random.randint(80, 540)  # Safe range: 640px width - 50px piece
    target_y = random.randint(10, 310)  # Safe range: 360px height - 50px piece
    return target_x, target_y

def store_session(token, target_x, target_y):
    """Store challenge session in database."""
    db = get_db()
    cursor = db.cursor()
    created_at = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO sessions (token, target_x, target_y, created_at, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (token, target_x, target_y, created_at))
    
    db.commit()

def retrieve_session(token):
    """Retrieve session by token."""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT token, target_x, target_y, created_at, status
        FROM sessions WHERE token = ?
    """, (token,))
    
    row = cursor.fetchone()
    if row:
        return {
            'token': row[0],
            'target_x': row[1],
            'target_y': row[2],
            'created_at': row[3],
            'status': row[4]
        }
    return None

def update_session_result(token, result_data):
    """Update session with verification result."""
    db = get_db()
    cursor = db.cursor()
    verified_at = datetime.now().isoformat()
    
    cursor.execute("""
        UPDATE sessions 
        SET status = ?, verified_at = ?, result = ?
        WHERE token = ?
    """, (
        result_data['status'],
        verified_at,
        json.dumps(result_data),
        token
    ))
    
    db.commit()

# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/captcha/init', methods=['GET'])
def init_captcha():
    """
    Initialize new captcha challenge.
    Returns: {token, target_x, target_y}
    """
    try:
        token = generate_token()
        target_x, target_y = generate_challenge()
        
        # Store in database
        store_session(token, target_x, target_y)
        
        return jsonify({
            'status': 'ok',
            'token': token,
            'target_x': target_x,
            'target_y': target_y
        }), 200
        
    except Exception as e:
        print(f"Error in /captcha/init: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/captcha/verify', methods=['POST'])
def verify_captcha():
    """
    Verify captcha response.
    Expected payload: {
        token, user_x, startTime, device, expectedShape, events
    }
    Returns: {passed, bot_score, message, details}
    """
    try:
        payload = request.get_json()
        
        # Validate payload
        required_fields = ['token', 'user_x', 'events', 'expectedShape']
        if not all(field in payload for field in required_fields):
            return jsonify({
                'passed': False,
                'bot_score': 1.0,
                'message': 'Missing required fields'
            }), 400
        
        token = payload['token']
        user_x = payload['user_x']
        events = payload['events']
        expected_shape = payload['expectedShape']
        
        # Retrieve session
        session = retrieve_session(token)
        if not session:
            return jsonify({
                'passed': False,
                'bot_score': 1.0,
                'message': 'Invalid or expired token'
            }), 401
        
        # Verify response
        result = verify_response(
            user_x=user_x,
            target_x=session['target_x'],
            events=events,
            expected_shape=expected_shape,
            session_data=session
        )
        
        # Update session with result
        update_session_result(token, result)
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error in /captcha/verify: {e}")
        return jsonify({
            'passed': False,
            'bot_score': 0.5,
            'message': str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    Get verification statistics.
    Returns: {total, passed, failed, bot_blocked, success_rate}
    """
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Count total sessions
        cursor.execute("SELECT COUNT(*) FROM sessions")
        total = cursor.fetchone()[0]
        
        # Count passed/failed
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE status = 'passed'")
        passed = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE status = 'failed'")
        failed = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE status = 'bot_blocked'")
        bot_blocked = cursor.fetchone()[0]
        
        success_rate = calculate_success_rate(passed, total) if total > 0 else 0
        
        return jsonify({
            'status': 'ok',
            'total': total,
            'passed': passed,
            'failed': failed,
            'bot_blocked': bot_blocked,
            'success_rate': round(success_rate, 2)
        }), 200
        
    except Exception as e:
        print(f"Error in /api/stats: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'message': 'CAPTCHA service running'}), 200

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """
    List all sessions (for debugging).
    Returns: [{token, target_x, target_y, created_at, status}]
    """
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT token, target_x, target_y, created_at, status
            FROM sessions ORDER BY created_at DESC LIMIT 50
        """)
        
        rows = cursor.fetchall()
        sessions = [
            {
                'token': row[0],
                'target_x': row[1],
                'target_y': row[2],
                'created_at': row[3],
                'status': row[4]
            }
            for row in rows
        ]
        
        return jsonify({
            'status': 'ok',
            'count': len(sessions),
            'sessions': sessions
        }), 200
        
    except Exception as e:
        print(f"Error in /api/sessions: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ─────────────────────────────────────────────────────────────────────────────
# Error Handlers
# ─────────────────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
