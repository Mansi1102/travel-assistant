"""
Travel Assistant Chatbot — Web UI (Flask)

Run with:  python app.py
"""

import logging
import os
import sys
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

from chatbot import TravelChatbot
from utils import setup_logging

load_dotenv()
setup_logging()

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(32)

_bots: dict[str, TravelChatbot] = {}


def _get_bot() -> TravelChatbot:
    """Return the TravelChatbot bound to the current browser session."""
    sid = session.get("sid")
    if sid and sid in _bots:
        return _bots[sid]

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    sid = uuid.uuid4().hex
    session["sid"] = sid
    bot = TravelChatbot(api_key=api_key)
    _bots[sid] = bot
    return bot


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()

    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    try:
        bot = _get_bot()
        reply = bot.send_message(user_msg)
        return jsonify({"reply": reply})
    except RuntimeError as exc:
        logger.exception("Chat error")
        return jsonify({"error": str(exc)}), 502


@app.route("/api/reset", methods=["POST"])
def reset():
    try:
        bot = _get_bot()
        bot.reset()
        return jsonify({"status": "ok"})
    except RuntimeError as exc:
        logger.exception("Reset error")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/history", methods=["GET"])
def history():
    try:
        bot = _get_bot()
        return jsonify({"history": bot.get_history()})
    except RuntimeError as exc:
        logger.exception("History error")
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print(
            "Error: GEMINI_API_KEY is not set.\n"
            "Create a .env file with:\n"
            "  GEMINI_API_KEY=your_api_key_here"
        )
        sys.exit(1)

    port = int(os.getenv("PORT", 5001))
    print(f"\n  Travel Assistant UI running at http://localhost:{port}\n")
    app.run(debug=False, port=port)
