from pydantic import BaseModel

class RAGQueryRequest(BaseModel):
    query: str
