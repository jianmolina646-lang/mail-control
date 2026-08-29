from mail_control.settings import get_settings

settings = get_settings()

checks = {
    "production_mode": settings.is_production,
    "encryption_key": bool(settings.credential_encryption_key),
    "google_client_id": bool(settings.google_client_id),
    "google_client_secret": bool(settings.google_client_secret),
    "microsoft_client_id": bool(settings.microsoft_client_id),
    "microsoft_client_secret": bool(settings.microsoft_client_secret),
    "openai_api_key": bool(settings.openai_api_key),
    "openai_model": settings.openai_model,
    "ai_provider": settings.ai_provider,
    "google_redirect_uri": settings.google_redirect_uri,
    "microsoft_redirect_uri": settings.microsoft_redirect_uri,
    "frontend_url": settings.frontend_url,
}

for key, value in checks.items():
    print(f"{key}={value}")
