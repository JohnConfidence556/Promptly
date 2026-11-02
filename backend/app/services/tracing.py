"""Optional Langfuse tracing. Does nothing unless Langfuse keys are configured."""

import logging
import os
from contextlib import ExitStack, contextmanager

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


class Recorder:
    """Wraps a Langfuse observation so a tracing problem can never break a build."""

    def __init__(self, observation=None):
        self._observation = observation

    def update(self, **fields) -> None:
        if self._observation is None:
            return

        try:
            self._observation.update(**fields)
        except Exception:
            logger.debug("Langfuse update failed.", exc_info=True)


@contextmanager
def observation(kind: str, name: str, **fields):
    """Open a Langfuse 'span' or 'generation' and yield a Recorder."""
    with ExitStack() as stack:
        recorder = Recorder()

        if enabled():
            try:
                from langfuse import get_client

                handle = stack.enter_context(
                    get_client().start_as_current_observation(
                        as_type=kind, name=name, **fields
                    )
                )
                recorder = Recorder(handle)
            except Exception:
                logger.warning("Langfuse tracing is unavailable.", exc_info=True)

        yield recorder


def tag_trace(user_id: str | None = None, tags: list[str] | None = None) -> None:
    if not enabled():
        return

    try:
        from langfuse import get_client

        get_client().update_current_trace(user_id=user_id, tags=tags)
    except Exception:
        logger.debug("Langfuse trace tagging failed.", exc_info=True)


def flush() -> None:
    """Send any queued traces. Called when the server shuts down."""
    if not enabled():
        return

    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        logger.debug("Langfuse flush failed.", exc_info=True)