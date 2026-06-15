from pydantic import BaseModel

class N8NRequest(BaseModel):
	message: str
	task: str
