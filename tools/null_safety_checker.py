"""Null safety checker tool for detecting potential NullPointerException spots."""

import os
import re
from typing import Dict, List, Any, Optional

from core.tools_registry import register_tool, create_tool_definition
from utils.output import (
    print_tool_start, print_tool_result, is_quiet,
    print_issues_summary, format_issue_with_snippet,
    bold, error, warn, success, muted, highlight
)


def check_null_safety(file_path: str = None, limit: int = 20) -> Dict[str, Any]:
    """
    Find potential NullPointerException spots in the codebase.

    Detects:
    - .get() without .isPresent() or .orElse()
    - Method calls on potentially null returns
    - Missing null checks on method parameters
    - Nullable annotations without null handling

    Args:
        file_path: Optional specific file to check. If None, checks all Java files.
        limit: Maximum number of issues to return

    Returns:
        dict with found issues, their locations, and suggestions
    """
    if not is_quiet():
        print_tool_start("check_null_safety")

    project_root = os.getcwd()
    issues = []

    if file_path:
        if os.path.exists(file_path):
            file_issues = analyze_file_for_null_issues(file_path)
            issues.extend(file_issues)
        else:
            return {
                "error": f"File not found: {file_path}",
                "issues": []
            }
    else:
        # Find all Java files
        java_files = find_java_files(project_root)
        for java_file in java_files:
            file_issues = analyze_file_for_null_issues(java_file)
            issues.extend(file_issues)
            if len(issues) >= limit * 2:  # Get extra for prioritization
                break

    # Prioritize issues
    issues = prioritize_issues(issues)

    # Limit results
    if len(issues) > limit:
        issues = issues[:limit]

    result = {
        "total_issues": len(issues),
        "issues": issues,
        "summary": f"Found {len(issues)} potential null safety issues"
    }

    if not is_quiet():
        print_tool_result(result["summary"])
        # Print colored issues with snippets
        if issues:
            print_issues_summary(issues[:10], "Null Safety Issues")

    return result


def find_java_files(project_root: str) -> List[str]:
    """Find all Java files in the project."""
    java_files = []
    src_dirs = ["src/main/java", "src"]

    for src_dir in src_dirs:
        src_path = os.path.join(project_root, src_dir)
        if os.path.exists(src_path):
            for root, _, files in os.walk(src_path):
                # Skip test directories for main analysis
                if 'test' in root.lower():
                    continue
                for file in files:
                    if file.endswith('.java'):
                        java_files.append(os.path.join(root, file))

    return java_files


def analyze_file_for_null_issues(file_path: str) -> List[Dict[str, Any]]:
    """Analyze a single Java file for null safety issues.

    Args:
        file_path: Path to the Java file

    Returns:
        List of issue dictionaries
    """
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception:
        return issues

    # Pattern 1: .get() without null handling
    # e.g., user.get().getName() - dangerous if Optional
    get_pattern = r'\.get\(\)\.'
    for i, line in enumerate(lines, 1):
        if re.search(get_pattern, line):
            # Check if there's isPresent/orElse nearby
            context_start = max(0, i - 3)
            context = '\n'.join(lines[context_start:i])
            if not re.search(r'\.isPresent\(\)|\.orElse|\.ifPresent|\.orElseThrow', context):
                issues.append({
                    "file": file_path,
                    "line": i,
                    "issue": "Optional.get() without null check",
                    "severity": "high",
                    "pattern": "optional_get_unchecked",
                    "snippet": get_snippet(lines, i),
                    "suggestion": "Use .orElse(), .orElseThrow(), or check with .isPresent() first"
                })

    # Pattern 2: Method chaining on potentially null result
    # e.g., repository.findById(id).getName() - findById might return null
    chain_pattern = r'\.(find\w+|get\w+)\([^)]*\)\.\w+'
    for i, line in enumerate(lines, 1):
        if re.search(chain_pattern, line):
            # Check if it's not an Optional return
            if not re.search(r'\.orElse|\.isPresent|\.ifPresent', line):
                match = re.search(r'\.(find\w+|get\w+)\([^)]*\)\.(\w+)', line)
                if match:
                    method = match.group(1)
                    issues.append({
                        "file": file_path,
                        "line": i,
                        "issue": f"Method chaining after {method}() - may be null",
                        "severity": "medium",
                        "pattern": "chain_on_nullable",
                        "snippet": get_snippet(lines, i),
                        "suggestion": "Add null check or use Optional"
                    })

    # Pattern 3: @Nullable parameter without null check
    nullable_pattern = r'@Nullable\s+\w+\s+(\w+)'
    for i, line in enumerate(lines, 1):
        match = re.search(nullable_pattern, line)
        if match:
            param_name = match.group(1)
            # Check if parameter is used without null check in next 10 lines
            method_body = '\n'.join(lines[i:min(i + 10, len(lines))])
            if param_name in method_body:
                if not re.search(rf'{param_name}\s*!=\s*null|{param_name}\s*==\s*null|Objects\.requireNonNull\({param_name}', method_body):
                    issues.append({
                        "file": file_path,
                        "line": i,
                        "issue": f"@Nullable parameter '{param_name}' used without null check",
                        "severity": "medium",
                        "pattern": "nullable_param_unchecked",
                        "snippet": get_snippet(lines, i),
                        "suggestion": f"Add null check for {param_name} before use"
                    })

    # Pattern 4: Return value of potentially null method assigned and used
    # e.g., User user = getUser(); user.getName();
    for i, line in enumerate(lines, 1):
        # Look for assignment from getter/finder
        assign_match = re.search(r'(\w+)\s+(\w+)\s*=\s*\w+\.(find\w+|get\w+)\([^)]*\);', line)
        if assign_match:
            type_name = assign_match.group(1)
            var_name = assign_match.group(2)
            method = assign_match.group(3)

            # Skip if Optional type
            if 'Optional' in type_name:
                continue

            # Check next few lines for use without null check
            for j in range(i, min(i + 5, len(lines))):
                next_line = lines[j]
                if re.search(rf'{var_name}\.', next_line):
                    # Check for null check
                    context = '\n'.join(lines[i:j + 1])
                    if not re.search(rf'{var_name}\s*!=\s*null|{var_name}\s*==\s*null|if\s*\(\s*{var_name}', context):
                        issues.append({
                            "file": file_path,
                            "line": j + 1,
                            "issue": f"'{var_name}' from {method}() used without null check",
                            "severity": "high",
                            "pattern": "use_without_null_check",
                            "snippet": get_snippet(lines, j + 1),
                            "suggestion": f"Add null check for {var_name} or use Optional"
                        })
                        break

    # Pattern 5: Stream operations that may hide NPE
    # e.g., list.stream().map(x -> x.getName()) - x might be null
    stream_pattern = r'\.stream\(\).*\.map\(\s*\w+\s*->\s*\w+\.'
    for i, line in enumerate(lines, 1):
        if re.search(stream_pattern, line):
            if not re.search(r'\.filter\(\s*Objects::nonNull', line):
                issues.append({
                    "file": file_path,
                    "line": i,
                    "issue": "Stream map operation may throw NPE if elements are null",
                    "severity": "low",
                    "pattern": "stream_null_element",
                    "snippet": get_snippet(lines, i),
                    "suggestion": "Consider adding .filter(Objects::nonNull) before map"
                })

    # Pattern 6: Constructor/method without @NonNull but required
    # Look for fields used immediately without initialization check
    field_use_pattern = r'this\.(\w+)\.'
    for i, line in enumerate(lines, 1):
        match = re.search(field_use_pattern, line)
        if match:
            field_name = match.group(1)
            # Check if we're in a method (not in constructor initialization)
            context_start = max(0, i - 10)
            context = '\n'.join(lines[context_start:i])
            if 'public ' in context or 'private ' in context or 'protected ' in context:
                # Likely in a method
                if not re.search(rf'this\.{field_name}\s*!=\s*null', context):
                    # Could add issue here if field might be null
                    pass

    return issues


def get_snippet(lines: List[str], line_num: int, context: int = 2) -> str:
    """Get a code snippet around a specific line.

    Args:
        lines: List of file lines
        line_num: Line number (1-indexed)
        context: Number of lines before/after

    Returns:
        Code snippet string
    """
    start = max(0, line_num - context - 1)
    end = min(len(lines), line_num + context)

    snippet_lines = []
    for i in range(start, end):
        prefix = ">>> " if i == line_num - 1 else "    "
        snippet_lines.append(f"{prefix}{i + 1}: {lines[i].rstrip()}")

    return '\n'.join(snippet_lines)


def prioritize_issues(issues: List[Dict]) -> List[Dict]:
    """Sort issues by severity and relevance.

    Args:
        issues: List of issue dictionaries

    Returns:
        Sorted list with high severity first
    """
    severity_order = {"high": 0, "medium": 1, "low": 2}

    return sorted(issues, key=lambda x: (
        severity_order.get(x.get("severity", "low"), 3),
        x.get("file", ""),
        x.get("line", 0)
    ))


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="check_null_safety",
    description="Find potential NullPointerException spots in the codebase. Detects: .get() without isPresent(), method chaining on nullable returns, @Nullable params without null checks.",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Optional: specific file to check. If not provided, checks all Java files."
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of issues to return (default 20)"
        }
    }
)


def register():
    """Register this tool with the registry."""
    register_tool("check_null_safety", check_null_safety, TOOL_DEFINITION)
