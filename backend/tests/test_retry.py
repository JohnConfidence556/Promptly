
import pytest

from app.services.errors import LLMError
from app.services.retry import run_with_retry


def test_succeeds_on_first_attempt():
    calls = []

    def operation():
        calls.append(1)
        return "success"

    result = run_with_retry(operation, sleep=lambda _: None)

    assert result == "success"
    assert len(calls) == 1


def test_fails_twice_then_succeeds():
    calls = []
    waits = []

    def operation():
        calls.append(1)
        if len(calls) < 3:
            raise LLMError("Temporary failure", retryable=True)
        return "success"

    result = run_with_retry(
        operation,
        sleep=waits.append,
        random_value=lambda: 0,
    )

    assert result == "success"
    assert len(calls) == 3
    assert waits == [1.0, 2.0]


def test_stops_at_attempt_cap():
    calls = []
    waits = []

    def operation():
        calls.append(1)
        raise LLMError("Still failing", retryable=True)

    with pytest.raises(LLMError, match="after 3 attempts") as exc_info:
        run_with_retry(
            operation,
            max_attempts=3,
            sleep=waits.append,
            random_value=lambda: 0,
        )

    assert "Still failing" in str(exc_info.value)
    assert exc_info.value.retryable is False


def test_non_retryable_error_is_not_retried():
    calls = []

    def operation():
        calls.append(1)
        raise LLMError("Invalid API key", retryable=False)

    with pytest.raises(LLMError, match="Invalid API key"):
        run_with_retry(operation, sleep=lambda _: None)

    assert len(calls) == 1


def test_waits_grow_between_attempts():
    calls = []
    waits = []

    def operation():
        calls.append(1)
        if len(calls) < 4:
            raise LLMError("Temporary failure", retryable=True)
        return "success"

    result = run_with_retry(
        operation,
        max_attempts=4,
        sleep=waits.append,
        random_value=lambda: 0,
    )

    assert result == "success"
    assert waits == [1.0, 2.0, 4.0]
    assert waits[0] < waits[1] < waits[2]
