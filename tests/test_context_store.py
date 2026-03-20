from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_docker_watcher.context_store import ContextStore


class ContextStoreBundleTests(unittest.TestCase):
    def test_init_creates_bundle_and_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            store = ContextStore(workspace)
            store.ensure()
            store.init_default_context()

            bundle = (workspace / ".vibe-docker" / "context" / "artifact_reference_bundle.md").read_text()
            examples = (
                workspace / ".vibe-docker" / "context" / "agent_brief_bundle_integration_examples.md"
            ).read_text()

            self.assertIn("# Artifact Reference Bundle", bundle)
            self.assertIn("context/recent_failures.md", bundle)
            self.assertIn("No active validation failure is recorded.", bundle)
            self.assertIn("# Agent Markdown Bundle Integration Examples", examples)
            self.assertIn("`AGENTS.md`", examples)
            self.assertIn("`CLAUDE.md` or `CODEX.md`", examples)

    def test_refresh_bundle_reflects_reports_and_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            store = ContextStore(workspace)
            store.ensure()
            store.init_default_context()

            store.write_json(
                "state/task_state.json",
                {
                    "task_id": "task-001",
                    "main_agent": "bridge",
                    "docker_status": "ok",
                    "validation_status": "failed",
                    "last_owner": "docker-agent",
                },
            )
            store.write_json(
                "state/changed_files.json",
                {
                    "changed_files": ["requirements.txt", "docker-compose.yml"],
                    "docker_related": True,
                },
            )
            store.write_json(
                "reports/validation_report.json",
                {
                    "status": "failed",
                    "owner": "docker-agent",
                    "error_type": "docker_build_failed",
                    "summary": "pip install failed",
                },
            )
            store.write_text("reports/docker_report.md", "# Docker Agent Report\n\nSummary: updated Dockerfile\n")
            store.write_text(
                "context/recent_failures.md",
                "# Recent Failures\n\n- owner: docker-agent\n- error_type: docker_build_failed\n- summary: pip install failed\n",
            )

            store.refresh_reference_bundle()

            bundle_path = workspace / ".vibe-docker" / "context" / "artifact_reference_bundle.md"
            bundle = bundle_path.read_text()

            self.assertIn("Validation is failing.", bundle)
            self.assertIn("`requirements.txt`", bundle)
            self.assertIn("pip install failed", bundle)
            self.assertIn("`docker_build_failed`", bundle)


if __name__ == "__main__":
    unittest.main()
