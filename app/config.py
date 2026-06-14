from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    app_name: str = "CixioHub API"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://cixiohub:cixiohub@localhost:5432/cixiohub"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Ollama (accessed via the AI service in full-stack; kept here for direct dev)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_embed_model: str = "nomic-embed-text"

    # AI Service — handles LLM, RAG, document extraction
    ai_service_url: str = "http://localhost:8003"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8002

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    # AWS / S3 / MinIO
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    aws_endpoint_url: str = ""  # Set to MinIO URL in dev (http://localhost:9000)
    s3_bucket: str = "cixiohub-uploads"
    s3_bucket_name: str = "cixiohub-uploads"  # alias kept for compat

    # SMTP / Email
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from_email: str = "noreply@hub.cixio.dev"

    # Google OAuth (optional)
    google_client_id: str = ""
    google_client_secret: str = ""

    # File upload
    max_upload_size_mb: int = 50

    # Test constants
    test_email: str = ""
    test_password: str = ""
    test_name: str = ""
    test_phone: str = ""


settings = Settings()
