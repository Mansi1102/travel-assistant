"""
Travel Assistant Chatbot — Entry Point

Run with:  python main.py
"""

import logging
import os
import sys

from dotenv import load_dotenv

from chatbot import TravelChatbot
from config import BOT_PREFIX, PROMPT_SYMBOL
from utils import print_banner, print_help, setup_logging, validate_input

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the Travel Assistant Chatbot CLI loop."""

    # --- 1. Initialise environment & logging --------------------------------
    load_dotenv()  # reads .env in the project root
    setup_logging()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print(
            "❌ Error: GEMINI_API_KEY is not set.\n"
            "   Create a .env file with:\n"
            "   GEMINI_API_KEY=your_api_key_here\n"
            "   Or export it in your shell."
        )
        sys.exit(1)

    # --- 2. Create the chatbot ----------------------------------------------
    try:
        bot = TravelChatbot(api_key=api_key)
    except Exception as exc:
        print(f"❌ Failed to initialise the chatbot: {exc}")
        logger.exception("Initialisation error")
        sys.exit(1)

    # --- 3. Welcome the user ------------------------------------------------
    print_banner()
    print("Ask me anything about travel! Type 'help' for commands.\n")

    # --- 4. Main conversation loop ------------------------------------------
    while True:
        try:
            user_input = input(PROMPT_SYMBOL).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Goodbye! Happy travels!")
            logger.info("Session ended via keyboard interrupt.")
            break

        # Handle empty input
        if not validate_input(user_input):
            print("⚠️  Please enter a message (or type 'help' for commands).")
            continue

        # Handle commands (case-insensitive)
        command = user_input.lower()

        if command == "exit":
            print("\n👋 Goodbye! Happy travels!")
            logger.info("Session ended by user.")
            break

        if command == "help":
            print_help()
            continue

        if command == "reset":
            bot.reset()
            print("🔄 Conversation cleared — let's start fresh!\n")
            continue

        if command == "history":
            history = bot.get_history()
            if not history:
                print("📭 No conversation history yet.\n")
            else:
                print("\n📜 Conversation History")
                print("─" * 40)
                for entry in history:
                    role = "You" if entry["role"] == "user" else "TravelBot"
                    # Truncate long messages for readability
                    text = entry["text"]
                    if len(text) > 200:
                        text = text[:200] + "…"
                    print(f"  [{role}]: {text}\n")
                print("─" * 40 + "\n")
            continue

        # Send to the chatbot
        try:
            reply = bot.send_message(user_input)
            print(f"{BOT_PREFIX}\n{reply}\n")
        except RuntimeError as exc:
            print(f"❌ {exc}\n")


if __name__ == "__main__":
    main()
