import os
import uuid
import shutil
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from app.models.document import Document

# Define a local folder where uploaded files will be saved temporarily/permanently
UPLOAD_DIR = os.path.join(os.getcwd(), "uploaded_files")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 1. This is the standalone function your router __init__.py is looking for globally
async def extract_text(file_path: str, file_type: str) -> str:
    """
    Temporary placeholder for text extraction. 
    Returns a dummy string so the application can run.
    """
    return f"Sample extracted text content from file at {file_path}"


# 2. This is your main service class handling CRUD operations
class DocumentService:
    
    @staticmethod
    def upload_document(db: Session, file: UploadFile, user_id: uuid.UUID) -> Document:
        # Generate a unique filename locally to prevent overwriting files with the same name
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save the uploaded file to the local disk
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not save file to disk: {str(e)}"
            )
            
        # Save the record to the PostgreSQL database
        db_document = Document(
            user_id=user_id,
            filename=file.filename,
            file_type=file.content_type or "unknown",
            file_size=os.path.getsize(file_path),
            storage_path=file_path,
            processed=False  # Set to False initially until background RAG worker processes it
        )
        
        db.add(db_document)
        db.commit()
        db.refresh(db_document)
        return db_document

    @staticmethod
    def get_user_documents(db: Session, user_id: uuid.UUID) -> list[Document]:
        # Fetch all documents belonging to this specific user
        return db.query(Document).filter(Document.user_id == user_id).all()

    @staticmethod
    def delete_document(db: Session, document_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        # Find the document and make sure it belongs to the requesting user
        db_document = db.query(Document).filter(
            Document.id == document_id, 
            Document.user_id == user_id
        ).first()
        
        if not db_document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or unauthorized access"
            )
            
        # Remove the actual file from disk storage
        if os.path.exists(db_document.storage_path):
            try:
                os.remove(db_document.storage_path)
            except Exception as e:
                # Log the error, but we can still proceed to clear the DB entry if needed
                print(f"Error deleting file from disk: {e}")

        # Delete the record from the database
        db.delete(db_document)
        db.commit()
        return True
    