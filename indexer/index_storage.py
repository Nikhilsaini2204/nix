"""Index storage for persisting and loading code index."""

import os
import json
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime

from config import get_index_path


class IndexStorage:
    """Handle persistence of code index to .nix/index/ folder."""

    # Index file names
    CLASSES_FILE = "classes.json"
    METHODS_FILE = "methods.json"
    CALL_GRAPH_FILE = "call_graph.json"
    META_FILE = "meta.json"

    def __init__(self, project_root: str = None):
        """Initialize index storage.

        Args:
            project_root: Root of the project. If None, uses current directory.
        """
        self.project_root = project_root or os.getcwd()
        self.index_path = get_index_path()

    def ensure_index_dir(self) -> bool:
        """Create index directory if it doesn't exist.

        Returns:
            True if directory exists or was created, False on error
        """
        try:
            os.makedirs(self.index_path, exist_ok=True)
            return True
        except Exception:
            return False

    def save_index_data(self, classes: List[Dict], methods: List[Dict],
                        call_graph: Dict, file_hashes: Dict[str, str]) -> bool:
        """Save index data to files.

        Args:
            classes: List of class information dictionaries
            methods: List of method information dictionaries
            call_graph: Call graph dictionary
            file_hashes: Dict mapping file paths to their content hashes

        Returns:
            True if saved successfully, False on error
        """
        if not self.ensure_index_dir():
            return False

        try:
            # Save classes
            classes_path = os.path.join(self.index_path, self.CLASSES_FILE)
            with open(classes_path, 'w', encoding='utf-8') as f:
                json.dump(classes, f, indent=2)

            # Save methods
            methods_path = os.path.join(self.index_path, self.METHODS_FILE)
            with open(methods_path, 'w', encoding='utf-8') as f:
                json.dump(methods, f, indent=2)

            # Save call graph
            call_graph_path = os.path.join(self.index_path, self.CALL_GRAPH_FILE)
            with open(call_graph_path, 'w', encoding='utf-8') as f:
                json.dump(call_graph, f, indent=2)

            # Save metadata
            meta = {
                'indexed_at': datetime.now().isoformat(),
                'project_root': self.project_root,
                'file_count': len(file_hashes),
                'class_count': len(classes),
                'method_count': len(methods),
                'file_hashes': file_hashes
            }
            meta_path = os.path.join(self.index_path, self.META_FILE)
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2)

            return True
        except Exception:
            return False

    def load_index_data(self) -> Optional[Dict[str, Any]]:
        """Load index data from files.

        Returns:
            Dictionary with 'classes', 'methods', 'call_graph', 'meta' keys,
            or None if index doesn't exist or is corrupted
        """
        try:
            classes_path = os.path.join(self.index_path, self.CLASSES_FILE)
            methods_path = os.path.join(self.index_path, self.METHODS_FILE)
            call_graph_path = os.path.join(self.index_path, self.CALL_GRAPH_FILE)
            meta_path = os.path.join(self.index_path, self.META_FILE)

            if not all(os.path.exists(p) for p in [classes_path, methods_path, call_graph_path, meta_path]):
                return None

            with open(classes_path, 'r', encoding='utf-8') as f:
                classes = json.load(f)

            with open(methods_path, 'r', encoding='utf-8') as f:
                methods = json.load(f)

            with open(call_graph_path, 'r', encoding='utf-8') as f:
                call_graph = json.load(f)

            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            return {
                'classes': classes,
                'methods': methods,
                'call_graph': call_graph,
                'meta': meta
            }
        except Exception:
            return None

    def is_index_stale(self, java_files: List[str]) -> bool:
        """Check if the index needs to be rebuilt.

        Args:
            java_files: List of Java file paths to check

        Returns:
            True if index is stale or doesn't exist, False if up-to-date
        """
        data = self.load_index_data()
        if data is None:
            return True

        meta = data.get('meta', {})
        stored_hashes = meta.get('file_hashes', {})

        # Check if file count matches
        if len(java_files) != len(stored_hashes):
            return True

        # Check if any file has changed
        for file_path in java_files:
            current_hash = self._compute_file_hash(file_path)
            stored_hash = stored_hashes.get(file_path)

            if current_hash != stored_hash:
                return True

        return False

    def get_changed_files(self, java_files: List[str]) -> List[str]:
        """Get list of files that have changed since last index.

        Args:
            java_files: List of Java file paths to check

        Returns:
            List of file paths that have changed or are new
        """
        data = self.load_index_data()
        if data is None:
            return java_files

        meta = data.get('meta', {})
        stored_hashes = meta.get('file_hashes', {})

        changed = []
        for file_path in java_files:
            current_hash = self._compute_file_hash(file_path)
            stored_hash = stored_hashes.get(file_path)

            if current_hash != stored_hash:
                changed.append(file_path)

        return changed

    def _compute_file_hash(self, file_path: str) -> Optional[str]:
        """Compute MD5 hash of file content.

        Args:
            file_path: Path to the file

        Returns:
            MD5 hash string or None if file can't be read
        """
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def clear_index(self) -> bool:
        """Delete all index files.

        Returns:
            True if cleared successfully, False on error
        """
        try:
            for filename in [self.CLASSES_FILE, self.METHODS_FILE, self.CALL_GRAPH_FILE, self.META_FILE]:
                path = os.path.join(self.index_path, filename)
                if os.path.exists(path):
                    os.remove(path)
            return True
        except Exception:
            return False

    def get_index_stats(self) -> Optional[Dict[str, Any]]:
        """Get statistics about the current index.

        Returns:
            Dictionary with index statistics or None if no index exists
        """
        data = self.load_index_data()
        if data is None:
            return None

        meta = data.get('meta', {})
        return {
            'indexed_at': meta.get('indexed_at'),
            'file_count': meta.get('file_count', 0),
            'class_count': meta.get('class_count', 0),
            'method_count': meta.get('method_count', 0),
            'index_path': self.index_path
        }
