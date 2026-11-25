"""Regressions for the Windows release. Uses a disposable profile and no provider calls."""

import asyncio
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def use_in_process_test_loop():
    """Run ASGI fixtures even when Windows sandboxing blocks socketpair()."""
    class PollingLoop(asyncio.ProactorEventLoop):
        def _make_self_pipe(self):
            self._internal_fds = 0

        def _close_self_pipe(self):
            pass

        def _loop_self_reading(self, future=None):
            pass

        def _write_to_self(self):
            pass

        def _run_once(self):
            wake = self.call_later(0.01, lambda: None)
            try:
                super()._run_once()
            finally:
                wake.cancel()

    class Policy(asyncio.WindowsProactorEventLoopPolicy):
        _loop_factory = PollingLoop

    asyncio.set_event_loop_policy(Policy())


def main():
    if sys.platform == "win32" and "--in-process" in sys.argv:
        use_in_process_test_loop()
    for path in (ROOT / "backend/app").rglob("*.py"):
        compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
    with TemporaryDirectory(prefix="agentdesk-verification-") as folder:
        profile = str(Path(folder) / "profile")
        os.environ.update(AGENTDESK_DATA=profile, AGENTDESK_WORKSPACE=folder, AGENTDESK_API_TOKEN="fixture-token", AGENTDESK_GATEWAY_TOKEN="integration-fixture")
        from fastapi.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect
        from app import agent, db
        from app.config import DEFAULT_SETTINGS
        from app.main import app
        from app.routes import browser_route, computer_route, gateway_route, terminal_route

        from app.engine import llama_local, webchat
        from app.engine.openai_compat import _attempt, ProviderHTTPError
        import httpx

        db.init_db()
        headers = {"Authorization": "Bearer fixture-token"}
        client = TestClient(app)
        assert client.get("/api/health").status_code == 403
        assert client.get("/api/settings", headers={**headers, "Origin": "https://untrusted.invalid"}).status_code == 403
        assert client.get("/api/health", headers=headers).json()["version"] == "0.4.0"
        models = client.get("/api/models", headers=headers).json()
        assert isinstance(models["local"], list) and isinstance(models["catalog"], list) and models["catalog"]
        assert models["backend"]["active"] in ("vulkan", "cpu")
        assert client.get("/api/models/backend", headers=headers).json()["selected"] == "auto"
        assert "Greetings and small talk are not tasks" in agent.SYSTEM_PROMPT
        assert "api-key-file" in (ROOT / "backend/app/engine/llama_server.py").read_text(encoding="utf-8")
        chatgpt_selectors = webchat.SITES["chatgpt"]["assistant"]
        assert isinstance(chatgpt_selectors, tuple)
        assert any("MarkdownRoot" in selector for selector in chatgpt_selectors)
        assert "prompt for Gemini" in webchat.SITES["gemini"]["input"]
        assert webchat._clean_reply("Gemini said\n\nGEMINI OK\ncopy") == "GEMINI OK"
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        assert any(
            item.get("from") == "installer/runtime/llama-vulkan"
            for item in package["build"]["extraResources"]
        )
        settings = client.get("/api/settings", headers=headers).json()
        assert "auto_gateways" in settings and "agents" in settings
        sandbox = client.get("/api/sandbox/session", headers=headers).json()
        assert sandbox["local"] is True and sandbox["session_id"].startswith("sandbox-")
        assert client.post("/api/sandbox/run", headers=headers, json={"sandbox_id": "unknown", "command": "echo"}).status_code == 404
        sandbox_run = client.post("/api/sandbox/run", headers=headers, json={"sandbox_id": sandbox["session_id"], "command": "echo fixture-sandbox"}).json()
        assert sandbox_run["exit_code"] == 0 and "fixture-sandbox" in sandbox_run["output"]
        assert client.get("/api/pet/status", headers=headers).json()["enabled"] is False
        assert client.get("/api/earnings/overview", headers=headers).json()["ventures_count"] == 0
        assert client.get("/api/extensions/mcp/presets", headers=headers).json()
        assert client.get("/api/extensions/skills", headers=headers).status_code == 200
        integration = {"Authorization": "Bearer integration-fixture"}
        assert client.get("/v1/models", headers=headers).status_code == 401
        assert client.get("/v1/models", headers={**integration, "Origin": "http://localhost"}).status_code == 401
        assert client.get("/v1/models", headers=integration).json()["data"][0]["id"] == "agentdesk-local"

        async def fixture_completion(_request, token):
            await token("Hello")
            return {"content": "Hello", "tool_calls": [], "finish_reason": "stop"}

        request = {"messages": [{"role": "user", "content": "Hi"}]}
        with patch.object(gateway_route, "_complete", fixture_completion):
            response = client.post("/v1/chat/completions", headers=integration, json=request)
            assert response.json()["choices"][0]["message"]["content"] == "Hello"
            response = client.post("/v1/chat/completions", headers=integration, json={**request, "stream": True})
            assert '"content": "Hello"' in response.text and "data: [DONE]" in response.text
        async def cloud_fixture(settings, _messages, _tools, on_token):
            assert settings["provider"] == "openrouter" and settings["model"]
            await on_token("Fallback")
            return {"content": "Fallback", "tool_calls": [], "finish_reason": "stop"}

        with patch.object(gateway_route, "load_settings", return_value={"hard_api_key": "fixture"}), \
             patch.object(gateway_route.llama_local, "ensure", AsyncMock(side_effect=RuntimeError("offline"))), \
             patch.object(gateway_route, "stream_completion", cloud_fixture):
            response = client.post("/v1/chat/completions", headers=integration, json={
                **request, "model": "agentdesk-hard", "stream": True,
            })
            assert '"content": "Fallback"' in response.text and "data: [DONE]" in response.text

        session = client.post("/api/sessions", headers=headers, json={"title": "Fixture", "workspace": folder}).json()["id"]
        mission = client.post("/api/missions", headers=headers, json={"name": "Fixture", "prompt": "Repeat the task", "session_id": session})
        assert mission.json()["prompt"] == "Repeat the task"
        assert client.get("/api/missions", headers=headers).json()[0]["id"] == mission.json()["id"]
        assert client.post("/api/browser/action", headers=headers, json={"action": "navigate"}).status_code == 400
        with patch.object(browser_route.browser, "navigate", AsyncMock()) as navigate:
            assert client.post("/api/browser/action", headers=headers, json={"action": "navigate", "url": "https://example.invalid"}).status_code == 200
            navigate.assert_awaited_once_with("https://example.invalid")
        with patch.object(computer_route.computer, "screenshot", AsyncMock(return_value={"frame": "fixture"})):
            assert client.post("/api/computer/capture", headers=headers).json()["frame"] == "fixture"
        terminal = SimpleNamespace(buffer="fixture", error=None, subscribers=set(), write=Mock())
        with patch.object(terminal_route.terminal_manager, "get", return_value=terminal):
            with client.websocket_connect(f"/ws/terminal/{session}", subprotocols=["agentdesk", "token.fixture-token"]) as socket:
                assert socket.receive_json()["buffer"] == "fixture"
        try:
            with client.websocket_connect(f"/ws/chat/{session}"):
                raise AssertionError("Unauthenticated socket was accepted")
        except WebSocketDisconnect:
            pass
        with client.websocket_connect(f"/ws/chat/{session}", subprotocols=["agentdesk", "token.fixture-token"]) as socket:
            assert socket.receive_json()["type"] == "ready"
            socket.send_json({"type": "chat", "text": "/help"})
            while True:
                event = socket.receive_json()
                assert event["type"] != "error", event
                if event["type"] == "done":
                    break

        messages = db.list_messages(session)
        assert messages[-1]["role"] == "assistant"
        assert client.post(f"/api/sessions/{session}/compact", headers=headers, json={}).status_code == 422
        assert db.list_messages(session) == messages
        assert client.post(f"/api/sessions/{session}/compact", headers=headers, json={"summary": "A valid summary."}).status_code == 200
        exported = client.get(f"/api/sessions/{session}/export", headers=headers).json()
        assert exported["messages"][0]["content"] == "A valid summary."
        assert len(exported["archives"][0]["messages"]) == len(messages)
        uploaded = client.post("/api/uploads/files", headers=headers, files={"files": ("sample.txt", b"fixture attachment")}).json()
        assert (Path(profile) / "uploads" / uploaded[0]["id"]).read_bytes() == b"fixture attachment"
        assert len({tool["function"]["name"] for tool in agent.TOOL_SCHEMAS}) == len(agent.TOOL_SCHEMAS)
        assert agent._social_reply("hi")
        assert agent._social_reply("thanks")
        assert agent._social_reply("ok")
        assert agent._social_reply("ok check this file") is None

        async def check_runner():
            send = AsyncMock()
            runner = agent.AgentRunner(session, send)
            settings = {
                **DEFAULT_SETTINGS, "provider": "custom", "gateway": "custom",
                "base_url": "https://example.invalid/v1", "model": "fixture-model", "api_key": "fixture-custom",
                "keys": {"openai": "fixture-openai"}, "hard_fallback_site": "gemini",
                "allow_cloud_fallback": True, "allow_webchat_fallback": True,
            }
            routes = await runner._route_plan(settings, "saved")
            assert [route["settings"]["provider"] for route in routes] == ["custom", "local", "keyless", "openai", "webchat"]
            assert routes[1]["settings"]["model"] == ""
            assert routes[2]["settings"]["api_key"] == "free"
            assert routes[3]["settings"]["api_key"] == "fixture-openai"
            assert routes[3]["settings"]["model"] != "fixture-model"
            assert routes[4]["settings"]["webchat_site"] == "gemini"
            assert await runner._attachment_context([{"id": "../agentdesk.db", "name": "outside"}]) == ""
            # Auto route: keyless + saved-key gateways first, local offline
            # fallback, then browser tabs.
            auto_routes = await runner._route_plan(settings, "auto")
            assert [route["settings"]["provider"] for route in auto_routes] == ["keyless", "openai", "local", "webchat"]
            assert auto_routes[0]["settings"]["api_key"] == "free"
            assert auto_routes[1]["settings"]["api_key"] == "fixture-openai"
            assert auto_routes[2]["settings"]["timeout_s"] == 45
            assert auto_routes[3]["settings"]["webchat_site"] == "gemini"
            # "hard" is a backwards-compatible alias for the auto route.
            hard_routes = await runner._route_plan(settings, "hard")
            assert [route["settings"]["provider"] for route in hard_routes] == ["keyless", "openai", "local", "webchat"]
            assert not await agent.AgentRunner(session, send, interactive=False)._approve("A command", True)
            with patch.object(runner, "_approve", AsyncMock(return_value=False)) as gate:
                for name, arguments in (("computer_click", {"x": 10, "y": 20}), ("browser_click", {"selector": "#submit"})):
                    allowed, _ = await runner._execute(name, arguments, folder, {
                        **settings, "auto_approve_commands": True, "policies": {name: "allow"}
                    })
                    assert not allowed and gate.await_args.args[1] is False

            async def check_stream(body):
                transport = httpx.MockTransport(lambda _: httpx.Response(200, text=body))
                async with httpx.AsyncClient(transport=transport, trust_env=False) as upstream:
                    return await _attempt(upstream, "http://fixture.invalid", {}, {}, AsyncMock())

            partial = 'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
            assert (await check_stream(partial + "data: [DONE]\n\n"))["content"] == "Hi"
            try:
                await check_stream(partial)
                raise AssertionError("Truncated stream was accepted.")
            except RuntimeError as error:
                assert "completion marker" in str(error)
            assert ProviderHTTPError(429, "4").retry_delay() == 4

            with patch.object(runner, "_approve", AsyncMock(return_value=False)) as approve:
                allowed, _ = await runner._execute("fetch_dependency", {"name": "fixture"}, folder, settings)
                assert not allowed and approve.await_count == 1
            with patch.object(agent, "load_settings", return_value={**settings, "allow_cloud_fallback": False}), \
                 patch.object(agent, "stream_completion", AsyncMock(side_effect=[
                     {"content": "", "tool_calls": [{"id": "1", "name": "write_file", "arguments": json.dumps({"path": "output.txt", "content": "verified"})}]},
                     {"content": "Done.", "tool_calls": []},
                 ])):
                await runner.start("Write a fixture file.", "saved")
                await runner._task
            assert runner.outcome == "completed"
            assert (Path(folder) / "output.txt").read_text() == "verified"

            # Hitting max_steps must still produce a real synthesized answer,
            # never the old "Stopped after N steps" status line.
            with patch.object(agent, "load_settings", return_value={
                **settings, "allow_cloud_fallback": False, "max_steps": 2,
            }), patch.object(agent, "stream_completion", AsyncMock(side_effect=[
                {"content": "", "tool_calls": [{"id": "s1", "name": "list_files", "arguments": '{"path":"."}'}]},
                {"content": "", "tool_calls": [{"id": "s2", "name": "list_files", "arguments": '{"path":"."}'}]},
                {"content": "Final synthesized answer from gathered work.", "tool_calls": []},
            ])) as completion:
                await runner.start("Probe the step limit.", "saved")
                await runner._task
            assert runner.outcome == "step_limit"
            final_message = db.list_messages(session)[-1]["content"]
            assert "Stopped after 2 steps" not in final_message
            assert final_message == "Final synthesized answer from gathered work."
            assert completion.await_args_list[-1].args[2] == []

        if "--in-process" in sys.argv and sys.platform == "win32":
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(lambda: asyncio.run(check_runner())).result(timeout=15)
        else:
            asyncio.run(check_runner())
    print("Release regression checks passed.")


if __name__ == "__main__":
    main()
