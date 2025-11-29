"""
Mem0 Manager for Biblical Quotation Detection

This module handles the configuration and management of Mem0 for vector-based
semantic search of biblical verses.
"""

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path
from mem0 import Memory
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class Mem0Manager:
    """
    Manager class for Mem0 memory operations.

    Handles initialization, adding verses to vector store, and semantic search.
    """

    def __init__(
        self,
        vector_store: str = "qdrant",
        embedding_model: str = "intfloat/multilingual-e5-large",
        qdrant_path: Optional[str] = None,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-20250514"
    ):
        """
        Initialize Mem0 with configuration.

        Args:
            vector_store: Vector store backend (qdrant, chromadb, etc.)
            embedding_model: HuggingFace embedding model name
            qdrant_path: Path to Qdrant database (None for in-memory)
            llm_provider: LLM provider for Mem0
            llm_model: LLM model name
        """
        self.vector_store = vector_store or os.getenv("MEM0_VECTOR_STORE", "qdrant")
        self.embedding_model = embedding_model or os.getenv(
            "MEM0_EMBEDDING_MODEL",
            "intfloat/multilingual-e5-large"
        )
        self.llm_provider = llm_provider or os.getenv("MEM0_LLM_PROVIDER", "anthropic")
        self.llm_model = llm_model or os.getenv("MEM0_LLM_MODEL", "claude-sonnet-4-20250514")

        # Set Qdrant path
        if qdrant_path is None:
            project_root = Path(__file__).parent.parent.parent
            self.qdrant_path = str(project_root / "data" / "processed" / "qdrant_db")
        else:
            self.qdrant_path = qdrant_path

        # Ensure directory exists
        Path(self.qdrant_path).mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing Mem0Manager with {self.vector_store} at {self.qdrant_path}")

        # Build configuration
        self.config = self._build_config()

        # Initialize Mem0
        self.memory = None
        self._initialize_memory()

    def _build_config(self) -> Dict:
        """Build Mem0 configuration dictionary."""
        config = {
            "vector_store": {
                "provider": self.vector_store,
                "config": {
                    "collection_name": "biblical_verses",
                    "embedding_model_dims": 1024,  # multilingual-e5-large dimension
                }
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": self.embedding_model,
                }
            },
            "llm": {
                "provider": self.llm_provider,
                "config": {
                    "model": self.llm_model,
                    "temperature": 0.1,
                    "max_tokens": 2000,
                }
            }
        }

        # Add path for Qdrant
        if self.vector_store == "qdrant":
            config["vector_store"]["config"]["path"] = self.qdrant_path

        # Add API key if using Anthropic
        if self.llm_provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key or api_key == "your_key_here":
                logger.warning("ANTHROPIC_API_KEY not set properly in .env file")
            else:
                config["llm"]["config"]["api_key"] = api_key

        return config

    def _initialize_memory(self):
        """Initialize Mem0 Memory instance."""
        try:
            self.memory = Memory.from_config(self.config)
            logger.info("Mem0 Memory initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Mem0: {e}")
            raise

    def add_verse(
        self,
        verse_id: str,
        greek_text: str,
        metadata: Dict,
        user_id: str = "biblical_corpus"
    ) -> Dict:
        """
        Add a single verse to the vector store.

        Args:
            verse_id: Unique identifier for the verse
            greek_text: The Greek text to embed
            metadata: Additional metadata (reference, book, chapter, etc.)
            user_id: User ID for memory organization

        Returns:
            Dictionary with result information
        """
        try:
            # Prepare metadata
            full_metadata = {
                "verse_id": verse_id,
                **metadata
            }

            # Add to memory
            result = self.memory.add(
                messages=greek_text,
                user_id=user_id,
                metadata=full_metadata
            )

            logger.debug(f"Added verse {metadata.get('reference', verse_id)} to memory")
            return result

        except Exception as e:
            logger.error(f"Failed to add verse {verse_id}: {e}")
            raise

    def add_verses_batch(
        self,
        verses: List[Dict],
        user_id: str = "biblical_corpus",
        batch_size: int = 100
    ) -> Dict:
        """
        Add multiple verses in batches.

        Args:
            verses: List of verse dictionaries with 'text' and 'metadata' keys
            user_id: User ID for memory organization
            batch_size: Number of verses to process at once

        Returns:
            Summary statistics
        """
        total = len(verses)
        added = 0
        failed = 0

        logger.info(f"Adding {total} verses to memory in batches of {batch_size}")

        for i in range(0, total, batch_size):
            batch = verses[i:i + batch_size]

            for verse in batch:
                try:
                    self.add_verse(
                        verse_id=verse.get("id", f"verse_{i}"),
                        greek_text=verse["text"],
                        metadata=verse.get("metadata", {}),
                        user_id=user_id
                    )
                    added += 1
                except Exception as e:
                    logger.error(f"Failed to add verse: {e}")
                    failed += 1

            if (i // batch_size + 1) % 10 == 0:
                logger.info(f"Progress: {i + len(batch)}/{total} verses processed")

        logger.info(f"Batch complete: {added} added, {failed} failed")

        return {
            "total": total,
            "added": added,
            "failed": failed
        }

    def search(
        self,
        query: str,
        user_id: str = "biblical_corpus",
        limit: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for semantically similar verses.

        Args:
            query: Greek text to search for
            user_id: User ID to search within
            limit: Maximum number of results
            filters: Optional metadata filters

        Returns:
            List of matching verses with similarity scores
        """
        try:
            results = self.memory.search(
                query=query,
                user_id=user_id,
                limit=limit
            )

            logger.info(f"Search returned {len(results)} results for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def get_all_memories(
        self,
        user_id: str = "biblical_corpus"
    ) -> List[Dict]:
        """
        Retrieve all memories for a user.

        Args:
            user_id: User ID to retrieve memories for

        Returns:
            List of all memories
        """
        try:
            results = self.memory.get_all(user_id=user_id)
            logger.info(f"Retrieved {len(results)} memories")
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            raise

    def delete_all(self, user_id: str = "biblical_corpus"):
        """
        Delete all memories for a user.

        Args:
            user_id: User ID to delete memories for
        """
        try:
            self.memory.delete_all(user_id=user_id)
            logger.info(f"Deleted all memories for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete memories: {e}")
            raise

    def get_stats(self) -> Dict:
        """
        Get statistics about the vector store.

        Returns:
            Dictionary with statistics
        """
        try:
            # Try to get memory count
            memories = self.get_all_memories()

            return {
                "vector_store": self.vector_store,
                "embedding_model": self.embedding_model,
                "qdrant_path": self.qdrant_path,
                "total_memories": len(memories) if memories else 0,
            }
        except Exception as e:
            logger.warning(f"Could not get full stats: {e}")
            return {
                "vector_store": self.vector_store,
                "embedding_model": self.embedding_model,
                "qdrant_path": self.qdrant_path,
                "total_memories": "unknown",
            }
