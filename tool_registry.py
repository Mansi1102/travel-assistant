"""
Tool Registry — central catalogue of tools available to the MCP server.

Each tool has a callable, a human-readable description, and a parameter
schema so clients (AI agents) know what arguments to supply.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolParam:
    """Describes a single parameter for a registered tool."""

    name: str
    type: str
    required: bool = True
    default: Any = None
    description: str = ""


@dataclass(frozen=True)
class ToolInfo:
    """Metadata for a registered tool."""

    name: str
    description: str
    function: Callable[..., Any]
    parameters: list[ToolParam] = field(default_factory=list)


class ToolRegistry:
    """Thread-safe registry that maps tool names to callables + metadata."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolInfo] = {}

    def register(
        self,
        func: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        """Register a callable as a tool.

        If *name* or *description* are omitted they are derived from the
        function name and docstring respectively.  Parameter metadata is
        extracted automatically via :mod:`inspect`.
        """
        tool_name = name or func.__name__
        tool_desc = description or (inspect.getdoc(func) or "").split("\n")[0]

        params = _extract_params(func)
        info = ToolInfo(
            name=tool_name,
            description=tool_desc,
            function=func,
            parameters=params,
        )
        self._tools[tool_name] = info
        logger.info("Registered tool '%s' (%d params).", tool_name, len(params))

    def get(self, name: str) -> ToolInfo | None:
        """Return the :class:`ToolInfo` for *name*, or ``None``."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return a JSON-serialisable list of all registered tools."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                        "default": p.default,
                        "description": p.description,
                    }
                    for p in t.parameters
                ],
            }
            for t in self._tools.values()
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# ── helpers ────────────────────────────────────────────────────────────

_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _python_type_to_str(annotation: Any) -> str:
    """Best-effort conversion of a Python type annotation to a string tag."""
    if annotation is inspect.Parameter.empty:
        return "string"
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        return _TYPE_MAP.get(origin, "string")
    return _TYPE_MAP.get(annotation, "string")


def _extract_params(func: Callable[..., Any]) -> list[ToolParam]:
    """Derive :class:`ToolParam` entries from a function's signature."""
    sig = inspect.signature(func)
    doc_lines = (inspect.getdoc(func) or "").splitlines()

    param_docs: dict[str, str] = {}
    for line in doc_lines:
        stripped = line.strip()
        if stripped.startswith(("Args:", "Parameters:", "Returns:", "Raises:")):
            continue
        if ":" in stripped and not stripped.startswith("-"):
            key, _, desc = stripped.partition(":")
            key = key.strip().lstrip("-").strip()
            if key and not key[0].isupper():
                param_docs[key] = desc.strip()

    params: list[ToolParam] = []
    for pname, p in sig.parameters.items():
        if pname == "self":
            continue
        has_default = p.default is not inspect.Parameter.empty
        params.append(
            ToolParam(
                name=pname,
                type=_python_type_to_str(p.annotation),
                required=not has_default,
                default=p.default if has_default else None,
                description=param_docs.get(pname, ""),
            )
        )
    return params


# ── singleton ──────────────────────────────────────────────────────────

registry = ToolRegistry()
