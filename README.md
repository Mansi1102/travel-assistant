# Travel Assistant Chatbot

A travel assistant powered by **Google Gemini** with **tool calling** and an **MCP server** . Available as a CLI chatbot, a web UI, and as a standalone MCP API server.

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
├── agent.py           # AI agent — Gemini reasoning + MCP tool calls
├── mcp_server.py      # FastAPI MCP server — exposes tools over HTTP
├── tool_registry.py   # Tool registry with metadata + parameter schemas
├── executor.py        # Safe dynamic tool execution engine
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

**AI Agent** (MCP-powered):

```bash
# Terminal 1 — start MCP server
python mcp_server.py

# Terminal 2 — start agent
python agent.py
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

## MCP Server

The project includes a **Model Context Protocol (MCP)-style server** built with FastAPI. It exposes all tools over HTTP so any AI agent or client can discover and call them dynamically.

### Architecture

```
┌──────────────────────────┐
│   AI Agent / Client      │
└─────┬──────────┬─────────┘
      │ GET      │ POST
      │ /tools   │ /execute
      ▼          ▼
┌──────────────────────────┐
│  mcp_server.py (FastAPI) │
└─────┬──────────┬─────────┘
      │          │
      ▼          ▼
┌────────────┐ ┌───────────┐
│  Registry  │ │ Executor  │
│  (catalog) │ │ (runner)  │
└────────────┘ └─────┬─────┘
                     ▼
              ┌────────────┐
              │  tools.py  │
              └────────────┘
```

### Run the MCP Server

```bash
python mcp_server.py
# Server:  http://localhost:8000
# Swagger: http://localhost:8000/docs
```

### API Endpoints

| Method | Path       | Description                        |
|--------|------------|------------------------------------|
| GET    | `/`        | Health check                       |
| GET    | `/tools`   | List all tools + parameter schemas |
| POST   | `/execute` | Execute a tool by name             |

### Example Requests

**List tools:**
```bash
curl http://localhost:8000/tools
```

**Execute weather tool:**
```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "get_weather", "parameters": {"city": "Goa", "country": "India"}}'
```

**Execute currency tool:**
```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "get_currency_rate", "parameters": {"from_currency": "USD", "to_currency": "INR", "amount": 100}}'
```

**Response format** (all endpoints):
```json
{
  "success": true,
  "result": { },
  "error": null,
  "execution_time_ms": 83.03
}
```

### MCP Components

| File                | Role                                                         |
|---------------------|--------------------------------------------------------------|
| `tool_registry.py`  | Registers tools + auto-extracts param schemas from signatures |
| `executor.py`       | Validates params, runs tools safely, returns structured results |
| `mcp_server.py`     | FastAPI app with routes, CORS, logging middleware, error handling |

### Scaling Suggestions

- **Auth**: Add API key or OAuth2 middleware to protect `/execute`
- **Rate limiting**: Use `slowapi` or a reverse proxy (nginx/Caddy)
- **More tools**: Add function to `tools.py`, call `registry.register(func)` in `mcp_server.py`
- **Async tools**: The executor already uses a thread pool — swap in `asyncio` native calls for IO-bound tools

---

## AI Agent (`agent.py`)

A ReAct-style agent that uses Gemini for reasoning and calls MCP tools dynamically — no hardcoded keyword matching.

### How It Works

```
User: "What's the weather in Tokyo?"
  │
  ▼
Agent sends query to Gemini with tool catalog
  │
  ▼
Gemini returns: {"action": "tool_call", "tool_name": "get_weather", ...}
  │
  ▼
Agent calls MCP server: POST /execute
  │
  ▼
Agent feeds tool result back to Gemini
  │
  ▼
Gemini returns: {"action": "respond", "message": "It's 19°C in Tokyo..."}
  │
  ▼
Agent displays final answer to user
```

### Features

- **LLM-driven decisions**: Gemini decides when to call tools — no `if "weather"` logic
- **Dynamic tool discovery**: fetches available tools from MCP at startup
- **Multi-round**: supports chained tool calls (up to 3 rounds per query)
- **Retry on failure**: retries MCP calls on transient errors
- **Conversation memory**: maintains full chat history across turns
- **Structured output**: Gemini responds with JSON (`tool_call` or `respond`)

### Agent Commands

| Command | Description              |
|---------|--------------------------|
| `tools` | List available MCP tools |
| `reset` | Clear conversation       |
| `exit`  | Quit                     |

---

## Adding New Tools

1. Add a function to `tools.py` with a clear docstring and type hints
2. **For Gemini chatbot**: Import and add it to the `tools=[...]` list in `config.py`; mention it in the system prompt
3. **For MCP server**: Call `registry.register(your_func)` in `_register_tools()` inside `mcp_server.py`

Both the Gemini SDK and the MCP registry auto-generate schemas from function signatures and docstrings. No manual JSON schema needed.

---

## License

MIT
