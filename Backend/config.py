"""
Configuration module for CAPTCHA service.
"""

import os

class Config:
    """Default configuration."""
    
    # Flask settings
    DEBUG = True
    HOST = '127.0.0.1'
    PORT = 5000
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    DATABASE = os.environ.get('DATABASE') or 'captcha.db'
    
    # CAPTCHA constraints
    PUZZLE_PIECE_SIZE = 50
    SAMPLING_RATE = 16  # milliseconds
    MIN_CANVAS_DURATION = 5000  # milliseconds
    SNAP_THRESHOLD = 10  # pixels
    
    # Bot detection thresholds
    BOT_SCORE_THRESHOLD = 0.6  # Score > 0.6 = bot
    MIN_EVENTS_COUNT = 6  # Minimum number of behavior events
    
    # Timing validation (in seconds)
    MAX_SESSION_DURATION = 300  # 5 minutes
    MIN_INTERACTION_TIME = 1  # At least 1 second between events
    
    # Canvas validation
    EXPECTED_SHAPES = ["vuông", "tròn", "tam giác"]
    MIN_STROKES = 3  # Minimum pen strokes
    MIN_POINTS_PER_STROKE = 5  # Minimum points to consider a valid stroke
    
    # Puzzle validation
    CONTAINER_WIDTH = 640
    CONTAINER_HEIGHT = 360
    PUZZLE_MAX_X = CONTAINER_WIDTH - PUZZLE_PIECE_SIZE
    PUZZLE_MAX_Y = CONTAINER_HEIGHT - PUZZLE_PIECE_SIZE

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'must-be-set-in-production')

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DATABASE = ':memory:'

# Select config based on environment
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
