import logging
from dataclasses import dataclass
from typing import Any

from groq import (
    Groq,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

import time
from app.services import progress, tracing

import re
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.services.errors import LLMError
from app.services.retry import MAX_RETRY_AFTER_SECONDS, run_with_retry

logger = logging.getLogger(__name__)

_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_SECONDS_PER_UNIT = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def parse_retry_after(text: str) -> float | None:
    """Read 'try again in 3.285s' (or '250ms', '14m25.248s') as seconds."""
    match = re.search(r"try again in\s+([0-9hms.]+)", text, re.IGNORECASE)
    if not match:
        return None

    parts = _DURATION_PART.findall(match.group(1))
    if not parts:
        return None

    return sum(
        float(number) * _SECONDS_PER_UNIT[unit] for number, unit in parts
    )


def _retry_after_seconds(exc: Exception, message: str) -> float | None:
    """Prefer the Retry-After header; fall back to the 'try again in' text."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    header_value = headers.get("retry-after") if headers is not None else None

    if header_value is not None:
        try:
            return float(header_value)
        except ValueError:
            pass

    return parse_retry_after(message)


@dataclass
class LLMResult:
    """Contains a model reply and its token usage."""
    reply: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass
class ToolCall:
    """A tool call requested by the language model."""

    id: str
    name: str
    arguments: str


@dataclass
class ToolCallResult:
    """A normalized response that may contain tool calls."""

    content: str | None
    tool_calls: list[ToolCall]
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


# Disable SDK retries so our application retry layer is the only retry loop.
#
# Worst-case budget for ONE logical request:
#   5 attempts (SDK retries disabled, so no multiplication with the SDK's own)
#   waits between attempts: normally 1s, 2s, 4s, 4s (plus jitter), but when
#   the provider says "try again in X s" we wait X (capped at 30s) plus 0.5s
#   each attempt can take up to the 20s timeout
#   worst case is about 5 x 20s + 4 x 30.5s = 222s
client = Groq(
    api_key=GROQ_API_KEY,
    max_retries=0,
    timeout=20.0,
)


def _translate_groq_error(exc: Exception) -> LLMError:
    """Translate a Groq SDK exception into our application's error type."""

    if isinstance(exc, AuthenticationError):
        return LLMError(
            "Groq authentication failed. Check your API key.",
            retryable=False,
        )


    if isinstance(exc, RateLimitError):
        body = getattr(exc, "body", None)
        error_info = body.get("error", {}) if isinstance(body, dict) else {}
        if not isinstance(error_info, dict):
            error_info = {}

        code = str(error_info.get("code", "")).lower()
        raw_message = str(error_info.get("message", ""))
        message = raw_message.lower()

        quota_indicators = (
            "insufficient_quota",
            "quota_exceeded",
            "billing_hard_limit",
            "quota exhausted",
            "billing limit",
            "out of credits",
        )

        quota_exhausted = any(
            indicator in code or indicator in message
            for indicator in quota_indicators
        )

        if quota_exhausted:
            logger.error(
                "Groq quota/billing limit detected: code=%s, message=%s",
                code or "unavailable",
                message or "unavailable",
            )
            return LLMError(
                "Groq quota or billing limit appears exhausted. "
                "Check your account limits before retrying.",
                retryable=False,
            )

        retry_after = _retry_after_seconds(exc, raw_message)

        logger.warning(
            "Groq rate limit encountered: code=%s, retry_after=%s, message=%s",
            code or "unavailable",
            retry_after,
            raw_message or "unavailable",
        )

        # A very long wait means a daily-style limit. Don't block on it.
        if retry_after is not None and retry_after > MAX_RETRY_AFTER_SECONDS:
            return LLMError(
                f"Groq rate limit reached; it resets in about "
                f"{int(retry_after)} seconds, which is too long to wait.",
                retryable=False,
                retry_after=retry_after,
            )

        return LLMError(
            "Groq rate limit reached. Try again later.",
            retryable=True,
            retry_after=retry_after,
        )
    

    if isinstance(exc, APITimeoutError):
        return LLMError(
            "The Groq request timed out.",
            retryable=True,
        )

    if isinstance(exc, APIConnectionError):
        return LLMError(
            "Could not connect to Groq.",
            retryable=True,
        )

    if isinstance(exc, APIStatusError):
        status = exc.status_code
        body = getattr(exc, "body", None)

        detail = None

        if isinstance(body, dict):
            error_info = body.get("error", {})
            if isinstance(error_info, dict):
                detail = error_info.get("message")

        if not detail:
            detail = getattr(exc, "message", None)

        logger.error(
            "Groq API error: status=%s, body=%r",
            status,
            body,
        )

        # Retry temporary server errors and request conflicts/timeouts.
        if status in (408, 409) or status >= 500:
            return LLMError(
                f"Groq returned a temporary API error (HTTP {status}).",
                retryable=True,
            )

        if status == 400 and detail:
            error_code = ""
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                error_code = str(body["error"].get("code", "")).lower()

            # The model failed to produce a usable tool call or JSON this time.
            # Model output is sampled, so a repeat can succeed.
            # Retries are still capped by run_with_retry.
            model_generation_failure = (
                error_code in ("tool_use_failed", "json_validate_failed")
                or "did not call a tool" in str(detail).lower()
            )

            return LLMError(
                f"Groq rejected the request: {str(detail)[:300]}",
                retryable=model_generation_failure,
            )

        # Other 4xx errors generally need the request or account corrected.
        return LLMError(
            f"Groq returned an API error (HTTP {status}).",
            retryable=False,
        )

    logger.exception("Unexpected error during Groq request.")
    return LLMError(
        "The Groq request failed unexpectedly.",
        retryable=False,
    )


def _create_completion(**request_args):
    """Send a completion request with bounded retries."""

    return run_with_retry(
        lambda: _create_completion_once(**request_args),
        max_attempts=5,
    )


def _trace_output(response) -> dict:
    if not response.choices:
        return {}

    message = response.choices[0].message
    return {
        "content": message.content,
        "tool_calls": [
            {"name": call.function.name, "arguments": call.function.arguments}
            for call in (message.tool_calls or [])
        ],
    }


def _create_completion_once(**request_args):
    """Make one Groq request, trace it, and translate any SDK exception."""
    started = time.monotonic()

    with tracing.observation(
        "generation",
        "groq-chat",
        model=request_args.get("model"),
        input=request_args.get("messages"),
    ) as trace:
        try:
            response = client.chat.completions.create(**request_args)
        except Exception as exc:
            trace.update(output={"error": str(exc)})
            raise _translate_groq_error(exc) from exc

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        trace.update(
            output=_trace_output(response),
            usage_details={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            },
        )

    # Token counts feed the run log; the browser never sees these events.
    progress.emit(
        {
            "kind": "llm",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "seconds": round(time.monotonic() - started, 2),
        }
    )
    return response


def _build_messages(prompt: str, system: str | None) -> list[dict[str, str]]:
    """Build the chat message list for a request."""
    messages = []

    if system:
        messages.append({"role": "system", "content": system})

    messages.append({"role": "user", "content": prompt})

    return messages


def _get_response(
    prompt: str,
    system: str | None = None,
    json_mode: bool = False,
    reasoning_effort: str | None = None,
):
    """Send a prompt to Groq and return the full response."""
    request_args = {
        "model": GROQ_MODEL,
        "messages": _build_messages(prompt, system),
    }

    if json_mode:
        request_args["response_format"] = {"type": "json_object"}

    if reasoning_effort:
        request_args["reasoning_effort"] = reasoning_effort

    return _create_completion(**request_args)


def ask_with_usage(
    prompt: str,
    system: str | None = None,
    json_mode: bool = False,
    reasoning_effort: str | None = None,
) -> LLMResult:
    """Return the model's reply and available token usage."""
    response = _get_response(
        prompt, system, json_mode=json_mode, reasoning_effort=reasoning_effort
    )

    reply = response.choices[0].message.content

    if not reply or not reply.strip():
        raise LLMError("The model returned an empty reply.")

    usage = response.usage

    return LLMResult(
        reply=reply,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        total_tokens=usage.total_tokens if usage else None,
    )


def ask(
    prompt: str,
    system: str | None = None,
    json_mode: bool = False,
    reasoning_effort: str | None = None,
) -> str:
    """Return only the model's reply."""
    return ask_with_usage(prompt, system, json_mode, reasoning_effort).reply


def ask_with_tools(
    prompt: str,
    tools: list[dict[str, Any]],
    system: str | None = None,
    tool_choice: str = "auto",
    reasoning_effort: str | None = None,
) -> ToolCallResult:
    """Ask Groq for a response that may contain tool calls."""

    request_args = {
        "model": GROQ_MODEL,
        "messages": _build_messages(prompt, system),
        "tools": tools,
        "tool_choice": tool_choice,
    }

    if reasoning_effort:
        request_args["reasoning_effort"] = reasoning_effort

    response = _create_completion(**request_args)

    if not response.choices:
        raise LLMError("Groq returned no response choices.")

    message = response.choices[0].message

    normalized_calls = []

    for call in message.tool_calls or []:
        normalized_calls.append(
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=call.function.arguments,
            )
        )

    usage = response.usage

    return ToolCallResult(
        content=message.content,
        tool_calls=normalized_calls,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
    )