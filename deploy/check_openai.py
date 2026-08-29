import asyncio

from mail_control.modules.analysis.openai import OpenAIClient
from mail_control.settings import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    result = await OpenAIClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    ).analyze(
        {
            "sender": "billing@example.com",
            "recipients": ["customer@example.com"],
            "subject": "Pago aprobado",
            "snippet": "Tu pago de PEN 19.90 fue aprobado correctamente.",
            "received_at": "2026-07-31T00:00:00Z",
        }
    )
    print(
        "OPENAI_TEST_OK "
        f"model={settings.openai_model} category={result.category.value}"
    )


if __name__ == "__main__":
    asyncio.run(main())
