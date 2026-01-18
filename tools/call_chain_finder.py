"""Call chain finder tool for tracing method calls."""

import os
from typing import Dict, List, Any, Optional

from core.tools_registry import register_tool, create_tool_definition
from utils.output import (
    print_tool_start, print_tool_result, is_quiet,
    print_code_snippet, bold, error, warn, success, muted, highlight, Colors
)


def find_call_chain(method_name: str, class_name: str = None,
                    direction: str = "both", max_depth: int = 5) -> Dict[str, Any]:
    """
    Find the call chain for a method - who calls it and what it calls.

    Traces the full call flow: Controller -> Service -> Repository

    Args:
        method_name: Name of the method to trace
        class_name: Optional class name to narrow search
        direction: "upstream" (callers), "downstream" (callees), or "both"
        max_depth: Maximum depth to trace (default 5)

    Returns:
        dict with call chains, method info, and code snippets
    """
    if not is_quiet():
        print_tool_start("find_call_chain")

    try:
        from indexer import IndexBuilder, CallGraph
    except ImportError:
        return {
            "error": "Indexer not available",
            "suggestion": "Make sure the indexer package is properly installed"
        }

    # Build/load index
    builder = IndexBuilder()
    index = builder.get_index()

    if not index:
        # Try to build the index
        build_result = builder.build_index()
        if not build_result.get('success'):
            return {
                "error": "Could not build code index",
                "details": build_result.get('message'),
                "suggestion": "Make sure the project has Java source files"
            }
        index = builder.get_index()

    if not index:
        return {
            "error": "No index available",
            "suggestion": "Run 'nix \"find issues\"' to build the index first"
        }

    # Find the method
    methods = builder.get_method(method_name, class_name)

    if not methods:
        # Try fuzzy search
        all_methods = index.get('methods', [])
        methods = [m for m in all_methods if method_name.lower() in m.get('name', '').lower()]

        if not methods:
            return {
                "error": f"Method '{method_name}' not found in index",
                "suggestion": f"Check the method name or run full analysis to rebuild index"
            }

    result = {
        "method_name": method_name,
        "matches": len(methods),
        "chains": [],
        "locations": []
    }

    # Load call graph
    call_graph = CallGraph.from_dict(index.get('call_graph', {}))

    for method in methods:
        method_fqn = method.get('fqn', '')
        method_info = {
            "fqn": method_fqn,
            "class": method.get('class_name'),
            "file": method.get('file_path'),
            "line": method.get('start_line'),
            "annotations": method.get('annotations', [])
        }

        # Get code snippet
        if method.get('file_path') and method.get('start_line'):
            method_info["snippet"] = get_code_snippet(
                method['file_path'],
                method['start_line']
            )

        chain_info = {
            "method": method_info,
            "upstream": [],
            "downstream": []
        }

        # Trace upstream (callers)
        if direction in ["upstream", "both"]:
            upstream_chains = call_graph.trace_upstream(method_fqn, max_depth)
            for chain in upstream_chains:
                chain_with_info = []
                for fqn in reversed(chain):  # Reverse to show entry -> target
                    method_detail = get_method_detail(builder, fqn)
                    chain_with_info.append(method_detail)
                chain_info["upstream"].append(chain_with_info)

        # Trace downstream (callees)
        if direction in ["downstream", "both"]:
            downstream_chains = call_graph.trace_downstream(method_fqn, max_depth)
            for chain in downstream_chains:
                chain_with_info = []
                for fqn in chain:
                    method_detail = get_method_detail(builder, fqn)
                    chain_with_info.append(method_detail)
                chain_info["downstream"].append(chain_with_info)

        result["chains"].append(chain_info)

        # Add to locations
        if method.get('file_path'):
            result["locations"].append({
                "file": method['file_path'],
                "line": method.get('start_line'),
                "method": method_fqn
            })

    # Format summary
    total_callers = sum(len(c.get("upstream", [])) for c in result["chains"])
    total_callees = sum(len(c.get("downstream", [])) for c in result["chains"])

    result["summary"] = f"Found {len(methods)} method(s) matching '{method_name}'. Traced {total_callers} upstream chain(s) and {total_callees} downstream chain(s)."

    if not is_quiet():
        print_tool_result(result["summary"])

        # Print colored call chains
        for chain_info in result["chains"][:3]:  # Show first 3 matches
            method_info = chain_info.get("method", {})
            print(f"\n{highlight('Method:')} {bold(method_info.get('fqn', 'unknown'))}")

            # Print location with snippet
            file_path = method_info.get('file')
            line = method_info.get('line')
            if file_path and line and os.path.exists(file_path):
                print_code_snippet(file_path, line, context=2)

            # Print upstream (callers)
            upstream = chain_info.get("upstream", [])
            if upstream:
                print(f"\n  {warn('Upstream (who calls this):')}")
                for i, chain in enumerate(upstream[:3], 1):
                    chain_str = format_call_chain(chain)
                    print(f"    {muted(f'{i}.')} {chain_str}")

            # Print downstream (callees)
            downstream = chain_info.get("downstream", [])
            if downstream:
                print(f"\n  {success('Downstream (what this calls):')}")
                for i, chain in enumerate(downstream[:3], 1):
                    chain_str = format_call_chain(chain)
                    print(f"    {muted(f'{i}.')} {chain_str}")

    return result


def get_method_detail(builder, method_fqn: str) -> Dict[str, Any]:
    """Get detailed information about a method by FQN.

    Args:
        builder: IndexBuilder instance
        method_fqn: Fully qualified method name

    Returns:
        Method detail dictionary
    """
    # Parse FQN to get method name
    parts = method_fqn.rsplit('.', 1)
    if len(parts) == 2:
        class_fqn, method_name = parts
        class_name = class_fqn.rsplit('.', 1)[-1] if '.' in class_fqn else class_fqn

        methods = builder.get_method(method_name, class_name)
        if methods:
            method = methods[0]
            return {
                "fqn": method_fqn,
                "class": method.get('class_name'),
                "method": method.get('name'),
                "file": method.get('file_path'),
                "line": method.get('start_line'),
                "annotations": method.get('annotations', [])
            }

    # Return basic info if method not found in index
    return {
        "fqn": method_fqn,
        "resolved": False
    }


def get_code_snippet(file_path: str, line: int, context: int = 2) -> Optional[str]:
    """Get a code snippet around a specific line.

    Args:
        file_path: Path to the file
        line: Line number (1-indexed)
        context: Number of lines before/after

    Returns:
        Code snippet string or None if file can't be read
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        start = max(0, line - context - 1)
        end = min(len(lines), line + context)

        snippet_lines = []
        for i in range(start, end):
            prefix = ">>> " if i == line - 1 else "    "
            snippet_lines.append(f"{prefix}{i + 1}: {lines[i].rstrip()}")

        return '\n'.join(snippet_lines)

    except Exception:
        return None


def format_call_chain(chain: List[Dict]) -> str:
    """Format a call chain for display with colors.

    Args:
        chain: List of method details

    Returns:
        Formatted string representation with colors
    """
    if not chain:
        return muted("(empty chain)")

    parts = []
    for method in chain:
        if method.get('resolved', True):
            class_name = method.get('class', '?')
            method_name = method.get('method', '?')
            line = method.get('line', '?')
            parts.append(f"{highlight(class_name)}.{bold(method_name)}:{warn(str(line))}")
        else:
            parts.append(muted(method.get('fqn', '?')))

    return f" {muted('->')} ".join(parts)


def get_entry_points_for_method(method_fqn: str, builder, call_graph) -> List[Dict]:
    """Find entry points (controllers, listeners) that lead to a method.

    Args:
        method_fqn: Target method FQN
        builder: IndexBuilder instance
        call_graph: CallGraph instance

    Returns:
        List of entry point method details
    """
    index = builder.get_index()
    if not index:
        return []

    methods = index.get('methods', [])
    entry_points = call_graph.get_entry_points(methods)

    # Filter to entry points that can reach our target method
    reachable_entries = []
    for entry_fqn in entry_points:
        path = call_graph.find_path(entry_fqn, method_fqn)
        if path:
            entry_detail = get_method_detail(builder, entry_fqn)
            entry_detail['path_to_target'] = path
            reachable_entries.append(entry_detail)

    return reachable_entries


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="find_call_chain",
    description="Trace the full call flow for a method. Shows who calls this method (upstream) and what it calls (downstream). Useful for understanding code flow: Controller -> Service -> Repository.",
    parameters={
        "method_name": {
            "type": "string",
            "description": "Name of the method to trace (required)"
        },
        "class_name": {
            "type": "string",
            "description": "Optional class name to narrow the search"
        },
        "direction": {
            "type": "string",
            "description": "Direction: 'upstream' (callers), 'downstream' (callees), or 'both' (default)"
        },
        "max_depth": {
            "type": "integer",
            "description": "Maximum depth to trace (default 5)"
        }
    }
)


def register():
    """Register this tool with the registry."""
    register_tool("find_call_chain", find_call_chain, TOOL_DEFINITION)
