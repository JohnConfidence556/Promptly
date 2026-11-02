from types import SimpleNamespace

import httpx
import pytest
from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from app.services import llm
from app.services.errors import LLMError


def make_status_error(error_cls, status_code, body=None):
    """Build a real Groq SDK exception the way the SDK would."""
    request = httpx.Request("POST", "https://api.groq.com/test")
    response = httpx.Response(status_code, request=request)
    return error_cls("test error", response=response, body=body)


def fake_response(text="ok"):
    """A minimal stand-in for a successful Groq response."""
    message = SimpleNamespace(content=text, tool_calls=None)
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


class FakeClient:
    """Plays back a scripted list of outcomes and counts the calls."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome



def test_retries_rate_limit_then_succeeds(monkeypatch):
    client = FakeClient([
        make_status_error(RateLimitError, 429),
        make_status_error(RateLimitError, 429),
        fake_response("hello"),
    ])
    monkeypatch.setattr(llm, "client", client)

    assert llm.ask("hi") == "hello"
    assert client.calls == 3


def test_auth_error_is_not_retried(monkeypatch):
    client = FakeClient([make_status_error(AuthenticationError, 401)])
    monkeypatch.setattr(llm, "client", client)

    with pytest.raises(LLMError):
        llm.ask("hi")

    assert client.calls == 1


def test_gives_up_after_five_attempts(monkeypatch):
    client = FakeClient(
        [make_status_error(RateLimitError, 429) for _ in range(6)]
    )
    monkeypatch.setattr(llm, "client", client)

    with pytest.raises(LLMError, match="5 attempts"):
        llm.ask("hi")

    assert client.calls == 5


@pytest.mark.parametrize(
    "error_cls, status, expected_retryable",
    [
        (AuthenticationError, 401, False),
        (RateLimitError, 429, True),
        (APIStatusError, 408, True),
        (APIStatusError, 500, True),
        (APIStatusError, 503, True),
        (APIStatusError, 404, False),
    ],
)
def test_translation_sets_retryable_flag(error_cls, status, expected_retryable):
    translated = llm._translate_groq_error(make_status_error(error_cls, status))

    assert isinstance(translated, LLMError)
    assert translated.retryable is expected_retryable


def test_timeout_and_connection_errors_are_retryable():
    request = httpx.Request("POST", "https://api.groq.com/test")

    for error in (
        APITimeoutError(request=request),
        APIConnectionError(request=request),
    ):
        assert llm._translate_groq_error(error).retryable is True


def test_model_generation_400_is_retryable():
    body = {
        "error": {
            "message": "Tool choice is required, but model did not call a tool.",
            "code": "tool_use_failed",
        }
    }
    translated = llm._translate_groq_error(
        make_status_error(APIStatusError, 400, body)
    )

    assert translated.retryable is True


def test_ordinary_400_is_not_retryable():
    body = {"error": {"message": "Unknown parameter: foo", "code": "invalid_request"}}
    translated = llm._translate_groq_error(
        make_status_error(APIStatusError, 400, body)
    )

    assert translated.retryable is False