from app.core.config import Settings
from app.core.security import create_access_token
from app.models import User

TEST_SETTINGS = Settings(
    _env_file=None,
    app_env="local",
    jwt_secret="test-secret-" + "x" * 40,
    google_oauth_client_id="test-client-id",
    allowed_email_domains=["huware.com"],
    bootstrap_admin_email=None,
)


def auth(user: User) -> dict[str, str]:
    token, _ = create_access_token(user.id, TEST_SETTINGS)
    return {"Authorization": f"Bearer {token}"}
