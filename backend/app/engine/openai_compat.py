import json
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Awaitable, Callable

import httpx

TokenCallback = Callable[[str], Awaitable[None]]


class ProviderHTTPError(RuntimeError):
    def __init__(self, status: int, retry_after: str = "") -> None:
        super().__init__(f"Model provider returned HTTP {status}.")
        self.status = status
        self.retry_after = retry_after

    def retry_delay(self) -> float | None:
        try:
            return max(0.0, float(self.retry_after))
        except ValueError:
            try:
                return max(0.0, (parsedate_to_datetime(self.retry_after) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None


async def _attempt(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    payload: dict,
    on_token: TokenCallback,
    on_tool_delta=None,
) -> dict:
    content_parts: list[str] = []
    calls: dict[int, dict] = {}
    complete = False
    finish_reason = None

    async with client.stream("POST", url, json=payload, headers=headers) as response:
        if response.status_code >= 400:
            raise ProviderHTTPError(response.status_code, response.headers.get("retry-after", ""))

        async for line in response.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                complete = True
                break
            if not data:
                continue
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if "error" in chunk:
                raise RuntimeError("The provider reported a streaming error.")
            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            finish_reason = choice.get("finish_reason") or finish_reason
            delta = choice.get("delta") or {}

            piece = delta.get("content")
            if piece:
                content_parts.append(piece)
                await on_token(piece)

            for fallback_index, tool_delta in enumerate(delta.get("tool_calls") or []):
                index = tool_delta.get("index", fallback_index)
                slot = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                if tool_delta.get("id"):
                    slot["id"] = tool_delta["id"]
                function = tool_delta.get("function") or {}
                if function.get("name"):
                    slot["name"] = function["name"]
                arguments = function.get("arguments")
                if arguments:
                    if isinstance(arguments, str):
                        slot["arguments"] += arguments
                    else:
                        slot["arguments"] += json.dumps(arguments)
                    if on_tool_delta is not None:
                        try:
                            await on_tool_delta(slot.get("id") or f"call_{index}", slot.get("name") or "", slot["arguments"])
                        except Exception:
                            pass

    if not complete and not finish_reason:
        raise RuntimeError("The model stream ended before a completion marker arrived.")
    if calls and finish_reason not in {"tool_calls", "function_call", "stop"}:
        raise RuntimeError("The model interrupted a tool call.")

    tool_calls = []
    for index in sorted(calls):
        call = calls[index]
        if not call["name"]:
            continue
        tool_calls.append(
            {
                "id": call["id"] or f"call_{index}",
                "name": call["name"],
                "arguments": call["arguments"] or "{}",
            }
        )

    content = "".join(content_parts)
    if not content and not tool_calls:
        raise RuntimeError("The model returned an empty response. Try again or switch models.")
    return {"content": content, "tool_calls": tool_calls, "finish_reason": finish_reason or ("tool_calls" if tool_calls else "stop")}


async def stream_completion(
    settings: dict,
    messages: list[dict],
    tools: list[dict],
    on_token: TokenCallback,
    on_tool_delta=None,
) -> dict:
    """Run one streaming chat completion and return content + accumulated tool calls.

    Some OpenAI-compatible providers (including several free OpenRouter models) reject
    tool definitions or the reasoning parameter. We retry with progressively simpler
    payloads on 400/422 instead of failing the whole turn.
    """
    base_url = str(settings.get("base_url", "")).rstrip("/")
    if not base_url:
        raise RuntimeError("No model endpoint configured. Open Settings and set a base URL.")
    url = base_url + "/chat/completions"

    payload: dict = {
        "model": settings.get("model"),
        "messages": messages,
        "temperature": settings.get("temperature", 0.2),
        "stream": True,
    }
    if settings.get("max_tokens") is not None:
        payload["max_tokens"] = settings["max_tokens"]
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if settings.get("disable_thinking"):
        payload["reasoning_effort"] = "none"

    headers = {"Content-Type": "application/json"}
    api_key = settings.get("api_key")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if "openrouter.ai" in base_url:
        headers["HTTP-Referer"] = "https://agentdesk.local"
        headers["X-Title"] = "AgentDesk"

    variants: list[dict] = [payload]
    if settings.get("disable_thinking"):
        stripped = {key: value for key, value in variants[-1].items() if key != "reasoning_effort"}
        if stripped not in variants:
            variants.append(stripped)

    # The bundled 1.5B CPU model can spend minutes prefilling a large agent prompt.
    # In Auto mode that stalls the whole chat, so bound the wait for local tokens
    # and let the router move on to a saved cloud gateway.
    is_local = settings.get("provider") == "local" or ":11435" in base_url
    read_timeout = float(
        settings.get("timeout_s") or (45.0 if is_local else 90.0)
    )
    timeout = httpx.Timeout(
        connect=5.0 if is_local else 15.0,
        read=read_timeout,
        write=60.0,
        pool=60.0,
    )
    last_error: ProviderHTTPError | None = None
    async with httpx.AsyncClient(timeout=timeout, trust_env=os.environ.get("AGENTDESK_USE_PROXY") == "1" and settings.get("provider") != "local") as client:
        for attempt, body in enumerate(variants):
            try:
                return await _attempt(client, url, headers, body, on_token, on_tool_delta)
            except ProviderHTTPError as exc:
                last_error = exc
                retryable = exc.status in (400, 404, 422) and attempt < len(variants) - 1
                if not retryable:
                    break

    if last_error:
        raise last_error
    raise RuntimeError("The model request failed for an unknown reason.")
