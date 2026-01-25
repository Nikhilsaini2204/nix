"""Smart tool selector - only sends relevant tools to LLM to save tokens."""

import re
from typing import List, Dict, Any

# Core tools that are always available (minimal set)
CORE_TOOLS = [
    "full_analysis",
    "smart_query",
    "semantic_search",
    "search_code",
    "read_file",
    "find_issues",      # Always available - most common use case
    "diagnose_error",   # Always available - for pasted errors/exceptions
]

# Tool groups for different query types
TOOL_GROUPS = {
    "project_overview": ["full_analysis", "smart_query"],
    "code_search": ["search_code", "semantic_search", "find_usages"],
    "analysis": ["analyze_code_structure", "analyze_dependencies", "analyze_endpoints", "analyze_beans", "analyze_entities"],
    "issues": ["find_issues", "diagnose_error", "check_null_safety", "check_bean_wiring", "build_project"],
    "files": ["read_file", "list_files", "explore_project", "describe_file"],
    "errors": ["diagnose_error", "suggest_fix"],  # Use diagnose_error for all errors (not trace_error)
    "dependencies": ["smart_query", "analyze_dependencies"],
    "configuration": ["smart_query", "analyze_configuration"],
}

# Phrase patterns that take priority (checked first, more specific)
PHRASE_PATTERNS = {
    # Issue finding - MUST come before generic "find"
    "find issues": "issues",
    "find problems": "issues",
    "find bugs": "issues",
    "check issues": "issues",
    "check problems": "issues",
    "any issues": "issues",
    "any problems": "issues",
    "any bugs": "issues",
    "what's wrong": "issues",
    "whats wrong": "issues",

    # Usage finding
    "find usages": "code_search",
    "find usage": "code_search",
    "where is": "code_search",
    "where does": "code_search",
    "usages of": "code_search",

    # Full analysis
    "analyze everything": "project_overview",
    "full analysis": "project_overview",
    "what is this project": "project_overview",
    "what does this project": "project_overview",
    "tell me about": "project_overview",
}

# Keywords that map to tool groups (checked after phrase patterns)
KEYWORD_MAPPING = {
    # Project overview
    "what is": "project_overview",
    "what does": "project_overview",
    "about": "project_overview",
    "overview": "project_overview",
    "project": "project_overview",

    # Code search (generic - phrase patterns handle specific cases)
    "search": "code_search",
    "locate": "code_search",

    # Issues (generic)
    "issue": "issues",
    "problem": "issues",
    "bug": "issues",

    # Errors (pasted errors, stack traces)
    "error": "errors",
    "exception": "errors",
    "fix": "errors",
    "debug": "errors",
    "failing": "errors",
    "broken": "errors",
    "npe": "errors",
    "nullpointer": "errors",

    # Files
    "file": "files",
    "read": "files",
    "structure": "files",

    # Analysis
    "analyze": "analysis",
    "endpoint": "analysis",
    "api": "analysis",
    "bean": "analysis",
    "entity": "analysis",
    "service": "project_overview",
    "controller": "project_overview",

    # Dependencies
    "dependency": "dependencies",
    "dependencies": "dependencies",
    "library": "dependencies",
    "libraries": "dependencies",
    "version": "dependencies",

    # Configuration
    "config": "configuration",
    "configuration": "configuration",
    "property": "configuration",
    "properties": "configuration",
    "setting": "configuration",
    "settings": "configuration",
    "profile": "configuration",
}


def detect_error_pattern(query: str) -> bool:
    """
    Detect if the query contains an error, exception, or stack trace.

    Patterns detected:
    - File paths with line numbers: /path/to/File.java:19:5
    - Stack traces: at com.example.Class.method(File.java:123)
    - Java errors: java: missing return statement
    - Exception names: NullPointerException, IllegalArgumentException, etc.
    - Error keywords in context
    """
    # File path with line number pattern
    if re.search(r'[/\\][\w/\\]+\.java:\d+', query):
        return True

    # Stack trace pattern
    if re.search(r'at\s+[\w.]+\([\w.]+:\d+\)', query):
        return True

    # Java compiler error pattern
    if re.search(r'java:\s*\w+', query):
        return True

    # Common exception names
    exception_patterns = [
        r'\w+Exception',
        r'\w+Error',
        r'NullPointer',
        r'IllegalArgument',
        r'ClassNotFound',
        r'NoSuchMethod',
        r'ArrayIndexOutOfBounds',
        r'NumberFormat',
        r'FileNotFound',
        r'IOException',
        r'SQLException',
        r'RuntimeException',
    ]
    for pattern in exception_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return True

    # Maven/Gradle error patterns
    if re.search(r'\[ERROR\]|\[FAILURE\]|BUILD FAILED|Compilation failure', query, re.IGNORECASE):
        return True

    return False


def _filter_tools_by_groups(all_tools: List[Dict], groups: set) -> List[Dict]:
    """
    Filter tools by relevant groups.

    Args:
        all_tools: Full list of tool definitions
        groups: Set of group names to include

    Returns:
        Filtered list of tool definitions
    """
    # Collect tool names from relevant groups
    relevant_tool_names = set(CORE_TOOLS)
    for group in groups:
        relevant_tool_names.update(TOOL_GROUPS.get(group, []))

    # Filter tools
    filtered_tools = [
        tool for tool in all_tools
        if tool.get("function", {}).get("name") in relevant_tool_names
    ]

    # If we have too few tools, add some core ones
    if len(filtered_tools) < 3:
        for tool in all_tools:
            if tool.get("function", {}).get("name") in CORE_TOOLS:
                if tool not in filtered_tools:
                    filtered_tools.append(tool)

    # Limit to max 8 tools to stay under token limit
    return filtered_tools[:8]


def select_tools_for_query(query: str, all_tools: List[Dict]) -> List[Dict]:
    """
    Select only relevant tools based on user query to save tokens.

    Args:
        query: User's question/command
        all_tools: Full list of tool definitions

    Returns:
        Filtered list of relevant tool definitions
    """
    query_lower = query.lower()

    # Determine which tool groups are relevant
    relevant_groups = set()

    # PRIORITY 1: Check for error/exception patterns (highest priority)
    if detect_error_pattern(query):
        relevant_groups.add("errors")
        # For pasted errors, only return error-related tools
        return _filter_tools_by_groups(all_tools, relevant_groups)

    # PRIORITY 2: Check phrase patterns (more specific, checked first)
    for phrase, group in PHRASE_PATTERNS.items():
        if phrase in query_lower:
            relevant_groups.add(group)
            # For specific phrases, return immediately with just that group
            return _filter_tools_by_groups(all_tools, relevant_groups)

    # PRIORITY 3: Check keyword mappings (if no phrase matched)
    for keyword, group in KEYWORD_MAPPING.items():
        if keyword in query_lower:
            relevant_groups.add(group)

    # If no specific match, use core tools only
    if not relevant_groups:
        relevant_groups.add("project_overview")

    return _filter_tools_by_groups(all_tools, relevant_groups)


def get_minimal_tool_definitions(tools: List[Dict]) -> List[Dict]:
    """
    Create minimal tool definitions with shorter descriptions to save tokens.

    Args:
        tools: Original tool definitions

    Returns:
        Tools with shortened descriptions
    """
    minimal_tools = []

    for tool in tools:
        func = tool.get("function", {})
        name = func.get("name", "")

        # Shortened descriptions for common tools
        short_descriptions = {
            "full_analysis": "Get complete project overview and understanding",
            "smart_query": "Answer questions about dependencies, config, services, endpoints",
            "semantic_search": "Find code by meaning/concept",
            "search_code": "Find exact text/pattern in code",
            "find_issues": "Find potential issues in codebase",
            "diagnose_error": "Diagnose and fix errors/exceptions",
            "read_file": "Read file contents",
            "analyze_dependencies": "Analyze project dependencies",
            "analyze_configuration": "Analyze configuration and properties",
            "analyze_endpoints": "Find REST endpoints",
            "suggest_fix": "Suggest fix for an error",
            "trace_error": "Trace error from stack trace",
            "build_project": "Build/compile the project",
            "check_null_safety": "Find potential null pointer issues",
            "check_bean_wiring": "Check Spring bean wiring",
        }

        minimal_tool = {
            "type": "function",
            "function": {
                "name": name,
                "description": short_descriptions.get(name, func.get("description", "")[:100]),
                "parameters": func.get("parameters", {"type": "object", "properties": {}})
            }
        }

        minimal_tools.append(minimal_tool)

    return minimal_tools
