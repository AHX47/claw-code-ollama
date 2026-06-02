"""
rag_skill.py
────────────
Local Retrieval-Augmented Generation using ChromaDB.

Ingest plain-text / Markdown files from a knowledge directory, then
query them semantically – all 100 % offline.

Dependencies
------------
    pip install chromadb sentence-transformers

Usage
-----
    from skills.rag_skill import RagSkill

    rag = RagSkill(knowledge_dir="./knowledge")
    rag.ingest()                          # index all .txt/.md files

    results = rag.search("how to fix memory leaks in Python")
    for r in results:
        print(r["source"], r["text"])

    # Or use as a drop-in for connectivity.search_or_rag:
    from skills.connectivity import search_or_rag
    search_or_rag("memory leaks python", rag_fn=rag.search)
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any


# ── helpers ─────────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = 512,
                overlap: int = 64) -> list[str]:
    """
    Split *text* into overlapping chunks of roughly *chunk_size* characters.
    Simple word-boundary split – good enough for RAG with small models.
    """
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        chunk = " ".join(words[start: start + chunk_size])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks or [text]


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


# ── RagSkill ─────────────────────────────────────────────────────────────────

class RagSkill:
    """
    Local vector-store RAG backed by ChromaDB + sentence-transformers.

    Parameters
    ----------
    knowledge_dir : directory with .txt / .md knowledge files
    db_path       : where ChromaDB persists its data
    collection    : ChromaDB collection name
    model_name    : sentence-transformers embedding model
                    (all-MiniLM-L6-v2 is ~80 MB, fast on CPU)
    top_k         : number of chunks returned per query
    """

    def __init__(
        self,
        knowledge_dir: str | Path = "./knowledge",
        db_path: str = "./chroma_db",
        collection: str = "claw_code_offline",
        model_name: str = "all-MiniLM-L6-v2",
        top_k: int = 4,
    ) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.db_path = db_path
        self.collection_name = collection
        self.model_name = model_name
        self.top_k = top_k
        self._client: Any = None
        self._collection: Any = None
        self._embedder: Any = None

    # ── lazy init ────────────────────────────────────────────────────────────

    def _ensure_ready(self) -> None:
        if self._client is not None:
            return
        try:
            import chromadb  # type: ignore
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "RAG requires chromadb and sentence-transformers.\n"
                "Run: pip install chromadb sentence-transformers"
            ) from exc

        self._embedder = SentenceTransformer(self.model_name)
        self._client = chromadb.PersistentClient(path=self.db_path)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── public API ───────────────────────────────────────────────────────────

    def ingest(self, extensions: tuple[str, ...] = (".txt", ".md")) -> int:
        """
        Index all files in *knowledge_dir* with matching *extensions*.
        Already-indexed chunks (identified by file hash + chunk index) are
        skipped, so re-running ingest is idempotent.

        Returns the number of new chunks added.
        """
        self._ensure_ready()
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        files = [
            p for p in self.knowledge_dir.rglob("*")
            if p.suffix.lower() in extensions and p.is_file()
        ]

        added = 0
        for file_path in files:
            file_hash = _file_hash(file_path)
            text = file_path.read_text(encoding="utf-8", errors="replace")
            chunks = _chunk_text(text)

            ids, docs, metas, embeds = [], [], [], []
            for idx, chunk in enumerate(chunks):
                doc_id = f"{file_hash}_{idx}"
                # Skip already indexed chunks
                existing = self._collection.get(ids=[doc_id])
                if existing["ids"]:
                    continue
                ids.append(doc_id)
                docs.append(chunk)
                metas.append({"source": str(file_path), "chunk": idx})
                embeds.append(
                    self._embedder.encode(chunk, normalize_embeddings=True).tolist()
                )

            if ids:
                self._collection.add(
                    ids=ids, documents=docs, metadatas=metas, embeddings=embeds
                )
                added += len(ids)
                print(f"[rag_skill] Indexed {len(ids)} chunks from {file_path.name}")

        print(f"[rag_skill] Ingest complete – {added} new chunks added.")
        return added

    def search(self, query: str) -> list[dict[str, str]]:
        """
        Return up to *top_k* relevant chunks for *query*.
        Each result is ``{"source": path, "text": chunk, "score": str}``.
        """
        self._ensure_ready()
        query_emb = self._embedder.encode(
            query, normalize_embeddings=True
        ).tolist()
        results = self._collection.query(
            query_embeddings=[query_emb],
            n_results=min(self.top_k, self._collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )
        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "source": meta.get("source", "unknown"),
                "text": doc,
                "score": f"{1.0 - dist:.3f}",   # cosine similarity
            })
        return output

    def add_document(self, text: str, source: str = "manual") -> None:
        """Ingest a raw string directly (no file needed)."""
        self._ensure_ready()
        chunks = _chunk_text(text)
        h = hashlib.sha256(text.encode()).hexdigest()[:16]
        ids, docs, metas, embeds = [], [], [], []
        for idx, chunk in enumerate(chunks):
            ids.append(f"{h}_{idx}")
            docs.append(chunk)
            metas.append({"source": source, "chunk": idx})
            embeds.append(
                self._embedder.encode(chunk, normalize_embeddings=True).tolist()
            )
        self._collection.add(ids=ids, documents=docs, metadatas=metas,
                             embeddings=embeds)
        print(f"[rag_skill] Added {len(ids)} chunks from '{source}'.")
