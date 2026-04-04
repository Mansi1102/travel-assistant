"""
Utility helpers — logging setup, input validation, and CLI display functions.
"""

import logging
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "travel_assistant.log"


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure logging to write to both a file and the console (stderr).

    Args:
        level: The minimum log level to capture.
    """
    LOG_DIR.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — captures everything at DEBUG level
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler — only warnings and above so it doesn't clutter the chat
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def validate_input(text: str) -> bool:
    """
    Return True if *text* is a non-empty, non-whitespace string.

    Args:
        text: The raw user input.
    """
    return bool(text and text.strip())


# ---------------------------------------------------------------------------
# CLI display helpers
# ---------------------------------------------------------------------------

BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║           ✈️  Travel Assistant Chatbot  🌍               ║
║  Powered by Google Gemini                                ║
╠══════════════════════════════════════════════════════════╣
║  Commands:                                               ║
║    help    — Show available commands                     ║
║    reset   — Start a new conversation                   ║
║    history — Show conversation history                  ║
║    exit    — Quit the chatbot                           ║
╚══════════════════════════════════════════════════════════╝
"""


def print_banner() -> None:
    """Print the welcome banner."""
    print(BANNER)


def print_help() -> None:
    """Print the list of available commands."""
    print(
        "\n📌 Available commands:\n"
        "  help    — Show this help message\n"
        "  reset   — Clear chat history and start fresh\n"
        "  history — Display the conversation so far\n"
        "  exit    — Quit the chatbot\n"
    )
