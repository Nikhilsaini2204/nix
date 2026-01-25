"""Indexer package for Java code parsing and indexing."""

from indexer.java_parser import JavaParser
from indexer.index_storage import IndexStorage
from indexer.index_builder import IndexBuilder
from indexer.call_graph import CallGraph
from indexer.project_summarizer import (
    generate_project_summary,
    save_project_context,
    load_project_context,
    get_project_summary
)
from indexer.context_builder import ContextBuilder

# Optional imports (require chromadb)
try:
    from indexer.vector_store import VectorStore
    from indexer.code_summarizer import summarize_methods
    __all__ = [
        'JavaParser', 'IndexStorage', 'IndexBuilder', 'CallGraph',
        'VectorStore', 'summarize_methods',
        'generate_project_summary', 'save_project_context', 'load_project_context', 'get_project_summary'
    ]
except ImportError:
    __all__ = [
        'JavaParser', 'IndexStorage', 'IndexBuilder', 'CallGraph',
        'generate_project_summary', 'save_project_context', 'load_project_context', 'get_project_summary'
    ]
