"""
Core TravelChatbot class — wraps the Google Gemini API for multi-turn travel
conversation.
"""

import logging

from google import genai
from google.genai import types

from config import CHAT_CONFIG, MODEL_NAME

logger = logging.getLogger(__name__)


class TravelChatbot:
    """A travel assistant chatbot powered by Google Gemini."""

    def __init__(self, api_key: str) -> None:
        """
        Configure the Gemini client and start a fresh chat session.

        Args:
            api_key: Google Gemini API key.
        """
        self._client = genai.Client(api_key=api_key)
        self._chat = self._client.chats.create(
            model=MODEL_NAME,
            config=CHAT_CONFIG,
        )
        logger.info("TravelChatbot initialised with model '%s'.", MODEL_NAME)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_message(self, user_input: str) -> str:
        """
        Send a message to the chatbot and return the assistant's reply.

        Args:
            user_input: The user's message text.

        Returns:
            The assistant's response text.

        Raises:
            RuntimeError: If the API call fails.
        """
        try:
            logger.debug("User message: %s", user_input)
            response = self._chat.send_message(message=user_input)
            reply = response.text
            logger.debug("Bot reply: %s", reply)
            return reply
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            raise RuntimeError(
                "Sorry, something went wrong while contacting the AI. "
                "Please try again."
            ) from exc

    def reset(self) -> None:
        """Clear conversation history and start a new chat session."""
        self._chat = self._client.chats.create(
            model=MODEL_NAME,
            config=CHAT_CONFIG,
        )
        logger.info("Chat session has been reset.")

    def get_history(self) -> list[dict]:
        """
        Return the conversation history as a list of dicts.

        Each dict has keys ``role`` ('user' or 'model') and ``text``.
        """
        history = []
        for message in self._chat.history:
            history.append(
                {
                    "role": message.role,
                    "text": message.parts[0].text,
                }
            )
        return history
