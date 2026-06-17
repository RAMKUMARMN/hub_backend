from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Application
    app_name: str = "CixioHub API"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:admin123@localhost:5432/cixiohub"

    # Redis
    redis_url: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Notification Service
    notification_service_url: str = "http://localhost:8001/api/v1/notify/send"

    # AI / LLM Configuration
    use_remote_ai: bool = True
    ai_service_url: str = "http://localhost:8003"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_vision_model: str = "qwen3-vl:2b"
    enable_vision_rag: bool = True
    enable_web_search: bool = False
    tavily_api_key: str | None = None
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "user_documents"
    enable_reranker: bool = False
    reranker_model: str = "mixedbread-ai/mxbai-rerank-base-v1"

    # AI Service — handles LLM, RAG, document extraction
    ai_service_url: str = "http://localhost:8003"

    # Notify Service
    notify_service_url: str = "http://localhost:8001"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8002

    # RabbitMQ
    rabbitmq_url: str

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

    #cloudinary details
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

settings = Settings()
print("DB URL:", settings.database_url)