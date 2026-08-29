from mail_control.settings import Settings


def base_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_secret_key": "x" * 32,
        "database_url": "postgresql+asyncpg://example",
        "redis_url": "redis://example",
        "rabbitmq_url": "amqp://example",
    }
    values.update(overrides)
    return Settings(**values)


def test_origins_are_parsed_from_csv() -> None:
    settings = base_settings(
        allowed_origins="https://one.example, https://two.example",
    )
    assert settings.allowed_origins == (
        "https://one.example",
        "https://two.example",
    )


def test_credential_encryption_key_is_loaded_from_file(tmp_path) -> None:
    key_file = tmp_path / "credential-key"
    key_file.write_text("f" * 48 + "\n", encoding="utf-8")

    settings = base_settings(
        credential_encryption_key="environment-key-that-is-long-enough",
        credential_encryption_key_file=str(key_file),
    )

    assert settings.credential_encryption_key == "f" * 48
