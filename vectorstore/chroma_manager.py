"""
vectorstore/chroma_manager.py
ChromaDB collection management — init, add documents, query.
This is the single source of truth for all vector store operations.
"""
import sys
import os

# Must be set BEFORE importing sentence_transformers / transformers
# Prevents the Keras 3 / tf-keras conflict in mixed TF+torch environments
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import chromadb
import threading
from chromadb.config import Settings as ChromaSettings
from loguru import logger
from typing import Optional

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import get_settings


class ChromaManager:
    """
    Manages a persistent ChromaDB collection.
    Uses sentence-transformers for local embedding — no API key required.
    """

    def __init__(self):
        settings = get_settings()
        self.collection_name = settings.chroma_collection_name
        self.persist_dir = settings.chroma_persist_dir
        self.embedding_model_name = settings.embedding_model
        self.top_k = settings.rag_top_k

        # ── Embedding model (loaded once at first query) ──
        # fastembed requires full model name e.g. "sentence-transformers/all-MiniLM-L6-v2"
        # but .env stores the short name "all-MiniLM-L6-v2" for readability — map it here
        FASTEMBED_NAME_MAP = {
            "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
            "all-mpnet-base-v2": "sentence-transformers/all-mpnet-base-v2",
        }
        fastembed_model_name = FASTEMBED_NAME_MAP.get(
            self.embedding_model_name, self.embedding_model_name
        )
        logger.info(f"Loading embedding model via fastembed: {fastembed_model_name}")
        from fastembed import TextEmbedding
        self.embed_model = TextEmbedding(model_name=fastembed_model_name)

        # ── ChromaDB persistent client ──
        logger.info(f"Connecting to ChromaDB at: {self.persist_dir}")
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # ── Get or create collection ──
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},  # cosine similarity
        )
        logger.info(
            f"Collection '{self.collection_name}' ready. "
            f"Documents: {self.collection.count()}"
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts using fastembed (ONNX Runtime — no PyTorch)."""
        # fastembed.embed() returns a generator of numpy arrays
        return [emb.tolist() for emb in self.embed_model.embed(texts)]

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """
        Add documents to ChromaDB with their metadata.

        Args:
            documents: List of text chunks.
            metadatas: List of dicts, one per chunk.
                       Expected keys: source, type, url (optional), chunk_index
            ids: Unique string IDs per chunk.
        """
        if not documents:
            logger.warning("add_documents called with empty document list.")
            return

        logger.info(f"Embedding {len(documents)} chunks...")
        embeddings = self.embed_texts(documents)

        logger.info(f"Upserting {len(documents)} chunks to ChromaDB...")
        self.collection.upsert(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        logger.success(
            f"Stored {len(documents)} chunks. Total in collection: {self.collection.count()}"
        )

    def query(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        Query the collection and return top-K results.

        Returns:
            List of dicts: {text, metadata, distance, id}
        """
        k = top_k or self.top_k
        query_embedding = self.embed_texts([query_text])[0]

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, max(self.collection.count(), 1)),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist, doc_id in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
                results["ids"][0],
            ):
                output.append(
                    {
                        "text": doc,
                        "metadata": meta,
                        "distance": round(dist, 4),
                        "id": doc_id,
                    }
                )

        logger.debug(f"Query returned {len(output)} results for: '{query_text[:60]}...'")
        return output

    def get_collection_stats(self) -> dict:
        """Return basic statistics about the collection."""
        count = self.collection.count()
        stats = {"total_documents": count, "collection_name": self.collection_name}

        if count > 0:
            # Sample to get unique sources
            sample = self.collection.get(limit=min(count, 1000), include=["metadatas"])
            sources = set()
            types = set()
            for meta in sample["metadatas"]:
                if "source" in meta:
                    sources.add(meta["source"])
                if "type" in meta:
                    types.add(meta["type"])
            stats["unique_sources"] = list(sources)
            stats["document_types"] = list(types)

        return stats

    def delete_collection(self) -> None:
        """Delete and recreate the collection (use for full re-ingestion)."""
        logger.warning(f"Deleting collection: {self.collection_name}")
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Collection recreated (empty).")

    def delete_by_source(self, source: str) -> None:
        """Remove all chunks belonging to a specific source file/URL."""
        logger.info(f"Deleting all chunks with source='{source}'")
        self.collection.delete(where={"source": source})


# ── Singleton for application-wide reuse ──
_chroma_manager: Optional[ChromaManager] = None
_chroma_lock = threading.Lock()


def get_chroma_manager() -> ChromaManager:
    """Return a cached ChromaManager instance (thread-safe)."""
    global _chroma_manager
    with _chroma_lock:
        if _chroma_manager is None:
            _chroma_manager = ChromaManager()
    return _chroma_manager
