"""RAG Schemas"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentUpload(BaseModel):
    filename: str
    content_type: str


class QueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    generate_response: bool = True
    max_tokens: int = Field(default=256, ge=1, le=1024)


class SearchResult(BaseModel):
    text: str
    score: float
    metadata: Dict[str, Any]


class Citation(BaseModel):
    """A source the answer cited AND that was actually retrieved.

    Built only from retrieved chunks — never from the model's own text — so
    a citation the model invents cannot reach the client."""
    document_id: str
    filename: str
    chunk_index: int
    score: float
    quote: str


class QueryResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    generated_response: Optional[str]
    citations: List[Citation] = Field(default_factory=list)
    insufficient_evidence: bool = False
    unverified_citation_count: int = 0


class DocumentInfo(BaseModel):
    id: str
    filename: str
    chunks: int
    created_at: str


class DocumentList(BaseModel):
    documents: List[DocumentInfo]