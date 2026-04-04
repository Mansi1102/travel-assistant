# Travel Assistant Chatbot

A travel assistant powered by **Google Gemini** with **tool calling** — it fetches real-time weather and currency data automatically when needed. Available as both a CLI chatbot and a web UI.

---

## Project Structure

```
travel-assistant/
├── main.py            # CLI chatbot loop
├── app.py             # Flask web UI + API
├── chatbot.py         # TravelChatbot class (Gemini chat + memory)
├── config.py          # Model settings, system prompt, tool registration
├── tools.py           # Tool functions (weather, currency) — auto-called by Gemini
├── utils.py           # Logging, input validation, display helpers
├── templates/
│   └── index.html     # Web UI (chat interface)
├── requirements.txt   # Python dependencies
└── .env               # API keys (not committed)
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- A Google Gemini API key — get one free at [Google AI Studio](https://aistudio.google.com/apikey)

### Install

```bash
cd travel-assistant
pip install -r requirements.txt
```

### Set Your API Key

```bash
# Create .env file
echo 'GEMINI_API_KEY=your_key_here' > .env
```

### Run

**Web UI** (recommended):

```bash
python app.py
# Open http://localhost:5001
```

**CLI**:

```bash
python main.py
```

---

## Tool Calling

Gemini automatically decides when to call external tools and uses the results in its response. No keyword matching — the LLM chooses.

### Available Tools

| Tool | What it does | API used | API key needed? |
|---|---|---|---|
| `get_weather` | Current weather for any city | Open-Meteo + Nominatim | No |
| `get_currency_rate` | Currency conversion | open.er-api.com | No |

### How It Works

```
User: "What's the weather in Goa?"
         │
         ▼
   Gemini decides → call get_weather("Goa", "India")
         │
         ▼
   SDK auto-executes the Python function
         │
         ▼
   Result: {temperature: 30.1, description: "Partly cloudy", ...}
         │
         ▼
   Gemini weaves data into natural response:
   "It's currently 30°C in Goa with partly cloudy skies..."
```

Tools are registered in `config.py` by passing Python functions directly:

```python
CHAT_CONFIG = types.GenerateContentConfig(
    system_instruction=_SYSTEM_INSTRUCTION,
    tools=[get_weather, get_currency_rate],
)
```

The `google-genai` SDK inspects function signatures and docstrings to generate schemas automatically. No manual schema definitions needed.

### Sample Queries That Trigger Tools

- "What's the weather in Goa?" → `get_weather`
- "Convert 500 USD to INR" → `get_currency_rate`
- "Plan a trip to Tokyo" → no tool (pure LLM)
- "Plan a trip to Bali, how's the weather?" → `get_weather` + itinerary

---

## CLI Commands

| Command   | Description                     |
|-----------|---------------------------------|
| `help`    | Show available commands         |
| `reset`   | Clear chat history, start fresh |
| `history` | Display conversation so far     |
| `exit`    | Quit the chatbot                |

---

## Web UI Features

- Chat bubbles with markdown rendering (bold, headers, lists, tables)
- Typing indicator while waiting for response
- Quick-start suggestion chips
- Reset button for new conversations
- Responsive design (works on mobile)

---

## How It Works

1. **`tools.py`** — Pure Python functions that call free APIs (no API keys needed). `get_weather` uses Nominatim for geocoding + Open-Meteo for weather data. `get_currency_rate` uses open.er-api.com.

2. **`config.py`** — Registers tools with Gemini via `GenerateContentConfig(tools=[...])`. Also defines the system prompt, model name, and generation parameters.

3. **`chatbot.py`** — `TravelChatbot` creates a `client.chats.create()` session with tools enabled. When `send_message()` is called, the SDK handles the full tool-calling loop automatically (Automatic Function Calling).

4. **`app.py`** — Flask backend with `/api/chat`, `/api/reset`, `/api/history` endpoints. Each browser session gets its own chatbot instance.

5. **`main.py`** — CLI loop with command handling (`exit`, `reset`, `history`, `help`).

### Multi-Turn Memory

The chat session maintains full conversation history. Each `send_message()` appends both the user message and model response, so the bot always has context of prior turns.

---

## Logging

Logs are written to `logs/travel_assistant.log` with DEBUG-level detail. Tool calls, API requests, and errors are all captured. Only warnings and errors appear on the console.

---

## Adding New Tools

1. Add a function to `tools.py` with a clear docstring and type hints
2. Import and add it to the `tools=[...]` list in `config.py`
3. Mention it in the system prompt so Gemini knows when to use it

The SDK auto-generates the schema from the function signature. No manual JSON schema needed.

---

## License

MIT
