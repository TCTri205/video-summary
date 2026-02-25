"""Reasoning + NLP pipeline package (Module 3)."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from reasoning_nlp.pipeline_runner import PipelineConfig

__all__ = ["PipelineConfig", "run_pipeline_g1_g3", "run_pipeline_g1_g5", "run_pipeline_g1_g8"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from reasoning_nlp import pipeline_runner as _runner

        return getattr(_runner, name)
    raise AttributeError(f"module 'reasoning_nlp' has no attribute {name!r}")
