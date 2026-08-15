def parse_time_to_seconds(time_str: str) -> float:
    """Конвертує рядок таймкоду 'MM:SS' або 'HH:MM:SS' у секунди (float)"""
    try:
        parts = list(map(int, time_str.strip().split(':')))
        if len(parts) == 2:
            return float(parts[0] * 60 + parts[1])
        elif len(parts) == 3:
            return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    except Exception:
        pass
    return 0.0

def format_seconds_to_time(seconds: float) -> str:
    """Конвертує секунди у рядок формату 'MM:SS'"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"
