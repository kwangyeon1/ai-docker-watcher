from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    workspace: Path
    interval_seconds: float = 2.0
    max_feedback_loops: int = 2

    @property
    def vibe_root(self) -> Path:
        return self.workspace / ".vibe"
