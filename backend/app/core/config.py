import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
BACKEND_ENV_PATH = PROJECT_ROOT / "backend" / ".env"

load_dotenv(dotenv_path=BACKEND_ENV_PATH)


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    aggregation_model: str
    compliance_model: str
    reporting_model: str
    embedding_model: str
    database_url: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str
    chroma_persist_dir: str
    environment: str


settings = Settings(
    google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
    aggregation_model=os.environ["AGGREGATION_MODEL"],
    compliance_model=os.environ["COMPLIANCE_MODEL"],
    reporting_model=os.environ["REPORTING_MODEL"],
    embedding_model=os.environ["EMBEDDING_MODEL"],
    database_url=os.environ["DATABASE_URL"],
    langfuse_public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    langfuse_secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    langfuse_host=os.environ["LANGFUSE_HOST"],
    chroma_persist_dir=os.environ.get("CHROMA_PERSIST_DIR", "./data/chroma"),
    environment=os.environ.get("ENVIRONMENT", "development"),
)
