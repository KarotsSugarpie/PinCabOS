from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[3] / "web"
sys.path.insert(0, str(WEB))


class DummyBlueprint:
    def __init__(self, *_args, **_kwargs):
        self.name = "dummy"

    def get(self, *_args, **_kwargs):
        return lambda function: function

    def post(self, *_args, **_kwargs):
        return lambda function: function


flask = types.ModuleType("flask")
flask.Blueprint = DummyBlueprint
flask.Response = object
flask.jsonify = lambda value: value
flask.make_response = lambda value: value
flask.request = types.SimpleNamespace()
sys.modules.setdefault("flask", flask)

from pincaboslink_multiplayer import _agent_arguments


class WebContractTests(unittest.TestCase):
    def test_only_whitelisted_actions_reach_the_agent(self):
        with self.assertRaises(ValueError):
            _agent_arguments("run-shell", {})

    def test_join_code_is_normalized(self):
        self.assertEqual(
            _agent_arguments("join", {"room_code": "ab-cd 23"}),
            ["join", "ABCD23"],
        )

    def test_test_table_cannot_escape_the_runtime(self):
        with self.assertRaises(ValueError):
            _agent_arguments("launch", {"table": "../private.vpx"})


if __name__ == "__main__":
    unittest.main()
