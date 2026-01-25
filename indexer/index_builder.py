"""Index builder for creating and maintaining the code index."""

import os
from typing import Dict, List, Optional, Any

from config import get_project_root
from indexer.java_parser import JavaParser
from indexer.index_storage import IndexStorage
from indexer.call_graph import CallGraph
from utils.output import is_quiet


def _is_chromadb_available() -> bool:
    """Check if ChromaDB is installed."""
    try:
        import chromadb
        return True
    except ImportError:
        return False


class IndexBuilder:
    """Build and maintain the code index for a Java project."""

    def __init__(self, project_root: str = None):
        """Initialize the index builder.

        Args:
            project_root: Root of the project. If None, uses current directory.
        """
        self.project_root = project_root or get_project_root()
        self.parser = JavaParser()
        self.storage = IndexStorage(self.project_root)
        self.call_graph = CallGraph()

    def build_index(self, force: bool = False) -> Dict[str, Any]:
        """Build the code index.

        Args:
            force: If True, rebuild even if index is up-to-date

        Returns:
            Dictionary with build results including stats and any errors
        """
        java_files = self._find_java_files()

        if not java_files:
            return {
                'success': True,
                'message': 'No Java files found',
                'stats': {'files': 0, 'classes': 0, 'methods': 0}
            }

        # Check if rebuild is needed and get changed files for incremental update
        changed_files = self.storage.get_changed_files(java_files)

        if not force and not changed_files:
            return {
                'success': True,
                'message': 'Index is up-to-date',
                'stats': self.storage.get_index_stats(),
                'rebuilt': False
            }

        # Parse all Java files
        all_classes = []
        all_methods = []
        all_method_calls = []
        file_hashes = {}
        errors = []

        for file_path in java_files:
            try:
                parsed = self.parser.parse_file(file_path)
                if parsed:
                    all_classes.extend(parsed.get('classes', []))
                    all_methods.extend(parsed.get('methods', []))
                    all_method_calls.extend(parsed.get('method_calls', []))

                    # Compute file hash
                    file_hashes[file_path] = self.storage._compute_file_hash(file_path)
            except Exception as e:
                errors.append({'file': file_path, 'error': str(e)})

        # Build call graph
        call_graph_data = self.call_graph.build_from_methods(all_methods, all_method_calls)

        # Save index
        success = self.storage.save_index_data(
            classes=all_classes,
            methods=all_methods,
            call_graph=call_graph_data,
            file_hashes=file_hashes
        )

        # Build vector index for semantic search (if ChromaDB available)
        vector_stats = None
        if _is_chromadb_available() and all_methods:
            vector_stats = self._build_vector_index(
                all_methods,
                changed_files=changed_files,
                force=force
            )

        result = {
            'success': success,
            'message': 'Index built successfully' if success else 'Failed to save index',
            'rebuilt': True,
            'stats': {
                'files': len(java_files),
                'classes': len(all_classes),
                'methods': len(all_methods),
                'call_edges': len(call_graph_data.get('edges', []))
            },
            'errors': errors if errors else None
        }

        if vector_stats:
            result['stats']['vectors'] = vector_stats.get('indexed', 0)
            result['vector_index'] = vector_stats

        return result

    def get_index(self) -> Optional[Dict[str, Any]]:
        """Get the current index, building if necessary.

        Returns:
            Index data or None if index can't be built/loaded
        """
        java_files = self._find_java_files()

        # Build if stale
        if self.storage.is_index_stale(java_files):
            result = self.build_index()
            if not result.get('success'):
                return None

        return self.storage.load_index_data()

    def get_class(self, class_name: str) -> Optional[Dict[str, Any]]:
        """Find a class by name.

        Args:
            class_name: Simple class name or fully qualified name

        Returns:
            Class information or None if not found
        """
        index = self.get_index()
        if not index:
            return None

        classes = index.get('classes', [])

        for cls in classes:
            if cls.get('name') == class_name or cls.get('fqn') == class_name:
                return cls

        return None

    def get_method(self, method_name: str, class_name: str = None) -> List[Dict[str, Any]]:
        """Find methods by name.

        Args:
            method_name: Method name to search for
            class_name: Optional class name to filter by

        Returns:
            List of matching method information dictionaries
        """
        index = self.get_index()
        if not index:
            return []

        methods = index.get('methods', [])
        results = []

        for method in methods:
            if method.get('name') == method_name:
                if class_name is None or method.get('class_name') == class_name:
                    results.append(method)

        return results

    def get_methods_in_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all methods in a specific file.

        Args:
            file_path: Path to the Java file

        Returns:
            List of method information dictionaries
        """
        index = self.get_index()
        if not index:
            return []

        methods = index.get('methods', [])
        return [m for m in methods if m.get('file_path') == file_path]

    def get_classes_in_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all classes in a specific file.

        Args:
            file_path: Path to the Java file

        Returns:
            List of class information dictionaries
        """
        index = self.get_index()
        if not index:
            return []

        classes = index.get('classes', [])
        return [c for c in classes if c.get('file_path') == file_path]

    def find_method_at_line(self, file_path: str, line: int) -> Optional[Dict[str, Any]]:
        """Find the method containing a specific line.

        Args:
            file_path: Path to the Java file
            line: Line number

        Returns:
            Method information or None if not found
        """
        methods = self.get_methods_in_file(file_path)

        for method in methods:
            start = method.get('start_line', 0)
            end = method.get('end_line', 0)
            if start <= line <= end:
                return method

        return None

    def find_class_at_line(self, file_path: str, line: int) -> Optional[Dict[str, Any]]:
        """Find the class containing a specific line.

        Args:
            file_path: Path to the Java file
            line: Line number

        Returns:
            Class information or None if not found
        """
        classes = self.get_classes_in_file(file_path)

        for cls in classes:
            start = cls.get('start_line', 0)
            end = cls.get('end_line', 0)
            if start <= line <= end:
                return cls

        return None

    def search_by_annotation(self, annotation: str) -> Dict[str, List]:
        """Find classes and methods with a specific annotation.

        Args:
            annotation: Annotation name (with or without @)

        Returns:
            Dictionary with 'classes' and 'methods' lists
        """
        index = self.get_index()
        if not index:
            return {'classes': [], 'methods': []}

        # Normalize annotation name
        if not annotation.startswith('@'):
            annotation = '@' + annotation

        results = {
            'classes': [],
            'methods': []
        }

        # Search classes
        for cls in index.get('classes', []):
            if annotation in cls.get('annotations', []):
                results['classes'].append(cls)

        # Search methods
        for method in index.get('methods', []):
            if annotation in method.get('annotations', []):
                results['methods'].append(method)

        return results

    def get_call_graph(self) -> Dict[str, Any]:
        """Get the call graph from the index.

        Returns:
            Call graph dictionary
        """
        index = self.get_index()
        if not index:
            return {'callers': {}, 'callees': {}, 'edges': []}

        return index.get('call_graph', {'callers': {}, 'callees': {}, 'edges': []})

    def _build_vector_index(self, methods: List[Dict[str, Any]],
                             changed_files: List[str] = None,
                             force: bool = False) -> Dict[str, Any]:
        """Build vector index for semantic search.

        Args:
            methods: List of parsed method dictionaries
            changed_files: List of files that changed (for incremental update)
            force: If True, rebuild entire index

        Returns:
            Dictionary with vector index build stats
        """
        try:
            from indexer.code_summarizer import summarize_methods
            from indexer.vector_store import VectorStore

            store = VectorStore()

            # Determine if we need full rebuild or incremental update
            if force or not store.has_index():
                if not is_quiet():
                    print("  Building semantic search index...")
                methods_to_index = methods
                # Clear for full rebuild
                store.clear()
            elif changed_files:
                if not is_quiet():
                    print(f"  Updating semantic index ({len(changed_files)} files changed)...")
                # Remove old vectors for changed files
                for file_path in changed_files:
                    store.remove_by_file(file_path)
                # Only index methods from changed files
                changed_set = set(changed_files)
                methods_to_index = [m for m in methods if m.get('file_path') in changed_set]
            else:
                # No changes
                return {'indexed': 0, 'skipped': 0, 'error': None, 'incremental': True}

            # Filter to important methods (skip simple getters/setters)
            important_methods = [
                m for m in methods_to_index
                if not self._is_trivial_method(m)
            ]

            skipped_count = len(methods_to_index) - len(important_methods)

            if not important_methods:
                return {'indexed': 0, 'skipped': len(methods_to_index), 'error': None}

            # Generate summaries using LLM
            summarized = summarize_methods(important_methods, show_progress=not is_quiet())

            # Prepare for vector store
            vector_data = []
            for method in summarized:
                # Create unique ID including file and line to avoid duplicates
                file_path = method.get('file_path', '')
                file_name = file_path.split('/')[-1].replace('.java', '') if file_path else 'unknown'
                line = method.get('start_line', 0)
                method_name = method.get('name', 'unknown')
                unique_id = f"{file_name}:{line}:{method_name}"

                vector_data.append({
                    'id': unique_id,
                    'summary': method.get('summary', ''),
                    'code': method.get('code', ''),
                    'file_path': file_path,
                    'line': line,
                    'class_name': method.get('class_name', ''),
                    'method_name': method_name,
                    'annotations': method.get('annotations', [])
                })

            # Store in vector database
            success = store.add_methods(vector_data)

            if success:
                total_count = store.get_count()
                if not is_quiet():
                    print(f"  Indexed {len(vector_data)} methods for semantic search (total: {total_count})")
                return {
                    'indexed': len(vector_data),
                    'skipped': len(methods_to_index) - len(important_methods),
                    'total': total_count,
                    'error': None
                }
            else:
                return {
                    'indexed': 0,
                    'skipped': len(methods),
                    'error': 'Failed to store vectors'
                }

        except Exception as e:
            import traceback
            if not is_quiet():
                print(f"  Warning: Semantic indexing failed: {str(e)}")
            traceback.print_exc()
            return {
                'indexed': 0,
                'skipped': len(methods),
                'error': str(e)
            }

    def _is_trivial_method(self, method: Dict[str, Any]) -> bool:
        """Check if a method is trivial (getter/setter/toString/etc).

        Args:
            method: Method dictionary

        Returns:
            True if method is trivial and should be skipped
        """
        name = method.get('name', '').lower()

        # Skip common trivial methods by exact name
        trivial_names = ['tostring', 'hashcode', 'equals', 'compareto', 'clone']
        if name in trivial_names:
            return True

        # Check getters/setters (but keep complex ones with multiple lines)
        start_line = method.get('start_line', 0)
        end_line = method.get('end_line', 0)
        method_length = end_line - start_line

        # Only filter very simple getters/setters (1-2 lines, just return/assign)
        trivial_prefixes = ['get', 'set']
        for prefix in trivial_prefixes:
            if name.startswith(prefix) and method_length <= 2:
                return True

        # Never filter constructors - they often contain important initialization logic
        # Never filter methods with annotations like @PostMapping, @Transactional, etc.

        return False

    def _find_java_files(self) -> List[str]:
        """Find all Java files in the project.

        Returns:
            List of absolute paths to Java files
        """
        java_files = []

        # Common source directories
        src_dirs = ['src', 'source']

        for src_dir in src_dirs:
            src_path = os.path.join(self.project_root, src_dir)
            if os.path.exists(src_path):
                for root, _, files in os.walk(src_path):
                    # Skip test directories for main index
                    # (we still want to be able to analyze tests though)
                    for file in files:
                        if file.endswith('.java'):
                            java_files.append(os.path.join(root, file))

        # If no src directory, look in project root
        if not java_files:
            for root, _, files in os.walk(self.project_root):
                # Skip common non-source directories
                skip_dirs = ['.git', 'target', 'build', 'out', 'node_modules', '.nix']
                if any(skip in root for skip in skip_dirs):
                    continue
                for file in files:
                    if file.endswith('.java'):
                        java_files.append(os.path.join(root, file))

        return java_files

    def get_stats(self) -> Dict[str, Any]:
        """Get current index statistics.

        Returns:
            Dictionary with index statistics
        """
        stats = self.storage.get_index_stats()
        if stats:
            return stats

        # No index exists yet
        java_files = self._find_java_files()
        return {
            'indexed': False,
            'java_files_found': len(java_files)
        }
