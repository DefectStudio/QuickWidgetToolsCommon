"""Version selection must never send a job or credential to the other farm."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "Content/Python/publish_render_queue_to_farm.py"
V1_URL = "https://defect-farm-api.twilight-tooth-7b7c.workers.dev"
V2_URL = "https://defect-farm-api-v2.twilight-tooth-7b7c.workers.dev"


class FarmVersionRoutingTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("farm_publisher_routing_test", SCRIPT)
        self.publisher = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"unreal": ModuleType("unreal")}):
            spec.loader.exec_module(self.publisher)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {"LOCALAPPDATA": self.directory.name}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.profile(False, V1_URL, "test-v1-submit")
        self.profile(True, V2_URL, "test-v2-submit")

    def profile(self, v2, url, token):
        relative = "RenderFarmV2/company-submit.json" if v2 else "RenderFarm/cloud_connection.json"
        path = Path(self.directory.name) / "DefectStudio" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"api_url": url, "submit_token": token}))
        return path

    def test_default_is_v1_even_after_a_v2_preview_session(self):
        os.environ.update(DEFECT_FARM_API_URL=V2_URL, DEFECT_FARM_SUBMIT_TOKEN="session-v2")
        self.assertEqual((V1_URL, "test-v1-submit"), self.publisher._load_dispatcher_submit_connection())

    def test_v2_uses_its_own_profile_in_a_v1_environment(self):
        os.environ.update(DEFECT_FARM_API_URL=V1_URL, DEFECT_FARM_SUBMIT_TOKEN="session-v1")
        self.assertEqual((V2_URL, "test-v2-submit"), self.publisher._load_dispatcher_submit_connection(True))

    def test_existing_v1_environment_credentials_still_work(self):
        os.environ["DEFECT_FARM_SUBMIT_TOKEN"] = "legacy-v1"
        self.assertEqual((V1_URL, "legacy-v1"), self.publisher._load_dispatcher_submit_connection())

    def test_missing_v2_credentials_never_fall_back_to_v1(self):
        self.profile(True, V2_URL, "")
        os.environ.update(DEFECT_FARM_API_URL=V1_URL, DEFECT_FARM_SUBMIT_TOKEN="session-v1")
        with self.assertRaisesRegex(self.publisher.DispatcherSubmissionError, "V2 submit credential"):
            self.publisher._load_dispatcher_submit_connection(True)

    def test_swapped_profile_is_rejected(self):
        self.profile(True, V1_URL, "test-v2-submit")
        with self.assertRaisesRegex(self.publisher.DispatcherSubmissionError, "company V2 service"):
            self.publisher._load_dispatcher_submit_connection(True)

    def test_non_boolean_version_is_rejected(self):
        with self.assertRaises(ValueError):
            self.publisher._load_dispatcher_submit_connection("False")


if __name__ == "__main__":
    unittest.main()
