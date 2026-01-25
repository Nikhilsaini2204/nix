"""Comprehensive error diagnostics tool combining RAG, trace analysis, and fix suggestions."""

import re
from typing import Dict, List, Any, Optional

from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def diagnose_error(
    error_message: str = None,
    stack_trace: str = None,
    file_path: str = None,
    line: int = None
) -> Dict[str, Any]:
    """
    Comprehensive error diagnosis combining multiple analysis techniques.

    This tool:
    1. Parses the error/stack trace to identify the problem
    2. Uses semantic search to find related code
    3. Analyzes the call chain to understand context
    4. Provides detailed fix suggestions

    Args:
        error_message: The error message or exception type
        stack_trace: Full stack trace (paste from console)
        file_path: Specific file where error occurred
        line: Specific line number

    Returns:
        Comprehensive diagnosis with:
        - error_type: Type of error identified
        - root_cause: Analysis of what's causing the error
        - related_code: Semantically related code that might be involved
        - fix_suggestions: How to fix the issue
        - affected_components: Components involved in the error
    """
    if not is_quiet():
        print_tool_start("diagnose_error")

    # Need at least one piece of information
    if not any([error_message, stack_trace, file_path]):
        return {
            "error": "Please provide an error message, stack trace, or file location",
            "suggestion": "Paste the full error/stack trace, or describe the error you're seeing"
        }

    result = {
        "error_type": None,
        "root_cause": None,
        "error_location": None,
        "related_code": [],
        "fix_suggestions": [],
        "call_chain": None,
        "project_context": None
    }

    # Load project context
    try:
        from indexer.project_summarizer import load_project_context
        project_context = load_project_context()
        if project_context:
            result["project_context"] = project_context.get("summary", "")
    except Exception:
        pass

    # Combine error_message and stack_trace
    full_error = ""
    if error_message:
        full_error = error_message
    if stack_trace:
        full_error = stack_trace if not full_error else f"{full_error}\n{stack_trace}"

    # Step 1: Parse the error/stack trace
    if not is_quiet():
        print_tool_result("Analyzing error...")

    error_info = _parse_error(full_error, file_path, line)
    result["error_type"] = error_info.get("type")
    result["error_location"] = error_info.get("location")

    # Step 2: Trace the error if we have a stack trace
    if stack_trace or (error_info.get("has_trace")):
        if not is_quiet():
            print_tool_result("Tracing error origin...")
        try:
            from tools.error_tracer import trace_error
            trace_result = trace_error(full_error)
            if trace_result and not trace_result.get("error"):
                result["call_chain"] = trace_result.get("call_chain", [])
                if not result["error_location"]:
                    result["error_location"] = trace_result.get("error_location")
        except Exception:
            pass

    # Step 3: Use semantic search to find related code
    if not is_quiet():
        print_tool_result("Finding related code...")

    search_queries = _build_search_queries(error_info, result.get("error_type"))

    try:
        from indexer.vector_store import VectorStore
        store = VectorStore()

        if store.is_available() and store.has_index():
            all_matches = []
            seen_ids = set()

            for query in search_queries[:2]:  # Use top 2 queries
                matches = store.search(query, top_k=3)
                for m in matches:
                    if m.get('id') not in seen_ids:
                        seen_ids.add(m.get('id'))
                        all_matches.append({
                            "method": f"{m.get('class_name', 'Unknown')}.{m.get('method_name', 'unknown')}",
                            "summary": m.get('summary', ''),
                            "file": m.get('file_path', ''),
                            "line": m.get('line', 0),
                            "relevance": round(m.get('relevance', 0) * 100, 1)
                        })

            result["related_code"] = sorted(all_matches, key=lambda x: x['relevance'], reverse=True)[:5]
    except Exception:
        pass

    # Step 4: Get fix suggestions
    if not is_quiet():
        print_tool_result("Generating fix suggestions...")

    try:
        from tools.fix_suggester import suggest_fix, detect_error_type, get_problem_explanation

        # Get detailed fix
        fix_result = suggest_fix(
            file_path=result.get("error_location", {}).get("file") if isinstance(result.get("error_location"), dict) else file_path,
            line=result.get("error_location", {}).get("line") if isinstance(result.get("error_location"), dict) else line,
            error_message=full_error
        )

        if fix_result and not fix_result.get("error"):
            result["fix_suggestions"].append({
                "type": fix_result.get("error_type"),
                "explanation": fix_result.get("problem_explanation"),
                "suggestion": fix_result.get("fix_suggestion"),
                "code_example": fix_result.get("code_example")
            })

            if not result["error_type"]:
                result["error_type"] = fix_result.get("error_type")
    except Exception:
        pass

    # Step 5: Analyze root cause
    result["root_cause"] = _analyze_root_cause(error_info, result)

    # Build summary
    if not is_quiet():
        print_tool_result("Diagnosis complete")

    result["summary"] = _build_diagnosis_summary(result)

    return result


def _parse_error(error_text: str, file_path: str = None, line: int = None) -> Dict[str, Any]:
    """Parse error text to extract key information."""
    info = {
        "type": None,
        "message": None,
        "location": None,
        "has_trace": False
    }

    if not error_text:
        if file_path:
            info["location"] = {"file": file_path, "line": line}
        return info

    # Check for stack trace
    if "at " in error_text and (".java:" in error_text or "Exception" in error_text):
        info["has_trace"] = True

    # Extract exception type
    exception_patterns = [
        r'([\w.]+Exception)',
        r'([\w.]+Error)',
        r'([\w.]+Failure)',
    ]

    for pattern in exception_patterns:
        match = re.search(pattern, error_text)
        if match:
            info["type"] = match.group(1)
            break

    # Extract error message
    msg_patterns = [
        r'Exception:\s*(.+?)(?:\n|$)',
        r'Error:\s*(.+?)(?:\n|$)',
        r'error:\s*(.+?)(?:\n|$)',
    ]

    for pattern in msg_patterns:
        match = re.search(pattern, error_text, re.IGNORECASE)
        if match:
            info["message"] = match.group(1).strip()
            break

    # Extract location from stack trace
    location_pattern = r'at\s+[\w.$]+\((\w+\.java):(\d+)\)'
    matches = re.findall(location_pattern, error_text)
    if matches:
        # First match is usually the error origin
        info["location"] = {"file": matches[0][0], "line": int(matches[0][1])}

    # Use provided location if none found
    if not info["location"] and file_path:
        info["location"] = {"file": file_path, "line": line}

    return info


def _build_search_queries(error_info: Dict, error_type: str) -> List[str]:
    """Build semantic search queries based on error information."""
    queries = []

    # Query based on exception type
    if error_type:
        type_lower = error_type.lower()

        if "nullpointer" in type_lower:
            queries.append("method that handles null values or optional")
            queries.append("null check validation")
        elif "classnotfound" in type_lower or "nosuchbean" in type_lower:
            queries.append("bean configuration and component scanning")
            queries.append("dependency injection autowired")
        elif "sql" in type_lower or "database" in type_lower or "jdbc" in type_lower:
            queries.append("database query repository method")
            queries.append("transaction management")
        elif "http" in type_lower or "web" in type_lower:
            queries.append("REST endpoint controller method")
            queries.append("request handling and response")
        elif "security" in type_lower or "auth" in type_lower:
            queries.append("authentication and authorization")
            queries.append("security filter access control")
        elif "io" in type_lower or "file" in type_lower:
            queries.append("file handling input output")
        elif "json" in type_lower or "parse" in type_lower:
            queries.append("JSON parsing serialization")
        elif "timeout" in type_lower or "connection" in type_lower:
            queries.append("connection handling timeout")
        else:
            # Generic query based on exception name
            clean_type = error_type.replace("Exception", "").replace("Error", "")
            queries.append(f"handling {clean_type}")

    # Query based on error message
    message = error_info.get("message", "")
    if message:
        # Extract key terms from message
        words = message.split()[:5]
        if words:
            queries.append(" ".join(words))

    # Default fallback
    if not queries:
        queries.append("error handling exception")

    return queries


def _analyze_root_cause(error_info: Dict, result: Dict) -> str:
    """Analyze and explain the root cause of the error."""
    error_type = result.get("error_type") or error_info.get("type") or "Unknown"

    # Common root cause explanations
    causes = {
        "NullPointerException": "A variable or object reference is null when a method or field is accessed. This often happens when an object is not initialized or a method returns null unexpectedly.",
        "ClassNotFoundException": "A class is referenced but cannot be found in the classpath. This usually means a dependency is missing or the class name is misspelled.",
        "NoSuchBeanDefinitionException": "Spring cannot find a bean that is required for dependency injection. Check that the class is annotated with @Service, @Component, etc., and is in a scanned package.",
        "SQLException": "A database operation failed. This could be due to connection issues, invalid SQL, or constraint violations.",
        "HttpMessageNotReadableException": "The request body could not be parsed. Check that the JSON format matches the expected DTO structure.",
        "MethodArgumentNotValidException": "Request validation failed. Check @Valid annotations and validation constraints on the DTO.",
        "AccessDeniedException": "The user does not have permission for this operation. Check security configuration and roles.",
        "DataIntegrityViolationException": "A database constraint was violated, such as a unique key or foreign key constraint.",
        "LazyInitializationException": "A Hibernate lazy-loaded collection was accessed outside of a transaction. Use @Transactional or fetch eagerly.",
        "CircularDependencyException": "Two or more beans depend on each other creating a cycle. Use @Lazy or restructure dependencies.",
    }

    for exc_type, cause in causes.items():
        if exc_type.lower() in error_type.lower():
            return cause

    # Generic cause based on error type
    if error_info.get("message"):
        return f"Error occurred: {error_info['message']}"

    return "Unable to determine specific root cause. Check the stack trace for more details."


def _build_diagnosis_summary(result: Dict) -> str:
    """Build a comprehensive summary of the diagnosis."""
    parts = []

    # Error type
    if result.get("error_type"):
        parts.append(f"ERROR: {result['error_type']}")

    # Location
    loc = result.get("error_location")
    if loc:
        if isinstance(loc, dict):
            parts.append(f"LOCATION: {loc.get('file', 'unknown')}:{loc.get('line', '?')}")
        else:
            parts.append(f"LOCATION: {loc}")

    # Root cause
    if result.get("root_cause"):
        parts.append(f"CAUSE: {result['root_cause'][:200]}")

    # Related code
    if result.get("related_code"):
        methods = [r['method'] for r in result['related_code'][:3]]
        parts.append(f"RELATED: {', '.join(methods)}")

    # Fix suggestion
    if result.get("fix_suggestions"):
        fix = result['fix_suggestions'][0]
        if fix.get("suggestion"):
            suggestion = fix['suggestion'][:150]
            parts.append(f"FIX: {suggestion}")

    return " | ".join(parts) if parts else "Could not generate diagnosis summary"


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="diagnose_error",
    description="""Comprehensive error diagnosis tool. Use when user:
- Pastes a stack trace or error message
- Says "help me debug this", "why is this failing", "what's causing this error"
- Describes an exception (NPE, ClassNotFound, etc.)
- Wants to understand and fix an error

This combines error tracing, semantic code search, and fix suggestions to provide a complete diagnosis.""",
    parameters={
        "error_message": {
            "type": "string",
            "description": "The error message or exception (e.g., 'NullPointerException in UserService')"
        },
        "stack_trace": {
            "type": "string",
            "description": "Full stack trace from the error (paste from console)"
        },
        "file_path": {
            "type": "string",
            "description": "Specific file where error occurred"
        },
        "line": {
            "type": "integer",
            "description": "Line number of the error"
        }
    }
)


def register():
    """Register this tool with the registry."""
    register_tool("diagnose_error", diagnose_error, TOOL_DEFINITION)
