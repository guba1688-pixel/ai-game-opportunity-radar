import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from radar.deepseek import load_deepseek_config, public_deepseek_status, save_deepseek_config


class DeepSeekConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_default_status_does_not_expose_key(self):
        with patch.dict(os.environ, {}, clear=True):
            status = public_deepseek_status(self.root)
        self.assertFalse(status["configured"])
        self.assertEqual("deepseek-flash", status["model"])
        self.assertNotIn("api_key", status)

    def test_save_and_preserve_masked_key(self):
        with patch.dict(os.environ, {}, clear=True):
            status = save_deepseek_config(self.root, {"api_key":"sk-secret-test","base_url":"https://api.deepseek.com","model":"deepseek-flash"})
            self.assertTrue(status["configured"])
            save_deepseek_config(self.root, {"api_key":"","base_url":"https://api.deepseek.com","model":"deepseek-v4-pro"})
            config = load_deepseek_config(self.root)
        self.assertEqual("sk-secret-test", config["api_key"])
        self.assertEqual("deepseek-v4-pro", config["model"])
        self.assertNotIn("sk-secret-test", json.dumps(status))

    def test_rejects_non_official_endpoint_and_unknown_model(self):
        with self.assertRaises(ValueError):
            save_deepseek_config(self.root, {"base_url":"https://example.com","model":"deepseek-flash"})
        with self.assertRaises(ValueError):
            save_deepseek_config(self.root, {"base_url":"https://api.deepseek.com","model":"unknown"})


if __name__ == "__main__":
    unittest.main()
