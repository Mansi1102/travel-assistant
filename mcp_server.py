"""
MCP Server — FastAPI application that exposes registered tools over HTTP.

Endpoints
---------
GET  /          Health check
GET  /tools     List every registered tool with its parameter schema
POST /execute   Run a tool by name with the supplied parameters
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from executor import ToolExecutor
from tool_registry import ToolRegistry, registry
from tools import get_currency_rate, get_weather
from utils import setup_logging

logger = logging.getLogger(__name__)


# ── Pydantic models ───────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    """Payload for POST /execute."""

    tool_name: str = Field(..., examples=["get_weather"])
    parameters: dict[str, Any] = Field(
        default_factory=dict, examples=[{"city": "Goa", "country": "India"}]
    )


class MCPResponse(BaseModel):
    """Uniform envelope returned by every endpoint."""

    success: bool
    result: Any = None
    error: str | None = None
    execution_time_ms: float | None = None


# ── bootstrap ─────────────────────────────────────────────────────────

def _register_tools(reg: ToolRegistry) -> None:
    """Register all available tools at startup."""
    reg.register(get_weather, description="Get current weather for a city")
    reg.register(
        get_currency_rate,
        description="Convert an amount between currencies",
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging(logging.DEBUG)
    _register_tools(registry)
    logger.info(
        "MCP server started — %d tool(s) registered.", len(registry)
    )
    yield
    logger.info("MCP server shutting down.")


# ── app creation ──────────────────────────────────────────────────────

app = FastAPI(
    title="Travel Assistant MCP Server",
    description="Exposes weather, currency, and other tools over HTTP "
    "so AI agents can call them dynamically.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ToolExecutor(registry)


# ── middleware ─────────────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "%s %s → %d (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


# ── routes ─────────────────────────────────────────────────────────────

@app.get("/", response_model=MCPResponse)
async def health_check():
    """Health check — confirms the server is running."""
    return MCPResponse(
        success=True,
        result={
            "status": "healthy",
            "tools_registered": len(registry),
        },
    )


@app.get("/tools", response_model=MCPResponse)
async def list_tools():
    """Return metadata for every registered tool."""
    return MCPResponse(success=True, result=registry.list_tools())


@app.post("/execute", response_model=MCPResponse)
async def execute_tool(req: ExecuteRequest):
    """Run a tool and return the result."""
    result = await executor.run_async(req.tool_name, req.parameters)

    return MCPResponse(
        success=result["success"],
        result=result.get("result"),
        error=result.get("error"),
        execution_time_ms=result.get("execution_time_ms"),
    )


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error. Check server logs.",
        },
    )


# ── entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print("\n  MCP Server running at http://localhost:8000")
    print("  Docs at         http://localhost:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
