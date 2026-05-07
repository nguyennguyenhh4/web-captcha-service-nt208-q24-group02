"""
Scoring logic for bot detection and CAPTCHA verification.
Analyzes user behavior and interaction patterns to detect bots.
"""

from config import Config
from datetime import datetime
import json

# ─────────────────────────────────────────────────────────────────────────────
# Bot Detection Algorithm
# ─────────────────────────────────────────────────────────────────────────────

def verify_response(user_x, target_x, events, expected_shape, session_data):
    """
    Main verification function.
    
    Args:
        user_x: User's final puzzle piece position
        target_x: Correct target position
        events: List of behavior events
        expected_shape: Expected canvas drawing shape
        session_data: Session metadata
    
    Returns:
        {
            'passed': bool,
            'bot_score': float (0-1),
            'message': str,
            'details': dict
        }
    """
    
    # Step 1: Validate puzzle accuracy
    puzzle_check = validate_puzzle(user_x, target_x)
    if not puzzle_check['valid']:
        return {
            'passed': False,
            'bot_score': 0.1,
            'message': 'Puzzle position incorrect',
            'details': puzzle_check
        }
    
    # Step 2: Validate minimum events
    if len(events) < Config.MIN_EVENTS_COUNT:
        return {
            'passed': False,
            'bot_score': 0.9,
            'message': f'Insufficient behavior data (got {len(events)}, need {Config.MIN_EVENTS_COUNT})',
            'details': {'event_count': len(events)}
        }
    
    # Step 3: Calculate bot score from events
    event_score = analyze_events(events)
    
    # Step 4: Analyze canvas drawing
    canvas_score = analyze_canvas_drawing(events, expected_shape)
    
    # Step 5: Check timing patterns
    timing_score = analyze_timing(events, session_data)
    
    # Step 6: Combine scores (weighted)
    bot_score = (
        event_score * 0.40 +      # Event patterns (40%)
        canvas_score * 0.35 +     # Canvas drawing (35%)
        timing_score * 0.25       # Timing patterns (25%)
    )
    
    # Step 7: Final decision
    details = {
        'puzzle_offset': abs(user_x - target_x),
        'event_count': len(events),
        'event_score': round(event_score, 2),
        'canvas_score': round(canvas_score, 2),
        'timing_score': round(timing_score, 2),
        'bot_score': round(bot_score, 2)
    }
    
    passed = bot_score < Config.BOT_SCORE_THRESHOLD
    
    return {
        'passed': passed,
        'bot_score': round(bot_score, 2),
        'status': 'passed' if passed else 'bot_blocked' if bot_score > 0.8 else 'failed',
        'message': 'Verification passed ✓' if passed else 'Verification failed (bot detected)' if bot_score > 0.8 else 'Verification failed',
        'details': details
    }

# ─────────────────────────────────────────────────────────────────────────────
# Sub-scoring Functions
# ─────────────────────────────────────────────────────────────────────────────

def validate_puzzle(user_x, target_x):
    """Validate puzzle piece position accuracy."""
    offset = abs(user_x - target_x)
    
    return {
        'valid': offset <= Config.SNAP_THRESHOLD,
        'offset': offset,
        'threshold': Config.SNAP_THRESHOLD
    }

def analyze_events(events):
    """
    Analyze behavior events to detect bot patterns.
    
    Bot indicators:
    - Too regular/uniform intervals
    - Perfect straight movements
    - Unnaturally fast/slow speeds
    - No hesitation or correction
    """
    
    if not events or len(events) < 2:
        return 1.0  # Suspicious if no events
    
    scores = []
    
    # Check event regularity (bots have too uniform timing)
    intervals = []
    for i in range(1, len(events)):
        if 'timestamp' in events[i] and 'timestamp' in events[i-1]:
            interval = events[i]['timestamp'] - events[i-1]['timestamp']
            intervals.append(interval)
    
    if intervals:
        regularity_score = detect_regularity(intervals)
        scores.append(regularity_score)
    
    # Check for natural variation in movement
    variation_score = detect_movement_variation(events)
    scores.append(variation_score)
    
    # Check for hesitation/correction (humans do this)
    hesitation_score = detect_hesitation_patterns(events)
    scores.append(hesitation_score)
    
    # Average scores
    return sum(scores) / len(scores) if scores else 0.5

def detect_regularity(intervals):
    """
    Detect if intervals are too uniform (bot signature).
    Humans have natural variation in timing.
    
    Returns: 0.0 (natural) to 1.0 (suspicious regularity)
    """
    if len(intervals) < 3:
        return 0.3  # Not enough data
    
    # Calculate variance
    mean_interval = sum(intervals) / len(intervals)
    if mean_interval == 0:
        return 0.5
    
    variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
    std_dev = variance ** 0.5
    coefficient_of_variation = std_dev / mean_interval if mean_interval > 0 else 0
    
    # If CV < 0.1, intervals are suspiciously regular
    if coefficient_of_variation < 0.1:
        return 0.9  # Very suspicious
    elif coefficient_of_variation < 0.3:
        return 0.5  # Somewhat suspicious
    else:
        return 0.1  # Natural variation

def detect_movement_variation(events):
    """
    Check if movements have natural variation (non-uniform velocity).
    Bots often move at constant velocity.
    
    Returns: 0.0 (natural) to 1.0 (suspicious)
    """
    slider_events = [e for e in events if e.get('area') == 'puzzle']
    
    if len(slider_events) < 3:
        return 0.3
    
    # Calculate deltas between consecutive positions
    deltas = []
    for i in range(1, len(slider_events)):
        if 'x' in slider_events[i] and 'x' in slider_events[i-1]:
            delta = abs(slider_events[i]['x'] - slider_events[i-1]['x'])
            deltas.append(delta)
    
    if not deltas or len(deltas) < 2:
        return 0.3
    
    # Check if deltas are too uniform (constant velocity = bot)
    mean_delta = sum(deltas) / len(deltas)
    if mean_delta == 0:
        return 0.8
    
    variance = sum((x - mean_delta) ** 2 for x in deltas) / len(deltas)
    std_dev = variance ** 0.5
    cv = std_dev / mean_delta if mean_delta > 0 else 0
    
    if cv < 0.15:
        return 0.8  # Too uniform = bot
    elif cv < 0.4:
        return 0.4
    else:
        return 0.1

def detect_hesitation_patterns(events):
    """
    Detect natural human hesitation (start-stop patterns).
    Humans often make corrections; bots rarely do.
    
    Returns: 0.0 (natural, has hesitation) to 1.0 (suspicious, too smooth)
    """
    puzzle_events = [e for e in events if e.get('area') == 'puzzle']
    
    if len(puzzle_events) < 4:
        return 0.4  # Not enough data
    
    # Count direction changes (hesitation indicator)
    direction_changes = 0
    for i in range(1, len(puzzle_events) - 1):
        if 'x' in puzzle_events[i] and 'x' in puzzle_events[i-1] and 'x' in puzzle_events[i+1]:
            prev_delta = puzzle_events[i]['x'] - puzzle_events[i-1]['x']
            next_delta = puzzle_events[i+1]['x'] - puzzle_events[i]['x']
            
            # Sign change indicates correction
            if prev_delta * next_delta < 0:
                direction_changes += 1
    
    # Humans typically have 1-3 corrections; bots have 0
    if direction_changes == 0:
        return 0.7  # Suspicious
    elif direction_changes <= 2:
        return 0.1  # Natural
    else:
        return 0.3  # A bit much but possible

def analyze_canvas_drawing(events, expected_shape):
    """
    Analyze canvas drawing behavior.
    
    Bot indicators:
    - Too perfect shape
    - Unnaturally consistent stroke pressure
    - Too few strokes
    - Drawing completed instantly
    """
    
    canvas_events = [e for e in events if e.get('area') == 'canvas']
    
    if not canvas_events:
        return 0.9  # No drawing = bot
    
    scores = []
    
    # Check stroke count
    stroke_count = count_strokes(canvas_events)
    if stroke_count < Config.MIN_STROKES:
        scores.append(0.8)
    else:
        scores.append(0.1)
    
    # Check drawing time (too fast = bot)
    draw_time_score = check_drawing_speed(canvas_events)
    scores.append(draw_time_score)
    
    # Check stroke consistency (too consistent = bot)
    consistency_score = check_stroke_consistency(canvas_events)
    scores.append(consistency_score)
    
    return sum(scores) / len(scores) if scores else 0.5

def count_strokes(canvas_events):
    """Count number of pen lifts (strokes)."""
    stroke_count = 0
    for event in canvas_events:
        if event.get('type') == 'up':
            stroke_count += 1
    return max(1, stroke_count)

def check_drawing_speed(canvas_events):
    """Check if drawing completed too quickly."""
    if len(canvas_events) < 2:
        return 0.5
    
    first_time = canvas_events[0].get('timestamp', 0)
    last_time = canvas_events[-1].get('timestamp', 0)
    duration = last_time - first_time
    
    # Drawing should take at least 2-3 seconds
    if duration < 2000:
        return 0.8  # Too fast = suspicious
    elif duration < 3000:
        return 0.5
    else:
        return 0.1

def check_stroke_consistency(canvas_events):
    """Check if strokes are unnaturally consistent."""
    strokes = extract_strokes(canvas_events)
    
    if len(strokes) < 2:
        return 0.3
    
    # Calculate stroke lengths
    lengths = [calculate_stroke_length(stroke) for stroke in strokes]
    
    if not lengths:
        return 0.5
    
    mean_length = sum(lengths) / len(lengths)
    if mean_length == 0:
        return 0.8
    
    variance = sum((x - mean_length) ** 2 for x in lengths) / len(lengths)
    std_dev = variance ** 0.5
    cv = std_dev / mean_length
    
    # Too consistent = bot
    if cv < 0.15:
        return 0.7
    else:
        return 0.1

def extract_strokes(canvas_events):
    """Extract individual strokes from canvas events."""
    strokes = []
    current_stroke = []
    
    for event in canvas_events:
        if event.get('type') == 'down':
            current_stroke = [event]
        elif event.get('type') == 'move' and current_stroke:
            current_stroke.append(event)
        elif event.get('type') == 'up' and current_stroke:
            current_stroke.append(event)
            strokes.append(current_stroke)
            current_stroke = []
    
    return strokes

def calculate_stroke_length(stroke):
    """Calculate total length of a stroke."""
    total_length = 0
    for i in range(1, len(stroke)):
        if 'x' in stroke[i] and 'y' in stroke[i] and 'x' in stroke[i-1] and 'y' in stroke[i-1]:
            dx = stroke[i]['x'] - stroke[i-1]['x']
            dy = stroke[i]['y'] - stroke[i-1]['y']
            total_length += (dx**2 + dy**2) ** 0.5
    return total_length

def analyze_timing(events, session_data):
    """
    Analyze overall timing patterns.
    
    Bot indicators:
    - Session completed too quickly
    - Events spaced unnaturally
    """
    
    if not events or len(events) < 2:
        return 0.5
    
    scores = []
    
    # Check session duration
    first_event_time = events[0].get('timestamp', 0)
    last_event_time = events[-1].get('timestamp', 0)
    session_duration = last_event_time - first_event_time
    
    # Interaction should take at least 5-10 seconds (canvas timer is 5s minimum)
    if session_duration < 4000:
        scores.append(0.8)
    elif session_duration < 6000:
        scores.append(0.3)
    else:
        scores.append(0.1)
    
    # Check inter-event timing (uniform = bot)
    inter_event_times = []
    for i in range(1, len(events)):
        time_diff = events[i].get('timestamp', 0) - events[i-1].get('timestamp', 0)
        if time_diff > 0:
            inter_event_times.append(time_diff)
    
    if inter_event_times:
        mean_time = sum(inter_event_times) / len(inter_event_times)
        if mean_time > 0:
            variance = sum((x - mean_time) ** 2 for x in inter_event_times) / len(inter_event_times)
            std_dev = variance ** 0.5
            cv = std_dev / mean_time
            
            if cv < 0.2:
                scores.append(0.7)
            else:
                scores.append(0.1)
    
    return sum(scores) / len(scores) if scores else 0.5

# ─────────────────────────────────────────────────────────────────────────────
# Statistics
# ─────────────────────────────────────────────────────────────────────────────

def calculate_success_rate(passed_count, total_count):
    """Calculate success rate percentage."""
    if total_count == 0:
        return 0.0
    return (passed_count / total_count) * 100
