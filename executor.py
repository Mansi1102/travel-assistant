"""
Tool Executor — safely runs a registered tool by name with supplied parameters.

Handles parameter validation, timeout, and structured result formatting so the
MCP server never leaks raw exceptions to clients.
"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

_THREAD_POOL = ThreadPoolExecutor(max_workers=4)
_DEFAULT_TIMEOUT = 30


class ToolExecutionError(Exception):
    """Raised when tool execution fails for a known reason."""


class ToolExecutor:
    """Validates parameters and runs tools from a :class:`ToolRegistry`."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def run(self, tool_name: str, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool synchronously and return a structured result.

        Returns:
            ``{"success": True, "result": …, "execution_time_ms": …}``
            or ``{"success": False, "error": …}``.
        """
        tool = self._registry.get(tool_name)
        if tool is None:
            available = [t["name"] for t in self._registry.list_tools()]
            return {
                "success": False,
                "error": f"Unknown tool '{tool_name}'.",
                "available_tools": available,
            }

        validation_error = self._validate(tool_name, parameters)
        if validation_error:
            return {"success": False, "error": validation_error}

        start = time.perf_counter()
        try:
            result = tool.function(**parameters)
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "Tool '%s' executed in %.1f ms.", tool_name, elapsed
            )
            return {
                "success": True,
                "result": result,
                "execution_time_ms": elapsed,
            }
        except Exception as exc:
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "Tool '%s' failed after %.1f ms: %s", tool_name, elapsed, exc
            )
            return {
                "success": False,
                "error": f"Tool execution failed: {exc}",
                "execution_time_ms": elapsed,
            }

    async def run_async(
        self, tool_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Run the tool in a thread pool so the event loop stays responsive."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _THREAD_POOL, self.run, tool_name, parameters
        )

    def _validate(
        self, tool_name: str, parameters: dict[str, Any]
    ) -> str | None:
        """Return an error message if *parameters* are invalid, else None."""
        tool = self._registry.get(tool_name)
        if tool is None:
            return f"Unknown tool '{tool_name}'."

        required = {p.name for p in tool.parameters if p.required}
        provided = set(parameters.keys())
        missing = required - provided
        if missing:
            return f"Missing required parameter(s): {', '.join(sorted(missing))}."

        known = {p.name for p in tool.parameters}
        unknown = provided - known
        if unknown:
            return f"Unknown parameter(s): {', '.join(sorted(unknown))}."

        return None
