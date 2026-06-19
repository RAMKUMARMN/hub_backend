from pydantic import BaseModel

class N8NRequest(BaseModel):
	message: str
	task: str

class DocumentSummaryRequest(BaseModel):
    document_text: str
    email: str
