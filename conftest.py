"""Root conftest — stub missing third-party packages for unit tests.

The agents/ package imports from deepagents, langchain, langchain_anthropic,
and langgraph at module level. These are optional runtime dependencies that
may not be installed in the test environment. We pre-populate sys.modules
with lightweight MagicMock stubs so that:

  1. ``import agents.player`` / ``import agents.coach`` succeed.
  2. Tests can ``patch("agents.player.create_agent")`` at the import site.
  3. isinstance() checks on middleware classes work (each class is a unique
     MagicMock whose instances report the correct ``type().__name__``).

The stubs are injected only when the real packages are missing (try/import
guard), so this conftest is a no-op in environments where the packages are
installed.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


def _stub_module(name: str, attrs: dict | None = None) -> ModuleType:
    """Create a stub module and register it in sys.modules."""
    mod = ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _make_class_stub(class_name: str) -> type:
    """Create a real class (not a MagicMock) so isinstance() works in tests."""

    class _Stub:
        def __init__(self, **kwargs: object) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

    _Stub.__name__ = class_name
    _Stub.__qualname__ = class_name
    return _Stub


# ---------------------------------------------------------------------------
# deepagents stubs
# ---------------------------------------------------------------------------

try:
    import deepagents  # noqa: F401
except ModuleNotFoundError:
    _FilesystemBackend = _make_class_stub("FilesystemBackend")
    _MemoryMiddleware = _make_class_stub("MemoryMiddleware")
    _FilesystemMiddleware = _make_class_stub("FilesystemMiddleware")
    _PatchToolCallsMiddleware = _make_class_stub("PatchToolCallsMiddleware")

    _stub_module("deepagents")
    _stub_module("deepagents.backends", {"FilesystemBackend": _FilesystemBackend})
    _stub_module(
        "deepagents.middleware",
        {
            "MemoryMiddleware": _MemoryMiddleware,
            "FilesystemMiddleware": _FilesystemMiddleware,
        },
    )
    _stub_module(
        "deepagents.middleware.patch_tool_calls",
        {"PatchToolCallsMiddleware": _PatchToolCallsMiddleware},
    )

# ---------------------------------------------------------------------------
# langchain stubs
# ---------------------------------------------------------------------------

try:
    import langchain  # noqa: F401
except ModuleNotFoundError:
    _stub_module("langchain")
    _stub_module("langchain.agents", {"create_agent": MagicMock(name="create_agent")})
    _stub_module(
        "langchain.chat_models",
        {"init_chat_model": MagicMock(name="init_chat_model")},
    )

try:
    import langchain_core  # noqa: F401
except ModuleNotFoundError:

    def _tool_decorator(func: object = None, **kwargs: object):  # type: ignore[assignment]
        """Stub for @tool decorator — returns the function unchanged."""
        if func is not None:
            return func
        return lambda f: f

    _BaseTool = type("BaseTool", (), {})

    _stub_module("langchain_core")
    _stub_module(
        "langchain_core.language_models",
        {"BaseChatModel": type("BaseChatModel", (), {})},
    )
    _stub_module(
        "langchain_core.tools",
        {"tool": _tool_decorator, "BaseTool": _BaseTool},
    )

# ---------------------------------------------------------------------------
# langchain_anthropic stubs
# ---------------------------------------------------------------------------

try:
    import langchain_anthropic  # noqa: F401
except ModuleNotFoundError:
    _AnthropicPromptCachingMiddleware = _make_class_stub(
        "AnthropicPromptCachingMiddleware"
    )
    _stub_module("langchain_anthropic")
    _stub_module(
        "langchain_anthropic.middleware",
        {"AnthropicPromptCachingMiddleware": _AnthropicPromptCachingMiddleware},
    )

# ---------------------------------------------------------------------------
# langgraph stubs
# ---------------------------------------------------------------------------

try:
    import langgraph  # noqa: F401
except ModuleNotFoundError:
    _stub_module("langgraph")
    _stub_module("langgraph.graph", {"END": "END", "StateGraph": MagicMock(name="StateGraph")})
    _stub_module("langgraph.graph.state", {"CompiledStateGraph": type("CompiledStateGraph", (), {})})
