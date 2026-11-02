from types import SimpleNamespace
from unittest.mock import Mock

import httpx

from groq import RateLimitError

from app.services import llm


def test_groq_rate_limit_is_retried_across_modules(monkeypatch):
    response = httpx.Response(
        429,
        request=httpx.Request(
            "POST", "https://api.groq.com/openai/v1/chat/completions"
        ),
        json={
            "error": {
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded",
            }
        },
    )

    rate_limit_error = RateLimitError(
        "Rate limit exceeded",
        response=response,
        body=response.json(),
    )

    successful_response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        ),
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content="Test response",
                    tool_calls=None,
                ),
                finish_reason="stop",
            )
        ],
    )

    create = Mock(
        side_effect=[
            rate_limit_error,
            rate_limit_error,
            successful_response,
        ]
    )

    monkeypatch.setattr(
        llm.client.chat.completions,
        "create",
        create,
    )

    # Avoid real waiting during retries.
    monkeypatch.setattr(
        "app.services.retry.time.sleep",
        lambda _: None,
    )

    result = llm._create_completion(
        model="test-model",
        messages=[{"role": "user", "content": "test"}],
    )

    assert result is successful_response
    assert create.call_count == 3
