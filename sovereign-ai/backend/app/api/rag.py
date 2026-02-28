from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

class RAGQueryRequest(BaseModel):
    query: str

router = APIRouter(prefix="/v1/rag")

# Mock database
documents_db = []
vectors_db = []

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    # Mocking reading and chunking document
    content = await file.read()
    filename = file.filename

    # Store mock metadata
    doc_id = len(documents_db) + 1
    documents_db.append({"id": doc_id, "name": filename, "size": len(content)})

    # Mock chunking and embedding
    vectors_db.append({"doc_id": doc_id, "chunks": 5})

    return {"status": "success", "message": f"Document {filename} processed and indexed."}

@router.get("/documents")
def list_documents():
    return documents_db

@router.post("/query")
def query_rag(req: RAGQueryRequest):
    if not documents_db:
        return {"context": "", "message": "No documents indexed."}

    # Mock retrieval logic
    context = f"Found relevant information regarding '{req.query}' in documents: {[d['name'] for d in documents_db]}."
    return {"context": context, "message": "Retrieval complete."}
