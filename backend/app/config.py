import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Flask ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DEBUG: bool = False
    TESTING: bool = False

    def __init__(self):
        # Refuse to start in production with the placeholder key
        env = os.environ.get("FLASK_ENV", "development")
        if env == "production" and self.SECRET_KEY == "dev-secret-change-me":
            raise RuntimeError(
                "SECRET_KEY must be set to a secure random value in production. "
                "Set the SECRET_KEY environment variable."
            )

    # ── MongoDB ────────────────────────────────────────────────────────────
    MONGO_URI: str = os.environ.get("MONGO_URI", "mongodb://localhost:27017/lablink")

    # ── JWT ────────────────────────────────────────────────────────────────
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 15))
    )
    JWT_REFRESH_TOKEN_EXPIRES: timedelta = timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 7))
    )
    # Refresh tokens are stored in secure HttpOnly cookies
    JWT_COOKIE_SECURE: bool = False        # True in production (HTTPS)
    JWT_COOKIE_SAMESITE: str = "Lax"

    # ── CORS ───────────────────────────────────────────────────────────────
    CORS_ORIGIN: str = os.environ.get("CORS_ORIGIN", "http://localhost:5173")

    # ── watsonx.ai ─────────────────────────────────────────────────────────
    WATSONX_API_KEY: str = os.environ.get("WATSONX_API_KEY", "")
    WATSONX_PROJECT_ID: str = os.environ.get("WATSONX_PROJECT_ID", "")
    WATSONX_URL: str = os.environ.get(
        "WATSONX_URL", "https://us-south.ml.cloud.ibm.com"
    )


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    # Tests override MONGO_URI via fixture; keep a default
    MONGO_URI = os.environ.get("TEST_MONGO_URI", "mongodb://localhost:27017/lablink_test")
    JWT_COOKIE_SECURE = False


class ProductionConfig(Config):
    JWT_COOKIE_SECURE = True

    def __init__(self):
        super().__init__()
        # Also require MONGO_URI to be explicitly set (not the localhost default)
        if self.MONGO_URI == "mongodb://localhost:27017/lablink":
            raise RuntimeError(
                "MONGO_URI must be set to a MongoDB Atlas connection string in production. "
                "Set the MONGO_URI environment variable."
            )


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config() -> Config:
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)()
