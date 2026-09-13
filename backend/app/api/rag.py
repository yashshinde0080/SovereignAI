"""RAG API Endpoints"""
import os
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from typing import List

from app.schemas.rag import (
    DocumentUpload,
    QueryRequest,
    QueryResponse,
    DocumentList
)
from app.vectorstore.manager import VectorStoreManager


router = APIRouter()


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...)
):
    """Upload document for RAG"""
    vector_store: VectorStoreManager = request.app.state.vector_store
    
    # Check Content-Length before reading body (fail fast)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max: 50MB")
    
    # Validate file type before reading body
    filename = (file.filename or "").lower()
    if not filename.endswith(('.txt', '.pdf')):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}. Only .txt and .pdf files are accepted.")
    
    # Save file
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max: 50MB")
    
    # Process based on file type
    filename = (file.filename or "").lower()
    text = ""
    if filename.endswith('.txt'):
        text = content.decode('utf-8', errors='replace')
    elif filename.endswith('.pdf'):
        pdf_plugin = request.app.state.plugin_manager.get_plugin('pdf_ingestion')
        if pdf_plugin is None:
            raise HTTPException(
                status_code=503,
                detail="PDF plugin not available (pypdf not installed). Upload a .txt file instead."
            )
        text = await pdf_plugin.extract_text(content)
        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail="No text could be extracted from this PDF (scanned/image-only PDFs are not supported)."
            )
    else:
        raise HTTPException(status_code=400, detail=f"Unhandled file type: {filename}")

    try:
        # Add to vector store
        doc_id = vector_store.ingest_text(
            text=text,
            filename=file.filename,
            metadata={"filename": file.filename}
        )
    except RuntimeError as e:
        # Vector store not initialized / embedder failed — say so plainly.
        raise HTTPException(status_code=503, detail=f"Vector store unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "success",
        "document_id": doc_id,
        "filename": file.filename,
        "chunks": len(vector_store.get_document_chunks(doc_id))
    }


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: Request, query: QueryRequest):
    """Query documents"""
    vector_store: VectorStoreManager = request.app.state.vector_store
    
    # Search similar chunks
    search_results = vector_store.search(
        query_text=query.query,
        top_k=query.top_k
    )

    results = [
        {
            "text": r.content,
            "score": r.score,
            "metadata": r.metadata,
            "document_id": r.document_id
        }
        for r in search_results
    ]
    
    # If model is loaded, generate response
    if request.app.state.active_engine and query.generate_response:
        context = "\n\n".join([r["text"] for r in results])
        
        prompt = (
            f"Context information is provided below:\n"
            f"---------------------\n"
            f"{context}\n"
            f"---------------------\n"
            f"Given the context information, answer the following query. "
            f"If the context does not contain the answer, answer based on your existing knowledge.\n"
            f"Query: {query.query}"
        )
        
        tokenizer = getattr(request.app.state.active_engine, "tokenizer", None)
        if tokenizer and hasattr(tokenizer, "apply_chat_template"):
            try:
                prompt = tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt}], 
                    tokenize=False, 
                    add_generation_prompt=True
                )
            except Exception:
                pass
                
        response = await request.app.state.active_engine.generate(
            input_data=prompt,
            max_tokens=query.max_tokens
        )
        
        return QueryResponse(
            query=query.query,
            results=results,
            generated_response=response.get("output") or response.get("text") or ""
        )
    
    return QueryResponse(
        query=query.query,
        results=results,
        generated_response=None
    )


@router.get("/stats")
async def rag_stats(request: Request):
    """Vector store health — FAISS vs metadata counts. in_sync=false means desync
    (search would silently return nothing until the startup self-heal runs)."""
    vector_store: VectorStoreManager = request.app.state.vector_store
    stats = vector_store.get_stats()
    stats["in_sync"] = stats["total_vectors"] == stats["total_embeddings"]
    return stats


@router.get("/documents", response_model=DocumentList)
async def list_documents(request: Request):
    """List indexed documents"""
    vector_store: VectorStoreManager = request.app.state.vector_store
    documents = vector_store.list_documents()
    return DocumentList(documents=documents)


@router.get("/documents/{doc_id}/chunks")
async def get_document_chunks(request: Request, doc_id: str):
    """Get all chunks (content previews) for a document."""
    vector_store: VectorStoreManager = request.app.state.vector_store
    chunks = vector_store.get_document_chunks(doc_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "document_id": doc_id,
        "chunks": [
            {
                "chunk_index": c.get("chunk_index", 0),
                "content": c.get("content", ""),
                "metadata": c.get("metadata", {}),
            }
            for c in chunks
        ]
    }


@router.delete("/documents/{doc_id}")
async def delete_document(request: Request, doc_id: str):
    """Delete document from index"""
    vector_store: VectorStoreManager = request.app.state.vector_store
    try:
        vector_store.delete_document(doc_id)
        success = True
    except Exception:
        success = False
    
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"status": "deleted", "document_id": doc_id}