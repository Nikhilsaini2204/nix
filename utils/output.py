"""Output formatting utilities with colors."""

import sys

# Flag to suppress output (used during full_analysis)
_quiet_mode = False


def set_quiet_mode(enabled):
    """Enable/disable quiet mode to suppress step/success prints."""
    global _quiet_mode
    _quiet_mode = enabled


def is_quiet():
    """Check if quiet mode is enabled."""
    return _quiet_mode

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Colors
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"


def supports_color():
    """Check if terminal supports colors."""
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


_use_color = supports_color()


def color(text, color_code):
    """Apply color to text if supported."""
    if _use_color:
        return f"{color_code}{text}{Colors.RESET}"
    return text


def bold(text):
    """Make text bold."""
    return color(text, Colors.BOLD)


def dim(text):
    """Make text dim/gray."""
    return color(text, Colors.GRAY)


def success(text):
    """Green success text."""
    return color(text, Colors.GREEN)


def error(text):
    """Red error text."""
    return color(text, Colors.RED)


def info(text):
    """Blue info text."""
    return color(text, Colors.BLUE)


def warn(text):
    """Yellow warning text."""
    return color(text, Colors.YELLOW)


def highlight(text):
    """Cyan highlight text."""
    return color(text, Colors.CYAN)


def muted(text):
    """Gray muted text."""
    return color(text, Colors.GRAY)


# Status indicators
def print_step(message):
    """Print a step/progress message."""
    if not _quiet_mode:
        print(f"{muted('›')} {message}")


def print_success(message):
    """Print success message."""
    if not _quiet_mode:
        print(f"{success('✓')} {message}")


def print_error(message):
    """Print error message."""
    if not _quiet_mode:
        print(f"{error('✗')} {message}")


def print_info(message):
    """Print info message."""
    print(f"{info('ℹ')} {message}")


# Claude Code style output
def print_tool_start(tool_name):
    """Print tool start in Claude Code style."""
    print(f"{color('⏺', Colors.MAGENTA)} {bold(tool_name)}")


def print_tool_result(result):
    """Print tool result in Claude Code style."""
    print(f"  {muted('⎿')}  {result}")
