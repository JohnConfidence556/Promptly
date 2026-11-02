import httpx
import pytest
from groq import RateLimitError

from app.services import llm
from app.services.errors import LLMError
from app.services.retry import (
    MAX_RETRY_AFTER_SECONDS,
    RETRY_AFTER_MARGIN_SECONDS,
    run_with_retry,
)

from app.services import progress


def make_rate_limit_error(message="", headers=None):
    request = httpx.Request("POST", "https://api.groq.com/test")
    response = httpx.Response(429, headers=headers or {}, request=request)
    body = {"error": {"message": message, "code": "rate_limit_exceeded"}}
    return RateLimitError("rate limited", response=response, body=body)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Please try again in 3.285s. Need more tokens?", 3.285),
        ("Please try again in 250ms.", 0.25),
        ("Please try again in 14m25.248s.", 865.248),
        ("Please try again in 1h2m3s.", 3723.0),
        ("No hint in this message.", None),
    ],
)
def test_parse_retry_after(text, expected):
    result = llm.parse_retry_after(text)

    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


def test_hint_from_message_is_kept():
    error = llm._translate_groq_error(
        make_rate_limit_error("Please try again in 3.285s.")
    )

    assert error.retryable is True
    assert error.retry_after == pytest.approx(3.285)


def test_retry_after_header_wins_over_message():
    error = llm._translate_groq_error(
        make_rate_limit_error(
            "Please try again in 3.285s.", headers={"retry-after": "7"}
        )
    )

    assert error.retry_after == 7.0


def test_rate_limit_without_hint_has_no_retry_after():
    error = llm._translate_groq_error(make_rate_limit_error("Slow down."))

    assert error.retryable is True
    assert error.retry_after is None


def test_very_long_wait_is_not_retried():
    error = llm._translate_groq_error(
        make_rate_limit_error("Please try again in 14m25.248s.")
    )

    assert error.retryable is False
    assert error.retry_after == pytest.approx(865.248)


def run_and_record(retry_after):
    sleeps = []
    attempts = {"count": 0}

    def operation():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise LLMError("limited", retryable=True, retry_after=retry_after)
        return "ok"

    result = run_with_retry(
        operation, sleep=sleeps.append, random_value=lambda: 0.0
    )
    return result, sleeps


def test_retry_waits_for_the_providers_hint():
    result, sleeps = run_and_record(5.0)

    assert result == "ok"
    assert sleeps == [pytest.approx(5.0 + RETRY_AFTER_MARGIN_SECONDS)]


def test_retry_caps_very_long_hints():
    _, sleeps = run_and_record(500.0)

    assert sleeps == [
        pytest.approx(MAX_RETRY_AFTER_SECONDS + RETRY_AFTER_MARGIN_SECONDS)
    ]


def test_small_hint_does_not_shorten_normal_backoff():
    _, sleeps = run_and_record(0.1)

    assert sleeps == [pytest.approx(1.0)]


def test_retry_announces_a_rate_limit_wait():
    received = []
    token = progress.set_sink(received.append)
    try:
        run_and_record(5.0)
    finally:
        progress.reset_sink(token)

    assert received == [{"kind": "waiting", "seconds": 5.5, "reason": "rate_limit"}]


def test_plain_retries_are_announced_too():
    received = []
    token = progress.set_sink(received.append)
    try:
        run_and_record(None)
    finally:
        progress.reset_sink(token)

    assert received == [{"kind": "waiting", "seconds": 1.0, "reason": "retry"}]