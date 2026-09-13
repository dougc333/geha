import os
import unittest
from unittest.mock import patch

from langfuse_app import graph_config, settings_from_env, trace_id_for_thread


class LangfuseApplicationTests(unittest.TestCase):
    def test_trace_id_is_stable_per_thread(self):
        self.assertEqual(trace_id_for_thread("thread-1"), trace_id_for_thread("thread-1"))
        self.assertNotEqual(trace_id_for_thread("thread-1"), trace_id_for_thread("thread-2"))

    def test_graph_config_preserves_checkpoint_thread(self):
        handler = object()
        config = graph_config("thread-1", handler, "start")
        self.assertEqual(config["configurable"]["thread_id"], "thread-1")
        self.assertEqual(config["callbacks"], [handler])
        self.assertTrue(config["metadata"]["synthetic_data"])

    def test_settings_require_project_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LANGFUSE_PUBLIC_KEY"):
                settings_from_env()

    def test_settings_use_local_server(self):
        env = {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = settings_from_env()
        self.assertEqual(settings.base_url, "http://localhost:3000")


if __name__ == "__main__":
    unittest.main()
