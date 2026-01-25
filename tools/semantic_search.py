"""Semantic code search tool for finding relevant code by meaning."""

import os
from typing import Dict, List, Any

from core.tools_registry import register_tool, create_tool_definition
from config import get_project_root, nix_exists
from utils.output import print_tool_start, print_tool_result, is_quiet


def semantic_search(query: str, top_k: int = 3) -> Dict[str, Any]:
    """Search codebase semantically for relevant code.

    Unlike text search (grep), this finds code by meaning.
    Example: "where is tax calculated" finds calculateTax(), computeTaxAmount(), etc.

    Args:
        query: Natural language description of what you're looking for
        top_k: Number of results to return (default 5)

    Returns:
        ToolResult with matching methods and their code
    """
    if not is_quiet():
        print_tool_start("semantic_search")

    if not nix_exists():
        return {"error": "Project not initialized. Run 'nix init' first."}

    # Check if vector store is available
    try:
        from indexer.vector_store import VectorStore
    except ImportError:
        return {"error": "ChromaDB not installed. Run: pip install chromadb"}

    store = VectorStore()

    if not store.is_available():
        return {"error": "ChromaDB not installed. Run: pip install chromadb"}

    if not store.has_index():
        return {
            "error": "Semantic index not built yet.",
            "suggestion": "The project needs to be re-indexed. Run 'nix init' to rebuild the index with semantic search support."
        }

    # Load project context for better understanding
    project_context = None
    try:
        from indexer.project_summarizer import load_project_context
        project_context = load_project_context()
    except Exception:
        pass

    # Perform semantic search
    results = store.search(query, top_k=top_k)

    if not results:
        if not is_quiet():
            print_tool_result("No semantically similar code found")
        return {
            "query": query,
            "matches": [],
            "message": "No semantically similar code found. Try rephrasing your query."
        }

    # Format results with truncated code to avoid token limits
    matches = []
    for r in results:
        # Truncate code to first 10 lines to reduce context size
        code = r.get('code', '')
        code_lines = code.split('\n')[:10]
        if len(code.split('\n')) > 10:
            code_lines.append('    // ... (truncated)')
        truncated_code = '\n'.join(code_lines)

        match = {
            "method": f"{r.get('class_name', 'Unknown')}.{r.get('method_name', 'unknown')}",
            "summary": r.get('summary', ''),
            "relevance": round(r.get('relevance', 0) * 100, 1),
            "file": r.get('file_path', ''),
            "line": r.get('line', 0),
            "annotations": r.get('annotations', []),
            "code": truncated_code
        }
        matches.append(match)

    # Build summary
    summary_lines = [f"Found {len(matches)} relevant methods for: \"{query}\""]

    if not is_quiet():
        print_tool_result(f"Found {len(matches)} relevant methods")
        for m in matches[:3]:
            print_tool_result(f"  {m['method']}: {m['summary'][:50]}...")

    for i, m in enumerate(matches, 1):
        summary_lines.append(f"{i}. {m['method']} ({m['relevance']}% match)")
        summary_lines.append(f"   {m['summary']}")
        summary_lines.append(f"   File: {m['file']}:{m['line']}")

    result = {
        "query": query,
        "match_count": len(matches),
        "matches": matches,
        "summary": '\n'.join(summary_lines)
    }

    # Include project context if available (helps LLM understand the codebase)
    if project_context:
        result["project_context"] = {
            "summary": project_context.get("summary", ""),
            "domains": project_context.get("domains", [])
        }

    return result


def register():
    """Register the semantic search tool."""
    definition = create_tool_definition(
        name="semantic_search",
        description="""Search codebase by MEANING, not just text patterns.

Use this tool when:
- User describes what code DOES, not its name (e.g., "where is tax calculated")
- User mentions an exception or error without knowing the exact location
- Looking for code that handles a specific business concept
- User asks vague questions about functionality

Examples:
- "where does the code calculate order totals" -> finds calculateTotal(), computeOrderAmount()
- "InvocationTargetException" -> finds code using reflection, Method.invoke, Spring proxies
- "user authentication" -> finds login(), authenticate(), validateCredentials()
- "database connection issues" -> finds connection pool code, datasource config

This is DIFFERENT from search_code which does text/regex matching.
Use search_code for: exact strings, class names, variable names, imports
Use semantic_search for: concepts, behaviors, "what does X", error diagnosis""",
        parameters={
            "query": {
                "type": "string",
                "description": "Natural language description of what you're looking for. Can be a concept, behavior, error type, or business functionality."
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default 3, max 5)"
            }
        },
        required=["query"]
    )

    register_tool(
        name="semantic_search",
        handler=semantic_search,
        definition=definition
    )
