"""Lightweight unit tests — no Discord network required."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestDiscordUtils(unittest.TestCase):
    def test_escape_backticks(self):
        from shared.discord_utils import escape_backticks, safe_inline

        self.assertIn("\u200b", escape_backticks("a`b"))
        self.assertNotIn("```", safe_inline("x```y", 50))

    def test_chunk_text(self):
        from shared.discord_utils import chunk_text

        self.assertEqual(chunk_text("", 10), [])
        self.assertEqual(chunk_text("abcdef", 2), ["ab", "cd", "ef"])
        self.assertEqual(chunk_text("hi", 10), ["hi"])
        # Non-positive limit: do not loop forever — return the original string
        self.assertEqual(chunk_text("abc", 0), ["abc"])


class TestProtocol(unittest.TestCase):
    def test_parse_help(self):
        with mock.patch("shared.protocol.command_prefix", return_value="!"):
            from shared.protocol import parse_command

            self.assertEqual(parse_command("!help"), "__HELP__")
            self.assertEqual(parse_command("!status"), "__STATUS__")
            self.assertEqual(parse_command("!ping"), "__PING__")
            self.assertEqual(parse_command("!history"), "__HISTORY__")
            self.assertEqual(parse_command("!last"), "__LAST__")
            self.assertEqual(parse_command("!input alt p"), "__INPUT__:alt p")
            self.assertEqual(parse_command("!mouse click"), "__MOUSE__:click")

    def test_parse_cmd_and_spaces(self):
        with mock.patch("shared.protocol.command_prefix", return_value="!"):
            with mock.patch("shared.protocol.resolve_alias", return_value=None):
                from shared.protocol import parse_command

                self.assertEqual(parse_command("!cmd echo hi"), "echo hi")
                self.assertEqual(parse_command("!input text:hello world"), "__INPUT__:text:hello world")
                self.assertIsNone(parse_command("!"))
                self.assertIsNone(parse_command("!cmd"))


class TestConfigNumeric(unittest.TestCase):
    def test_positive_int_rejects_zero_and_negative(self):
        from shared.config import _parse_positive_int, _parse_int

        self.assertEqual(_parse_positive_int(0, 20), 20)
        self.assertEqual(_parse_positive_int(-5, 20), 20)
        self.assertEqual(_parse_positive_int("nope", 20), 20)
        self.assertEqual(_parse_positive_int(7, 20), 7)
        # 0 remains valid for fields like audit_channel_id
        self.assertEqual(_parse_int(0, 99), 0)

    def test_max_output_chunks_default_positive(self):
        from shared.config import _parse_positive_int

        self.assertEqual(_parse_positive_int(0, 6), 6)
        self.assertEqual(_parse_positive_int(3, 6), 3)


class TestConfigPrefix(unittest.TestCase):
    def test_empty_prefix_falls_back(self):
        with mock.patch("shared.config.get", return_value={"discord": {"command_prefix": ""}}):
            from shared.config import command_prefix

            self.assertEqual(command_prefix(), "!")

        with mock.patch("shared.config.get", return_value={"discord": {"command_prefix": "  "}}):
            from shared.config import command_prefix

            self.assertEqual(command_prefix(), "!")


class TestPolicy(unittest.TestCase):
    def test_unrestricted_allows(self):
        with mock.patch("daemon.security.execution_mode", return_value="unrestricted"):
            from daemon.security import command_allowed_by_policy

            ok, _ = command_allowed_by_policy("rm -rf /")
            self.assertTrue(ok)

    def test_allowlist_blocks(self):
        with mock.patch("daemon.security.execution_mode", return_value="allowlist"):
            with mock.patch("daemon.security.allowed_patterns", return_value=["uptime"]):
                from daemon.security import command_allowed_by_policy

                ok, msg = command_allowed_by_policy("rm -rf /")
                self.assertFalse(ok)
                ok2, _ = command_allowed_by_policy("uptime")
                self.assertTrue(ok2)

    def test_allowlist_no_substring_injection(self):
        """Plain pattern must not match as a loose substring."""
        with mock.patch("daemon.security.execution_mode", return_value="allowlist"):
            with mock.patch("daemon.security.allowed_patterns", return_value=["uptime"]):
                from daemon.security import command_allowed_by_policy

                ok, _ = command_allowed_by_policy("rm -rf /; uptime")
                self.assertFalse(ok)
                ok_g, _ = command_allowed_by_policy("uptime -p")
                self.assertFalse(ok_g)

    def test_allowlist_glob_and_regex(self):
        with mock.patch("daemon.security.execution_mode", return_value="allowlist"):
            with mock.patch(
                "daemon.security.allowed_patterns",
                return_value=["uptime*", "re:^df\\b"],
            ):
                from daemon.security import command_allowed_by_policy

                self.assertTrue(command_allowed_by_policy("uptime -p")[0])
                self.assertTrue(command_allowed_by_policy("df -h")[0])
                self.assertFalse(command_allowed_by_policy("echo uptime")[0])


class TestPasswordHash(unittest.TestCase):
    def test_roundtrip(self):
        from daemon.security import hash_password, verify_password

        stored = hash_password("correct-horse-battery")
        self.assertTrue(verify_password("correct-horse-battery", stored))
        self.assertFalse(verify_password("wrong", stored))


class TestExecutorTimeout(unittest.TestCase):
    def test_timeout_returns_code_1_and_message(self):
        from daemon.executor import run_command

        rc, stdout, stderr = run_command("sleep 5", timeout=1)
        self.assertEqual(rc, 1)
        self.assertIn("timed out", stderr.lower())


class TestHistory(unittest.TestCase):
    def test_record_and_last(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("daemon.history.state_dir", return_value=Path(td)):
                with mock.patch("daemon.history.history_enabled", return_value=True):
                    with mock.patch("daemon.history.history_max_entries", return_value=10):
                        from daemon import history

                        history.record(1, "user", "echo hi", 0)
                        last = history.last_command()
                        self.assertIsNotNone(last)
                        self.assertEqual(last["command"], "echo hi")


if __name__ == "__main__":
    os.environ.setdefault("DISCORD_TOKEN", "test-token-not-real")
    os.environ.setdefault("COMMAND_CHANNEL_ID", "1")
    unittest.main(verbosity=2)
