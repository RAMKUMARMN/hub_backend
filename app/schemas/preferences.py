from pydantic import BaseModel


class PreferencesResponse(BaseModel):
    theme: str
    notification_settings: dict
    security_settings: dict

    model_config = {"from_attributes": True}


class PreferencesUpdate(BaseModel):
    theme: str | None = None
    notification_settings: dict | None = None


class SecuritySettingsUpdate(BaseModel):
    security_settings: dict