"""Loopback OpenAI-compatible inference for programs using AgentDesk."""
import asyncio
import contextlib
import json
import time
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import provider_health
from ..config import load_settings
from ..engine import llama_local
from ..engine.gateways import FALLBACK_CHAIN, GATEWAY_ENDPOINTS, GATEWAY_MODELS, key_for_gateway
from ..engine.openai_compat import ProviderHTTPError, stream_completion

router = APIRouter()
MODELS = ("agentdesk-local", "agentdesk-hard")


class ChatRequest(BaseModel):
    model: str = "agentdesk-local"
    messages: list[dict] = Field(min_length=1, max_length=200)
    stream: bool = False
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=512, gt=0, le=4096)
    tools: list[dict] = Field(default_factory=list, max_length=32)


async def _complete(request: ChatRequest, on_token):
    settings = load_settings()
    routes: list[str] = []
    if request.model == "agentdesk-hard":
        # Same Auto policy as chat: every usable gateway first in user order,
        # then the local model as the offline safety net.
        for gateway in settings.get("auto_gateways") or FALLBACK_CHAIN:
            if gateway != "local" and key_for_gateway(gateway, settings):
                routes.append(gateway)
    routes.append("local")
    for provider in routes:
        if not provider_health.available(provider):
            continue
        emitted = False
        started = time.monotonic()

        async def forward(text: str):
            nonlocal emitted
            emitted = True
            await on_token(text)

        try:
            if provider == "local":
                url = await llama_local.ensure()
                api_key = llama_local.access_key()
                model = await llama_local.resolve_model_name()
            else:
                url = GATEWAY_ENDPOINTS.get(provider, "")
                api_key = key_for_gateway(provider, settings)
                model = str(
                    (settings.get("gateway_models") or {}).get(provider)
                    or GATEWAY_MODELS.get(provider, "")
                )
                if not url or not api_key or not model:
                    continue
            if provider == "local" and request.tools:
                # The bundled compact CPU model is intended for plain chat through the integration API.
                continue
            async with asyncio.timeout(150):
                result = await stream_completion(
                    {"base_url": url, "api_key": api_key, "model": model, "provider": provider,
                     "temperature": request.temperature, "max_tokens": request.max_tokens},
                    request.messages, request.tools, forward if request.stream else _ignore,
                )
            provider_health.record(provider, True, (time.monotonic() - started) * 1000)
            return result
        except Exception as error:
            provider_health.record(provider, False, (time.monotonic() - started) * 1000)
            if isinstance(error, ProviderHTTPError) and error.status == 429:
                provider_health.cooldown(provider, error.retry_delay())
            if emitted:
                raise RuntimeError("The provider interrupted the response.") from None
    raise RuntimeError("No compatible model is available. Check AgentDesk provider settings.")


async def _ignore(_text: str):
    pass


def _tool_calls(result):
    return [
        {"index": index, "id": call["id"], "type": "function",
         "function": {"name": call["name"], "arguments": call["arguments"]}}
        for index, call in enumerate(result["tool_calls"])
    ]


@router.get("/models")
async def models():
    return {"object": "list", "data": [
        {"id": model, "object": "model", "created": 0, "owned_by": "agentdesk"} for model in MODELS
    ]}


@router.post("/chat/completions")
async def chat_completions(request: ChatRequest):
    if request.model not in MODELS:
        raise HTTPException(404, "Use agentdesk-local or agentdesk-hard.")
    response_id = f"chatcmpl-{uuid.uuid4().hex}"
    base = {"id": response_id, "created": int(time.time()), "model": request.model}
    if not request.stream:
        try:
            result = await _complete(request, _ignore)
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from None
        message = {"role": "assistant", "content": result["content"] or None}
        if result["tool_calls"]:
            message["tool_calls"] = [{k: v for k, v in call.items() if k != "index"} for call in _tool_calls(result)]
        return {**base, "object": "chat.completion",
                "choices": [{"index": 0, "message": message, "finish_reason": result["finish_reason"]}]}

    async def events():
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)

        async def produce():
            async def token(text):
                await queue.put(("text", text))

            try:
                await queue.put(("complete", await _complete(request, token)))
            except RuntimeError as error:
                await queue.put(("error", str(error)))
            except Exception:
                await queue.put(("error", "The AgentDesk gateway could not complete the request."))

        def chunk(delta, finish=None):
            return "data: " + json.dumps({**base, "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}) + "\n\n"

        task = asyncio.create_task(produce())
        try:
            while True:
                kind, value = await queue.get()
                if kind == "text":
                    yield chunk({"content": value})
                    continue
                if kind == "error":
                    yield "data: " + json.dumps({"error": {"message": value, "type": "provider_error"}}) + "\n\n"
                    break
                calls = _tool_calls(value)
                if calls:
                    yield chunk({"tool_calls": calls})
                yield chunk({}, value["finish_reason"])
                yield "data: [DONE]\n\n"
                break
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
