"""Code search tool for finding patterns in source code."""

import os
import re
from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def search_code(pattern, file_pattern=None, include_context=True, max_results=50):
    """
    Search for a pattern in source code files.

    Args:
        pattern: Regex pattern or plain text to search for
        file_pattern: File extension filter (e.g., "*.java", "*.xml")
        include_context: Whether to include surrounding lines
        max_results: Maximum number of results to return

    Returns:
        dict with matching files and lines
    """
    if not is_quiet():
        print_tool_start("search_code")

    project_root = os.getcwd()

    # Find files to search
    files = find_searchable_files(project_root, file_pattern)

    if not files:
        if not is_quiet():
            print_tool_result("No matching files found")
        return {
            "error": "No files found to search",
            "suggestion": f"Try a different file pattern. Current: {file_pattern or 'all source files'}"
        }

    results = []
    files_with_matches = set()

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        # If not valid regex, escape and search as literal
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    for file_path in files:
        file_matches = search_in_file(file_path, regex, include_context, project_root)
        if file_matches:
            files_with_matches.add(file_path)
            results.extend(file_matches)

            if len(results) >= max_results:
                break

    # Trim to max results
    results = results[:max_results]

    if not is_quiet():
        print_tool_result(f"{len(results)} matches in {len(files_with_matches)} files")
        # Show details of matches
        for r in results[:5]:  # Show first 5
            print_tool_result(f"  {r.get('file')}:{r.get('line_number')} - {r.get('line', '').strip()[:60]}")
        if len(results) > 5:
            print_tool_result(f"  ... and {len(results) - 5} more")

    return {
        "summary": f"Found {len(results)} matches in {len(files_with_matches)} files",
        "pattern": pattern,
        "match_count": len(results),
        "file_count": len(files_with_matches),
        "results": results,
        "truncated": len(results) >= max_results
    }


def find_searchable_files(project_root, file_pattern=None):
    """Find all searchable source files."""
    files = []

    skip_dirs = {
        '.git', '.nix', 'target', 'build', 'node_modules',
        '.idea', '__pycache__', '.gradle', 'bin', 'out'
    }

    # Default to common source file extensions
    if file_pattern:
        if file_pattern.startswith("*."):
            extensions = [file_pattern[1:]]  # "*.java" -> ".java"
        else:
            extensions = [file_pattern]
    else:
        extensions = ['.java', '.xml', '.properties', '.yml', '.yaml', '.json', '.kt', '.gradle']

    for root, dirs, filenames in os.walk(project_root):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

        for filename in filenames:
            # Check extension
            if any(filename.endswith(ext) for ext in extensions):
                files.append(os.path.join(root, filename))

    return files


def search_in_file(file_path, regex, include_context, project_root):
    """Search for pattern in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        return []

    matches = []
    rel_path = os.path.relpath(file_path, project_root)

    for i, line in enumerate(lines):
        if regex.search(line):
            match_info = {
                "file": rel_path,
                "line_number": i + 1,
                "line": line.rstrip(),
            }

            if include_context:
                # Add context (2 lines before and after)
                context_before = []
                context_after = []

                for j in range(max(0, i - 2), i):
                    context_before.append({
                        "line_number": j + 1,
                        "line": lines[j].rstrip()
                    })

                for j in range(i + 1, min(len(lines), i + 3)):
                    context_after.append({
                        "line_number": j + 1,
                        "line": lines[j].rstrip()
                    })

                match_info["context_before"] = context_before
                match_info["context_after"] = context_after

            matches.append(match_info)

    return matches


def find_usages(symbol, file_pattern=None):
    """
    Find all usages of a symbol (class, method, variable).

    Args:
        symbol: The symbol name to find usages of
        file_pattern: Optional file filter

    Returns:
        dict with all usages
    """
    if not is_quiet():
        print_tool_start("find_usages")

    # Build search pattern - handle special chars like @ that aren't word chars
    escaped = re.escape(symbol)
    if symbol and (symbol[0].isalnum() or symbol[0] == '_'):
        pattern = rf'\b{escaped}\b'
    else:
        # For symbols starting with @ or other special chars, don't use word boundary at start
        pattern = rf'{escaped}\b' if symbol and symbol[-1].isalnum() else escaped

    # Search for the symbol (suppress search_code's output since we're wrapping it)
    from utils.output import set_quiet_mode
    was_quiet = is_quiet()
    set_quiet_mode(True)
    result = search_code(
        pattern=pattern,
        file_pattern=file_pattern,
        include_context=True
    )
    set_quiet_mode(was_quiet)

    if result.get("error"):
        return result

    # Categorize usages
    usages = {
        "declarations": [],
        "references": [],
        "imports": []
    }

    for match in result.get("results", []):
        line = match.get("line", "")

        if "import " in line:
            usages["imports"].append(match)
        elif f"class {symbol}" in line or f"interface {symbol}" in line:
            usages["declarations"].append(match)
        elif f"{symbol} " in line and ("=" in line or "(" in line):
            usages["declarations"].append(match)
        else:
            usages["references"].append(match)

    if not is_quiet():
        total = len(result.get('results', []))
        print_tool_result(f"{total} usages of '{symbol}'")
        # Show breakdown
        if usages["declarations"]:
            print_tool_result(f"  Declarations: {len(usages['declarations'])}")
        if usages["references"]:
            print_tool_result(f"  References: {len(usages['references'])}")
        if usages["imports"]:
            print_tool_result(f"  Imports: {len(usages['imports'])}")
        # Show first few matches
        for r in result.get('results', [])[:3]:
            print_tool_result(f"  {r.get('file')}:{r.get('line_number')}")

    return {
        "summary": f"Found {len(result.get('results', []))} usages of '{symbol}'",
        "symbol": symbol,
        "total_usages": len(result.get("results", [])),
        "declarations": len(usages["declarations"]),
        "references": len(usages["references"]),
        "imports": len(usages["imports"]),
        "usages": usages
    }


# Tool definitions
SEARCH_CODE_DEFINITION = create_tool_definition(
    name="search_code",
    description="Search for a pattern or text in source code files. Supports regex. Use this to find specific code patterns, method calls, annotations, etc.",
    parameters={
        "pattern": {
            "type": "string",
            "description": "Pattern to search for (text or regex)"
        },
        "file_pattern": {
            "type": "string",
            "description": "File filter (e.g., '*.java', '*.xml'). Default: all source files"
        }
    },
    required=["pattern"]
)

FIND_USAGES_DEFINITION = create_tool_definition(
    name="find_usages",
    description="Find all usages of a symbol (class, method, variable) in the codebase. Categorizes into declarations, references, and imports.",
    parameters={
        "symbol": {
            "type": "string",
            "description": "The symbol name to find usages of"
        },
        "file_pattern": {
            "type": "string",
            "description": "Optional file filter (e.g., '*.java')"
        }
    },
    required=["symbol"]
)


def register():
    """Register search tools with the registry."""
    register_tool("search_code", search_code, SEARCH_CODE_DEFINITION)
    register_tool("find_usages", find_usages, FIND_USAGES_DEFINITION)
