from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / '.env')


def _resolve_path(env_var: str, default_relative: str) -> Path:
    """Resolve a path from env var or default relative to project root."""
    val = os.getenv(env_var)
    # Ignore stale macOS paths when the repository is run on Windows.
    stale_macos_path = os.name == 'nt' and (val or '').replace('\\', '/').startswith('/Users/')
    if val and not stale_macos_path:
        configured = Path(val)
        return configured if configured.is_absolute() else PROJECT_ROOT / configured
    return PROJECT_ROOT / default_relative


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / '.env', extra='ignore')

    input_root: Path = _resolve_path('BAI_INPUT_ROOT', 'data/input')
    working_dir: Path = _resolve_path('BAI_WORKING_DIR', 'data/working')
    output_dir: Path = _resolve_path('BAI_OUTPUT_DIR', 'data/output')
    db_path: Path = _resolve_path('BAI_DB_PATH', 'data/working/bai.duckdb')
    storage_mode: str = 'duckdb'
    postgres_url: str | None = None
    postgres_pool_size: int = 5
    postgres_max_overflow: int = 10

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    openai_api_version: str = '2024-05-01-preview'
    azure_openai_chat_deployment: str | None = None
    azure_openai_embeddings_deployment: str | None = None

    openai_api_key: str | None = None
    openai_api_base: str | None = None
    openai_api_mode: str = 'auto'
    chat_deployment: str | None = None
    openai_model: str = 'gpt-4.1-mini'
    brand_id: str = 'aveeno'
    brand_display: str = 'Aveeno'
    market: str = 'US'
    language: str = 'en-US'
    source_system: str = 'BrandRank'

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT


settings = Settings(
    input_root=_resolve_path('BAI_INPUT_ROOT', 'data/input'),
    working_dir=_resolve_path('BAI_WORKING_DIR', 'data/working'),
    output_dir=_resolve_path('BAI_OUTPUT_DIR', 'data/output'),
    db_path=_resolve_path('BAI_DB_PATH', 'data/working/bai.duckdb'),
    storage_mode=os.getenv('BAI_STORAGE_MODE', 'duckdb'),
    postgres_url=os.getenv('BAI_POSTGRES_URL'),
    postgres_pool_size=int(os.getenv('BAI_POSTGRES_POOL_SIZE', '5')),
    postgres_max_overflow=int(os.getenv('BAI_POSTGRES_MAX_OVERFLOW', '10')),
    azure_openai_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
    azure_openai_api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    openai_api_version=os.getenv('OPENAI_API_VERSION', '2024-05-01-preview'),
    azure_openai_chat_deployment=os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT'),
    azure_openai_embeddings_deployment=os.getenv('AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT'),
    openai_api_key=os.getenv('OPENAI_API_KEY'),
    openai_api_base=os.getenv('OPENAI_API_BASE'),
    openai_api_mode=os.getenv('OPENAI_API_MODE', 'auto'),
    chat_deployment=os.getenv('CHAT_DEPLOYMENT'),
    openai_model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
    brand_id=os.getenv('BAI_BRAND_ID', 'aveeno'),
    brand_display=os.getenv('BAI_BRAND_DISPLAY', 'Aveeno'),
    market=os.getenv('BAI_MARKET', 'US'),
    language=os.getenv('BAI_LANGUAGE', 'en-US'),
    source_system=os.getenv('BAI_SOURCE_SYSTEM', 'BrandRank'),
)


def effective_api_key() -> str | None:
    return settings.azure_openai_api_key or settings.openai_api_key


def effective_api_base() -> str | None:
    return settings.azure_openai_endpoint or settings.openai_api_base


def effective_llm_mode() -> str:
    configured = (settings.openai_api_mode or 'auto').strip().lower()
    if configured in {'managed_responses', 'azure_chat'}:
        return configured

    base = (effective_api_base() or '').lower()
    if '/openai/managed' in base:
        return 'managed_responses'

    return 'azure_chat'


def effective_chat_deployment() -> str | None:
    return settings.azure_openai_chat_deployment or settings.chat_deployment
