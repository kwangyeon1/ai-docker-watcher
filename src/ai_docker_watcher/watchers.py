from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .events import Event
from .impact import DOCKER_IMPACT_FILES


@dataclass
class FileChangeWatcher:
    workspace: Path
    ignore_prefixes: tuple[str, ...] = (
        ".git",
        ".vibe",
        "__pycache__",
        ".pytest_cache",
        "venv",
        ".venv",
        "node_modules",
    )
    tracked_suffixes: tuple[str, ...] = (
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".java",
        ".go",
        ".rb",
        ".yml",
        ".yaml",
        ".json",
        ".toml",
        ".ini",
        "Dockerfile",
    )
    _last_snapshot: dict[str, float] = field(default_factory=dict)

    def _should_track(self, rel: str) -> bool:
        if any(rel.startswith(prefix + "/") or rel == prefix for prefix in self.ignore_prefixes):
            return False
        name = Path(rel).name
        if name in DOCKER_IMPACT_FILES:
            return True
        return rel.endswith(self.tracked_suffixes) or name == "Dockerfile"

    def _snapshot(self) -> dict[str, float]:
        snap: dict[str, float] = {}
        for p in self.workspace.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(self.workspace))
            if not self._should_track(rel):
                continue
            snap[rel] = p.stat().st_mtime
        return snap

    def initialize(self) -> None:
        self._last_snapshot = self._snapshot()

    def poll(self) -> Event | None:
        current = self._snapshot()
        changed = [
            path
            for path, mtime in current.items()
            if path not in self._last_snapshot or self._last_snapshot[path] != mtime
        ]
        deleted = [path for path in self._last_snapshot if path not in current]

        self._last_snapshot = current

        all_changed = sorted(set(changed + deleted))
        if not all_changed:
            return None

        return Event(
            name="files_changed",
            source="file-change-watcher",
            payload={"changed_files": all_changed},
        )
