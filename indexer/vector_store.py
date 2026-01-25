"""Vector store for semantic code search using ChromaDB."""

import os
from typing import Dict, List, Optional, Any

from config import get_index_path


class VectorStore:
    """ChromaDB-based vector store for code embeddings."""

    COLLECTION_NAME = "code_methods"

    def __init__(self):
        """Initialize the vector store."""
        self.index_path = get_index_path()
        self.vectors_path = os.path.join(self.index_path, "vectors")
        self._client = None
        self._collection = None

    def _ensure_initialized(self) -> bool:
        """Lazy initialization of ChromaDB client.

        Returns:
            True if initialized successfully, False otherwise
        """
        if self._client is not None:
            return True

        try:
            import chromadb
            from chromadb.config import Settings

            # Create vectors directory
            os.makedirs(self.vectors_path, exist_ok=True)

            # Initialize persistent client
            self._client = chromadb.PersistentClient(
                path=self.vectors_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "Code method summaries for semantic search"}
            )

            return True
        except ImportError:
            return False
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if ChromaDB is available.

        Returns:
            True if ChromaDB is installed and working
        """
        try:
            import chromadb
            return True
        except ImportError:
            return False

    def add_methods(self, methods: List[Dict[str, Any]]) -> bool:
        """Add method summaries to the vector store.

        Args:
            methods: List of method dicts with keys:
                - id: Unique identifier (class.method)
                - summary: LLM-generated summary (this gets embedded)
                - code: Original source code
                - file_path: Path to source file
                - line: Line number
                - class_name: Class containing the method
                - method_name: Method name
                - annotations: List of annotations

        Returns:
            True if added successfully, False otherwise
        """
        if not self._ensure_initialized():
            return False

        if not methods:
            return True

        try:
            # Prepare data for ChromaDB
            ids = []
            documents = []  # Summaries - these get embedded
            metadatas = []

            for method in methods:
                method_id = method.get('id', f"{method.get('class_name', 'Unknown')}.{method.get('method_name', 'unknown')}")
                ids.append(method_id)
                documents.append(method.get('summary', ''))
                # Truncate code to ~500 chars (about 10-15 lines) to reduce storage
                code = method.get('code', '')
                if len(code) > 500:
                    code = code[:500] + '\n// ... (truncated)'

                metadatas.append({
                    'file_path': method.get('file_path', ''),
                    'line': method.get('line', 0),
                    'class_name': method.get('class_name', ''),
                    'method_name': method.get('method_name', ''),
                    'annotations': ','.join(method.get('annotations', [])),
                    'code': code
                })

            # Add to collection (upsert to handle updates)
            self._collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

            return True
        except Exception:
            return False

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for methods semantically similar to the query.

        Args:
            query: Natural language search query
            top_k: Number of results to return

        Returns:
            List of matching methods with scores
        """
        if not self._ensure_initialized():
            return []

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                include=['documents', 'metadatas', 'distances']
            )

            # Format results
            matches = []
            if results and results.get('ids') and results['ids'][0]:
                for i, method_id in enumerate(results['ids'][0]):
                    match = {
                        'id': method_id,
                        'summary': results['documents'][0][i] if results.get('documents') else '',
                        'distance': results['distances'][0][i] if results.get('distances') else 0,
                        'relevance': 1 - (results['distances'][0][i] if results.get('distances') else 0),
                    }

                    # Add metadata
                    if results.get('metadatas') and results['metadatas'][0]:
                        metadata = results['metadatas'][0][i]
                        match.update({
                            'file_path': metadata.get('file_path', ''),
                            'line': metadata.get('line', 0),
                            'class_name': metadata.get('class_name', ''),
                            'method_name': metadata.get('method_name', ''),
                            'annotations': metadata.get('annotations', '').split(',') if metadata.get('annotations') else [],
                            'code': metadata.get('code', '')
                        })

                    matches.append(match)

            return matches
        except Exception:
            return []

    def clear(self) -> bool:
        """Clear all vectors from the store.

        Returns:
            True if cleared successfully, False otherwise
        """
        if not self._ensure_initialized():
            return False

        try:
            # Delete and recreate collection
            self._client.delete_collection(self.COLLECTION_NAME)
            self._collection = self._client.create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "Code method summaries for semantic search"}
            )
            return True
        except Exception:
            return False

    def remove_by_file(self, file_path: str) -> bool:
        """Remove all vectors for methods from a specific file.

        Args:
            file_path: Path to the source file

        Returns:
            True if removed successfully
        """
        if not self._ensure_initialized():
            return False

        try:
            # Find all IDs with this file path
            results = self._collection.get(
                where={"file_path": file_path},
                include=[]
            )

            if results and results.get('ids'):
                self._collection.delete(ids=results['ids'])

            return True
        except Exception:
            return False

    def get_indexed_files(self) -> set:
        """Get set of all file paths that have been indexed.

        Returns:
            Set of file paths
        """
        if not self._ensure_initialized():
            return set()

        try:
            # Get all unique file paths
            results = self._collection.get(include=['metadatas'])

            files = set()
            if results and results.get('metadatas'):
                for meta in results['metadatas']:
                    if meta.get('file_path'):
                        files.add(meta['file_path'])

            return files
        except Exception:
            return set()

    def get_count(self) -> int:
        """Get number of methods in the vector store.

        Returns:
            Number of indexed methods
        """
        if not self._ensure_initialized():
            return 0

        try:
            return self._collection.count()
        except Exception:
            return 0

    def has_index(self) -> bool:
        """Check if vector index exists and has data.

        Returns:
            True if index exists with data
        """
        return self.get_count() > 0
