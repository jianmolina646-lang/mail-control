from __future__ import annotations

from typing import Protocol

from mail_control.modules.analysis.schemas import AnalysisResult

PROMPT_VERSION = "2026-08-15.1"


class AnalysisClient(Protocol):
    model: str

    async def analyze(self, email_data: dict[str, object]) -> AnalysisResult: ...
