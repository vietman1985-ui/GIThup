import json
import os
import subprocess
import sys
import unittest

from brain.hooks import handle

from .helpers import REPO_ROOT, VaultTestCase

BRAIN = [sys.executable, str(REPO_ROOT / "bin" / "brain")]


class HookTests(VaultTestCase):
    def test_session_start_emits_additional_context(self):
        out, code = handle(self.config, "session-start", {"session_id": "s1", "cwd": "/home/user/GIThup", "source": "startup"})
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("[brain]", data["hookSpecificOutput"]["additionalContext"])

    def test_prompt_recall_and_skips(self):
        out, _ = handle(self.config, "prompt", {"session_id": "s1", "prompt": "what language does the user prefer to speak"})
        data = json.loads(out)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("User prefers Vietnamese", data["hookSpecificOutput"]["additionalContext"])
        # the same prompt delivered twice (plugin + project hooks) is injected once
        self.assertEqual(handle(self.config, "prompt", {"session_id": "s1", "prompt": "what language does the user prefer to speak"})[0], "")
        self.assertEqual(handle(self.config, "prompt", {"session_id": "s1", "prompt": "/brain:recall x"})[0], "")
        self.assertEqual(handle(self.config, "prompt", {"session_id": "s1", "prompt": "hi"})[0], "")
        self.config.settings["auto_recall"] = False
        self.assertEqual(handle(self.config, "prompt", {"session_id": "s1", "prompt": "what language does the user prefer"})[0], "")

    def test_post_tool_and_session_end_cli(self):
        env = dict(os.environ, BRAIN_VAULT=str(self.vault))
        start = subprocess.run(BRAIN + ["hook", "session-start"], input=json.dumps({"session_id": "cli-1", "cwd": "/p", "source": "startup"}), capture_output=True, text=True, env=env, cwd=str(self.tmp))
        self.assertEqual(start.returncode, 0, start.stderr)
        json.loads(start.stdout)  # valid JSON
        post = subprocess.run(BRAIN + ["hook", "post-tool"], input=json.dumps({"session_id": "cli-1", "tool_name": "Edit", "tool_input": {"file_path": "/p/a.py"}}), capture_output=True, text=True, env=env, cwd=str(self.tmp))
        self.assertEqual((post.returncode, post.stdout), (0, ""))
        end = subprocess.run(BRAIN + ["hook", "session-end"], input=json.dumps({"session_id": "cli-1", "reason": "exit"}), capture_output=True, text=True, env=env, cwd=str(self.tmp))
        self.assertEqual((end.returncode, end.stdout), (0, ""))
        logs = list((self.vault / "memory" / "episodic").glob("*.md"))
        self.assertEqual(len(logs), 1)
        self.assertIn("touched 1 file(s): a.py", logs[0].read_text(encoding="utf-8"))

    def test_default_vault_is_created_on_first_hook(self):
        env = {k: v for k, v in os.environ.items() if k not in ("BRAIN_VAULT",)}
        env["BRAIN_HOME"] = str(self.tmp / "home-brain")
        r = subprocess.run(BRAIN + ["hook", "session-start"], input=json.dumps({"session_id": "auto", "cwd": "/p", "source": "startup"}), capture_output=True, text=True, env=env, cwd=str(self.tmp))
        self.assertEqual(r.returncode, 0, r.stderr)
        vault = self.tmp / "home-brain" / "vault"
        self.assertTrue((vault / "Home.md").exists())
        self.assertTrue((vault / "_schema.md").exists(), "schema is copied from the plugin's seed vault")
        self.assertTrue((vault / "_templates" / "fact.md").exists())
        self.assertFalse((vault / "wiki" / "Second brain landscape 2026.md").exists(), "example notes are not copied")
        self.assertIn("[brain]", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"])
        # an explicit but missing BRAIN_VAULT is never auto-created
        env["BRAIN_VAULT"] = str(self.tmp / "explicit-missing")
        r = subprocess.run(BRAIN + ["hook", "session-start"], input="{}", capture_output=True, text=True, env=env, cwd=str(self.tmp))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertFalse((self.tmp / "explicit-missing").exists())

    def test_hook_never_fails_on_garbage(self):
        env = dict(os.environ, BRAIN_VAULT=str(self.vault))
        r = subprocess.run(BRAIN + ["hook", "prompt"], input="not json", capture_output=True, text=True, env=env, cwd=str(self.tmp))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        env["BRAIN_VAULT"] = str(self.tmp / "does-not-exist")
        r = subprocess.run(BRAIN + ["hook", "session-start"], input="{}", capture_output=True, text=True, env=env, cwd=str(self.tmp))
        self.assertEqual((r.returncode, r.stdout), (0, ""))


class McpServerTests(VaultTestCase):
    def _rpc(self, proc, msg):
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        if "id" not in msg:
            return None
        line = proc.stdout.readline()
        self.assertTrue(line, "server closed stdout")
        return json.loads(line)

    def test_protocol_roundtrip(self):
        env = dict(os.environ, BRAIN_VAULT=str(self.vault))
        proc = subprocess.Popen(BRAIN + ["mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=str(self.tmp))
        try:
            init = self._rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}})
            self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
            self.assertIn("tools", init["result"]["capabilities"])
            self.assertEqual(init["result"]["serverInfo"]["name"], "brain")
            self._rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            self.assertEqual(self._rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"], {})

            tools = self._rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})["result"]["tools"]
            names = {t["name"] for t in tools}
            self.assertTrue({"brain_search", "brain_read", "brain_remember", "brain_capture", "brain_log", "brain_lint", "brain_packet", "brain_context"} <= names)
            for t in tools:
                self.assertEqual(t["inputSchema"]["type"], "object")

            r = self._rpc(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "brain_remember", "arguments": {"title": "MCP test fact", "content": "The MCP server works end to end.", "type": "fact", "tags": ["test"], "importance": 4}}})
            self.assertFalse(r["result"]["isError"])
            self.assertIn("ADD: memory/semantic/facts/MCP test fact.md", r["result"]["content"][0]["text"])

            r = self._rpc(proc, {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "brain_search", "arguments": {"query": "MCP server works", "k": 3}}})
            self.assertIn("MCP test fact", r["result"]["content"][0]["text"])

            r = self._rpc(proc, {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "brain_read", "arguments": {"path": "MCP test fact"}}})
            self.assertIn("The MCP server works end to end.", r["result"]["content"][0]["text"])

            r = self._rpc(proc, {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "brain_read", "arguments": {"path": "nope"}}})
            self.assertTrue(r["result"]["isError"])

            r = self._rpc(proc, {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "unknown_tool", "arguments": {}}})
            self.assertEqual(r["error"]["code"], -32602)

            r = self._rpc(proc, {"jsonrpc": "2.0", "id": 9, "method": "no/such"})
            self.assertEqual(r["error"]["code"], -32601)

            # Content-Length framing is tolerated too
            body = json.dumps({"jsonrpc": "2.0", "id": 10, "method": "ping"})
            proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n{body}")
            proc.stdin.flush()
            self.assertEqual(json.loads(proc.stdout.readline())["id"], 10)
        finally:
            proc.stdin.close()
            proc.wait(timeout=10)
            stderr = proc.stderr.read()
            proc.stdout.close()
            proc.stderr.close()
            self.assertEqual(proc.returncode, 0, stderr)


if __name__ == "__main__":
    unittest.main()
