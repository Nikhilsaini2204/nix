from datetime import datetime


def log(message, level="INFO"):
    """Simple logging function"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def log_error(message):
    """Log error message"""
    log(message, "ERROR")


def log_warning(message):
    """Log warning message"""
    log(message, "WARNING")