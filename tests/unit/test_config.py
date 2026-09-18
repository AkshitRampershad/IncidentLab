from core.config import Settings


def test_cors_allowed_origins_list_defaults_to_local_dev():
    assert Settings().cors_allowed_origins_list == ["http://localhost:3000"]


def test_cors_allowed_origins_list_splits_on_comma():
    settings = Settings(cors_allowed_origins="https://a.example.com,https://b.example.com")
    assert settings.cors_allowed_origins_list == ["https://a.example.com", "https://b.example.com"]


def test_cors_allowed_origins_list_trims_whitespace_around_entries():
    settings = Settings(cors_allowed_origins=" https://a.example.com , https://b.example.com ")
    assert settings.cors_allowed_origins_list == ["https://a.example.com", "https://b.example.com"]


def test_cors_allowed_origins_list_ignores_empty_entries():
    """A trailing comma in a hand-edited .env (or a value like "a,,b")
    shouldn't produce a "" entry — starlette's CORSMiddleware treats an
    empty string in allow_origins as a real (wrong) value, not a no-op."""
    settings = Settings(cors_allowed_origins="https://a.example.com,,https://b.example.com,")
    assert settings.cors_allowed_origins_list == ["https://a.example.com", "https://b.example.com"]


def test_cors_allowed_origins_list_empty_string_is_no_origins():
    assert Settings(cors_allowed_origins="").cors_allowed_origins_list == []
