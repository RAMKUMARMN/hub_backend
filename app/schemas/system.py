from pydantic import BaseModel


class SystemSettingUpdate(BaseModel):
    value: dict


class HealthResponse(BaseModel):
    database: str
    redis: str
    rabbitmq: str
    qdrant: str