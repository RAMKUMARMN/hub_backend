from pydantic import BaseModel


class DeviceRegisterSchema(BaseModel):
    device_token: str
    platform: str = "android"

    model_config = {"from_attributes": True}
