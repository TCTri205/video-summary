from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PipelineError(Exception):
    code: str
    stage: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"[{self.stage}] {self.code}: {self.message}"


def fail(stage: str, code: str, message: str, details: dict[str, Any] | None = None) -> PipelineError:
    return PipelineError(code=code, stage=stage, message=message, details=details)
