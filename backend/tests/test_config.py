from app.core.config import Settings


def test_cors_origins_from_comma_separated_string():
    s = Settings(cors_origins="http://a.test, http://b.test")
    assert s.cors_origins == ["http://a.test", "http://b.test"]
