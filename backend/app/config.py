from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Klarnova"
    API_V1_STR: str = "/v1"
    
    # LLM
    LLM_PROVIDER: str = "ollama"
    OPENAI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3.2:3b"
    
    # Databases
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/klarnova"
    REDIS_URL: str = "redis://localhost:6379/0"
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    
    # K8s
    KUBE_IN_CLUSTER: bool = False
    
    # Observability
    PROMETHEUS_URL: str = "http://localhost:9090"
    ALERTMANAGER_WEBHOOK_TOKEN: str = "secret-token"
    LOKI_URL: str = "" # Optional
    
    # Extra config
    CHROMA_PERSIST_DIR: str = "data/chroma"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    TARGET_NAMESPACE: str = "default"
    KB_REFRESH_INTERVAL: int = 3600
    KB_SOURCE_LIST: str = "knowledge-base/sources.yaml"
    KB_AUTO_INGEST: bool = True
    
    # Auth
    JWT_SECRET: str = "supersecret"
    JWT_EXPIRY: int = 3600
    ALGORITHM: str = "HS256"

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "ignore"

settings = Settings()
