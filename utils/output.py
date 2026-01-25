"""Output formatting utilities with colors."""

import sys

# Flag to suppress output (used during full_analysis)
_quiet_mode = False


# ASCII Art Banner for nix
NIX_BANNER = """
███╗   ██╗██╗██╗  ██╗
████╗  ██║██║╚██╗██╔╝
██╔██╗ ██║██║ ╚███╔╝
██║╚██╗██║██║ ██╔██╗
██║ ╚████║██║██╔╝ ██╗
╚═╝  ╚═══╝╚═╝╚═╝  ╚═╝
"""


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


def print_banner():
    """Print the nix ASCII art banner in blue."""
    if _use_color:
        print(f"{Colors.BLUE}{Colors.BOLD}{NIX_BANNER}{Colors.RESET}")
    else:
        print(NIX_BANNER)


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


def format_code_snippet(lines, error_line, context=2, show_line_numbers=True):
    """Format a code snippet with the error line highlighted in red.

    Args:
        lines: List of code lines (or full file content as string)
        error_line: Line number to highlight (1-indexed)
        context: Number of lines to show before/after
        show_line_numbers: Whether to show line numbers

    Returns:
        Formatted string with colored error line
    """
    if isinstance(lines, str):
        lines = lines.split('\n')

    start = max(0, error_line - context - 1)
    end = min(len(lines), error_line + context)

    snippet_lines = []
    for i in range(start, end):
        line_num = i + 1
        line_content = lines[i].rstrip() if i < len(lines) else ""

        if show_line_numbers:
            line_num_str = f"{line_num:4d}"
        else:
            line_num_str = ""

        if line_num == error_line:
            # Error line: red background or red text with arrow
            prefix = error(">>> ")
            if show_line_numbers:
                formatted = f"{prefix}{error(line_num_str)} {Colors.RED}{line_content}{Colors.RESET}"
            else:
                formatted = f"{prefix}{Colors.RED}{line_content}{Colors.RESET}"
        else:
            # Context lines: dimmed
            prefix = muted("    ")
            if show_line_numbers:
                formatted = f"{prefix}{muted(line_num_str)} {muted(line_content)}"
            else:
                formatted = f"{prefix}{muted(line_content)}"

        snippet_lines.append(formatted)

    return '\n'.join(snippet_lines)


def print_code_snippet(file_path, error_line, context=2, message=None):
    """Print a code snippet with the error line highlighted.

    Args:
        file_path: Path to the source file
        error_line: Line number to highlight (1-indexed)
        context: Number of lines before/after to show
        message: Optional message to print before snippet
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        if message:
            print(f"\n{error('>')} {bold(message)}")

        # Print file location
        import os
        file_name = os.path.basename(file_path)
        print(f"  {muted('at')} {highlight(file_name)}:{warn(str(error_line))}")
        print()

        # Print formatted snippet
        snippet = format_code_snippet(lines, error_line, context)
        for line in snippet.split('\n'):
            print(f"  {line}")
        print()

    except Exception:
        pass


def format_issue_with_snippet(issue, show_full_path=False):
    """Format an issue with its code snippet for display.

    Args:
        issue: Issue dictionary with file, line, issue/message, severity, snippet
        show_full_path: Whether to show full file path or just filename

    Returns:
        Formatted string with colored output
    """
    import os

    severity = issue.get('severity', 'medium').upper()
    file_path = issue.get('file')
    line = issue.get('line')
    message = issue.get('issue') or issue.get('message', 'Unknown issue')

    # Severity colors
    severity_colors = {
        'CRITICAL': Colors.RED + Colors.BOLD,
        'HIGH': Colors.RED,
        'MEDIUM': Colors.YELLOW,
        'LOW': Colors.CYAN
    }
    sev_color = severity_colors.get(severity, Colors.WHITE)

    output_lines = []

    # Header line with severity and message
    sev_badge = color(f"[{severity}]", sev_color)
    output_lines.append(f"{sev_badge} {bold(message)}")

    # File location
    if file_path and line:
        if show_full_path:
            location = file_path
        else:
            location = os.path.basename(file_path)
        output_lines.append(f"  {muted('at')} {highlight(location)}:{warn(str(line))}")

    # Code snippet if available
    snippet = issue.get('snippet')
    if snippet:
        output_lines.append("")
        # Parse and re-format snippet with colors
        for snippet_line in snippet.split('\n'):
            if snippet_line.startswith('>>> '):
                # Error line
                content = snippet_line[4:]  # Remove prefix
                output_lines.append(f"  {error('>>>')} {Colors.RED}{content}{Colors.RESET}")
            else:
                # Context line
                content = snippet_line.lstrip()
                output_lines.append(f"  {muted('   ')} {muted(content)}")

    # Suggestion if available
    suggestion = issue.get('suggestion')
    if suggestion:
        output_lines.append(f"  {success('Fix:')} {suggestion}")

    return '\n'.join(output_lines)


def print_issues_summary(issues, title="Issues Found"):
    """Print a formatted summary of issues with colored snippets.

    Args:
        issues: List of issue dictionaries
        title: Title for the summary section
    """
    if not issues:
        print(f"\n{success('✓')} No issues found!")
        return

    print(f"\n{bold(title)} ({len(issues)} total)")
    print(muted("─" * 50))

    for i, issue in enumerate(issues, 1):
        print(f"\n{muted(f'[{i}]')} {format_issue_with_snippet(issue)}")

    print(muted("─" * 50))
