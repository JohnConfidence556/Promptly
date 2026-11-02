import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar
from app.services import progress

from app.services.errors import LLMError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# A provider's "try again in X seconds" hint is honored up to this cap.
# Longer waits (for example a daily limit) are not worth blocking on.
MAX_RETRY_AFTER_SECONDS = 30.0

# Extra seconds added on top of the provider's hint, as a safety margin.
RETRY_AFTER_MARGIN_SECONDS = 0.5


def run_with_retry(
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 4.0,
    jitter: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> T:
    """Run an operation with bounded retries for retryable LLM errors."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    if base_delay < 0 or max_delay < 0 or jitter < 0:
        raise ValueError("Delay and jitter values cannot be negative.")

    for attempt in range(1, max_attempts + 1):
        try:
            return operation()

        except LLMError as exc:
            if not exc.retryable:
                raise

            if attempt == max_attempts:
                raise LLMError(
                    f"Operation failed after {attempt} attempts: {exc}",
                    retryable=False,
                ) from exc

            exponential_delay = min(
                base_delay * (2 ** (attempt - 1)),
                max_delay,
            )

            # random_value() is between 0 and 1.
            # Add jitter from 0 up to jitter seconds.
            wait = exponential_delay + (random_value() * jitter)

            # If the provider told us how long to wait, never wait less.
            if exc.retry_after is not None:
                hinted_wait = (
                    min(exc.retry_after, MAX_RETRY_AFTER_SECONDS)
                    + RETRY_AFTER_MARGIN_SECONDS
                )
                wait = max(wait, hinted_wait)

            logger.warning(
                "Retrying in %.1fs (attempt %s of %s failed): %s",
                wait,
                attempt,
                max_attempts,
                exc,
            )

            progress.emit(
                {
                    "kind": "waiting",
                    "seconds": round(wait, 1),
                    "reason": "rate_limit" if exc.retry_after is not None else "retry",
                }
            )
            sleep(wait)

    # Defensive fallback; the loop always returns or raises.
    raise RuntimeError("Retry loop exited unexpectedly.")