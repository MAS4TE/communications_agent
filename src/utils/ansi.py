# ANSI escape codes
RESET = "\033[0m"
BOLD = "\033[1m"
BLUE = "\033[34m"
GREEN = "\033[32m"
BOLD_BLUE = f"{BOLD}{BLUE}"
BOLD_GREEN = f"{BOLD}{GREEN}"

def color_text(text, color):
    """Wrap text with ANSI color codes."""
    return f"{color}{text}{RESET}"