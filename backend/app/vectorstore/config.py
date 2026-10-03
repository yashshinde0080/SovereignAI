"""
Vector store configuration.
Defaults from Settings (storage.toml was optional, never shipped, removed).
"""

import os
from dataclasses import dataclass


@dataclass
class VectorStoreConfig:
    from app.config import settings
    index_path: str = str(settings.data_dir / "vector_index")
    index_file: str = "index.faiss"
    metadata_db: str = "metadata.db"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunk_size: int = 512
    chunk_overlap: int = 64
    max_chunks_per_document: int = 10000
    nprobe: int = 10
    top_k_default: int = 5
    min_score: float = 0.15  # retrieval floor when query passes 0.0 (normalized cosine)
    mmr_lambda: float = 0.7  # 1.0 = pure relevance, 0.0 = pure diversity
    use_gpu: bool = False
    index_type: str = "Flat"  # "Flat", "IVFFlat", "IVFPQ" — Flat exact default: correct at any corpus size, zero training edge cases
    nlist: int = 100
    normalize_embeddings: bool = True

    @property
    def index_full_path(self) -> str:
        return os.path.join(self.index_path, self.index_file)

    @property
    def metadata_db_path(self) -> str:
        return os.path.join(self.index_path, self.metadata_db)
