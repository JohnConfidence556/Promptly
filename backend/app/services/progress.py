"""A tiny channel for 'what is happening right now' messages.

Deep code (the Coder, the retry loop) announces events with emit(). Whoever runs
the build installs a sink that forwards them to the browser. With no sink
installed, emit() does nothing, so tests and scripts need no setup.
"""

from collections.abc import Callable
from contextvars import ContextVar, Token

_sink: "ContextVar[Callable[[dict], None] | None]" = ContextVar(
    "progress_sink", default=None
)


def set_sink(sink: "Callable[[dict], None] | None") -> Token:
    return _sink.set(sink)


def reset_sink(token: Token) -> None:
    _sink.reset(token)


def emit(event: dict) -> None:
    sink = _sink.get()
    if sink is not None:
        sink(event)