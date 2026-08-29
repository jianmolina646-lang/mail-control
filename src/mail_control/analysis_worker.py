from __future__ import annotations

import asyncio

from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.infrastructure.resources import Resources
from mail_control.modules.analysis.client import AnalysisClient
from mail_control.modules.analysis.gemini import GeminiClient
from mail_control.modules.analysis.openai import OpenAIClient
from mail_control.modules.analysis.repository import AnalysisRepository
from mail_control.modules.analysis.service import AnalysisService
from mail_control.settings import get_settings


async def run() -> None:
    settings = get_settings()
    client: AnalysisClient
    if settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        client = OpenAIClient(settings.openai_api_key, settings.openai_model)
    elif settings.ai_provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required")
        client = GeminiClient(settings.gemini_api_key, settings.gemini_model)
    else:
        raise RuntimeError(f"unsupported AI_PROVIDER: {settings.ai_provider}")
    resources = await Resources.connect(settings)
    try:
        while True:
            async for session in resources.system_database.session():
                repository = AnalysisRepository(session)
                event = await repository.claim()
                if event is None:
                    await asyncio.sleep(2)
                    break
                try:
                    await set_tenant_context(session, event.tenant_id)
                    message = await repository.message(
                        event.tenant_id,
                        event.aggregate_id,
                    )
                    if message is None:
                        await repository.complete(event)
                        continue
                    await AnalysisService(repository, client).process(event, message)
                except Exception as error:
                    await repository.fail(event, error)
    finally:
        await resources.close()


if __name__ == "__main__":
    asyncio.run(run())
