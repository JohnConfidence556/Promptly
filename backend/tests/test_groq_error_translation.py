
import httpx
import pytest
from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from app.services.llm import _translate_groq_error


def make_status_error(status_code, error_body=None):
    request = httpx.Request(
        "POST",
        "https://api.groq.com/openai/v1/chat/completions",
    )
    response = httpx.Response(
        status_code,
        request=request,
        json=error_body or {},
    )
    return APIStatusError(
        f"HTTP {status_code}",
        response=response,
        body=error_body or {},
    )


def test_authentication_error_is_not_retryable():
    request = httpx.Request("POST", "https://api.groq.com")
    response = httpx.Response(401, request=request, json={})
    exc = AuthenticationError(
        "Invalid API key",
        response=response,
        body={},
    )

    result = _translate_groq_error(exc)

    assert result.retryable is False
    assert "authentication failed" in str(result).lower()


def test_rate_limit_is_retryable_under_current_policy():
    request = httpx.Request("POST", "https://api.groq.com")
    response = httpx.Response(429, request=request, json={})
    exc = RateLimitError(
        "Rate limit exceeded",
        response=response,
        body={},
    )

    result = _translate_groq_error(exc)

    assert result.retryable is True


def test_timeout_is_retryable():
    request = httpx.Request("POST", "https://api.groq.com")
    result = _translate_groq_error(APITimeoutError(request=request))

    assert result.retryable is True


def test_connection_error_is_retryable():
    request = httpx.Request("POST", "https://api.groq.com")
    exc = APIConnectionError(
        message="Connection failed",
        request=request,
    )

    result = _translate_groq_error(exc)

    assert result.retryable is True


@pytest.mark.parametrize("status_code", [408, 409, 500, 502, 503])
def test_temporary_status_codes_are_retryable(status_code):
    result = _translate_groq_error(make_status_error(status_code))

    assert result.retryable is True


def test_tool_use_failed_400_is_retryable():
    result = _translate_groq_error(
        make_status_error(
            400,
            {
                "error": {
                    "message": (
                        "Tool choice is required, but model did not call a tool"
                    ),
                    "type": "invalid_request_error",
                    "code": "tool_use_failed",
                }
            },
        )
    )

    assert result.retryable is True
    assert "tool choice is required" in str(result).lower()


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
def test_other_client_errors_are_not_retryable(status_code):
    result = _translate_groq_error(make_status_error(status_code))

    assert result.retryable is False



def test_quota_exhaustion_is_not_retryable():
    request = httpx.Request("POST", "https://api.groq.com")
    body = {
        "error": {
            "message": "Insufficient quota for this request",
            "type": "rate_limit_error",
            "code": "insufficient_quota",
        }
    }
    response = httpx.Response(429, request=request, json=body)
    exc = RateLimitError(
        "Rate limit exceeded",
        response=response,
        body=body,
    )

    result = _translate_groq_error(exc)

    assert result.retryable is False
    assert "quota" in str(result).lower()


def test_ordinary_rate_limit_remains_retryable():
    request = httpx.Request("POST", "https://api.groq.com")
    body = {
        "error": {
            "message": "Rate limit exceeded; please try again shortly",
            "type": "rate_limit_error",
            "code": "rate_limit_exceeded",
        }
    }
    response = httpx.Response(429, request=request, json=body)
    exc = RateLimitError(
        "Rate limit exceeded",
        response=response,
        body=body,
    )

    result = _translate_groq_error(exc)

    assert result.retryable is True
