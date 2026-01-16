"""
Direct Qdrant Manager for Biblical Quotation Detection

This module provides direct vector storage using Qdrant with sentence-transformers
embeddings, bypassing Mem0's LLM-based memory extraction for fast bulk ingestion.
"""

import os
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class QdrantManager:
    """
    Direct Qdrant manager for biblical verse storage and search.

    Uses sentence-transformers for local embeddings (no API calls).
    Much faster than Mem0's memory extraction approach.
    """

    def __init__(
        self,
        collection_name: str = "biblical_verses",
        embedding_model: str = "intfloat/multilingual-e5-large",
        qdrant_path: Optional[str] = None,
    ):
        """
        Initialize Qdrant manager.

        Args:
            collection_name: Name of the Qdrant collection
            embedding_model: HuggingFace embedding model name
            qdrant_path: Path to Qdrant database (None for default)
        """
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model

        # Set Qdrant path
        if qdrant_path is None:
            project_root = Path(__file__).parent.parent.parent
            self.qdrant_path = str(project_root / "data" / "processed" / "qdrant_direct")
        else:
            self.qdrant_path = qdrant_path

        # Ensure directory exists
        Path(self.qdrant_path).mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing QdrantManager at {self.qdrant_path}")

        # Initialize embedding model
        logger.info(f"Loading embedding model: {self.embedding_model_name}")
        self.embedding_model = SentenceTransformer(self.embedding_model_name)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        logger.info(f"Embedding dimension: {self.embedding_dim}")

        # Initialize Qdrant client
        self.client = QdrantClient(path=self.qdrant_path)

        # Create collection if needed
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            logger.info(f"Creating collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
        else:
            logger.info(f"Collection {self.collection_name} already exists")

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text."""
        return self.embedding_model.encode(text).tolist()

    def embed_texts_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently."""
        return self.embedding_model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
        ).tolist()

    def add_verse(
        self,
        verse_id: int,
        greek_text: str,
        metadata: Dict,
    ) -> bool:
        """
        Add a single verse to the collection.

        Args:
            verse_id: Unique integer ID for the verse
            greek_text: Greek text to embed
            metadata: Verse metadata (reference, book, chapter, etc.)

        Returns:
            True if successful
        """
        try:
            embedding = self.embed_text(greek_text)

            point = PointStruct(
                id=verse_id,
                vector=embedding,
                payload={
                    "text": greek_text,
                    **metadata,
                },
            )

            self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )
            return True

        except Exception as e:
            logger.error(f"Failed to add verse {verse_id}: {e}")
            return False

    def add_verses_batch(
        self,
        verses: List[Dict],
        batch_size: int = 100,
    ) -> Dict:
        """
        Add multiple verses efficiently using batch embedding.

        Args:
            verses: List of dicts with 'id', 'text', and 'metadata' keys
            batch_size: Number of verses per batch

        Returns:
            Summary statistics
        """
        total = len(verses)
        added = 0
        failed = 0

        logger.info(f"Adding {total} verses in batches of {batch_size}")

        for i in range(0, total, batch_size):
            batch = verses[i:i + batch_size]

            try:
                # Extract texts for batch embedding
                texts = [v["text"] for v in batch]

                # Generate embeddings in batch (much faster)
                embeddings = self.embedding_model.encode(
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=False,
                )

                # Create points
                points = []
                for j, (verse, embedding) in enumerate(zip(batch, embeddings)):
                    points.append(
                        PointStruct(
                            id=verse["id"],
                            vector=embedding.tolist(),
                            payload={
                                "text": verse["text"],
                                **verse.get("metadata", {}),
                            },
                        )
                    )

                # Upsert batch
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                )

                added += len(batch)

                # Progress logging every 10 batches
                if ((i // batch_size) + 1) % 10 == 0:
                    logger.info(f"Progress: {i + len(batch)}/{total} verses ({(i + len(batch)) / total * 100:.1f}%)")

            except Exception as e:
                logger.error(f"Batch failed at index {i}: {e}")
                failed += len(batch)

        logger.info(f"Batch complete: {added} added, {failed} failed")

        return {
            "total": total,
            "added": added,
            "failed": failed,
        }

    def search(
        self,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.0,
        book_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search for semantically similar verses.

        Args:
            query: Greek text to search for
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)
            book_filter: Filter by book name
            source_filter: Filter by source

        Returns:
            List of matching verses with scores
        """
        try:
            # Generate query embedding
            query_embedding = self.embed_text(query)

            # Build filter if needed
            filter_conditions = []
            if book_filter:
                filter_conditions.append(
                    FieldCondition(key="book", match=MatchValue(value=book_filter))
                )
            if source_filter:
                filter_conditions.append(
                    FieldCondition(key="source", match=MatchValue(value=source_filter))
                )

            query_filter = Filter(must=filter_conditions) if filter_conditions else None

            # Search
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
            )

            # Format results
            formatted = []
            for hit in results:
                formatted.append({
                    "id": hit.id,
                    "score": hit.score,
                    "text": hit.payload.get("text", ""),
                    "reference": hit.payload.get("reference", ""),
                    "book": hit.payload.get("book", ""),
                    "chapter": hit.payload.get("chapter"),
                    "verse": hit.payload.get("verse"),
                    "source": hit.payload.get("source", ""),
                })

            logger.info(f"Search returned {len(formatted)} results for: {query[:50]}...")
            return formatted

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def get_collection_info(self) -> Dict:
        """Get information about the collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
                "embedding_model": self.embedding_model_name,
                "embedding_dim": self.embedding_dim,
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}

    def delete_collection(self):
        """Delete the entire collection."""
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise

    def clear_collection(self):
        """Clear all points from the collection (recreate)."""
        try:
            self.delete_collection()
            self._ensure_collection()
            logger.info(f"Cleared collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            raise
