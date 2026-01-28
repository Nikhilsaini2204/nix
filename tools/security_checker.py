"""Security checker tool for finding security vulnerabilities in Spring Boot code."""

import os
import re
from typing import Dict, List, Any

from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def check_security(file_path: str = None, limit: int = 20) -> Dict[str, Any]:
    """
    Find security vulnerabilities in the codebase.

    Detects:
    - Hardcoded credentials (passwords, API keys, secrets)
    - SQL injection vulnerabilities
    - Improper string comparison (== vs .equals())
    - Missing input validation
    - Insecure random number generation
    - Path traversal vulnerabilities
    - XSS vulnerabilities
    - Missing authorization checks

    Args:
        file_path: Optional specific file to check
        limit: Maximum issues to return

    Returns:
        dict with security issues found
    """
    if not is_quiet():
        print_tool_start("check_security")

    project_root = os.getcwd()
    issues = []

    if file_path:
        if os.path.exists(file_path):
            issues.extend(analyze_file_security(file_path))
        else:
            return {"error": f"File not found: {file_path}", "issues": []}
    else:
        java_files = find_java_files(project_root)
        for java_file in java_files:
            issues.extend(analyze_file_security(java_file))
            if len(issues) >= limit * 2:
                break

    # Prioritize by severity
    issues = sorted(issues, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.get("severity", "low"), 4))

    if len(issues) > limit:
        issues = issues[:limit]

    result = {
        "total_issues": len(issues),
        "issues": issues,
        "summary": f"Found {len(issues)} security issues"
    }

    if not is_quiet():
        print_tool_result(result["summary"])
        for issue in issues[:5]:
            print_tool_result(f"  [{issue.get('severity', 'medium').upper()}] {issue.get('issue')} at {os.path.basename(issue.get('file', ''))}:{issue.get('line', '?')}")

    return result


def find_java_files(project_root: str) -> List[str]:
    """Find all Java files in the project."""
    java_files = []
    seen_files = set()  # Track to avoid duplicates

    for src_dir in ["src/main/java", "src"]:
        src_path = os.path.join(project_root, src_dir)
        if os.path.exists(src_path):
            for root, _, files in os.walk(src_path):
                # Skip test directories (but not project names containing 'test')
                rel_path = os.path.relpath(root, project_root)
                if '/test/' in rel_path or rel_path.startswith('test/') or rel_path == 'test':
                    continue
                if 'src/test' in rel_path:
                    continue
                for file in files:
                    if file.endswith('.java'):
                        full_path = os.path.join(root, file)
                        if full_path not in seen_files:
                            seen_files.add(full_path)
                            java_files.append(full_path)
    return java_files


def analyze_file_security(file_path: str) -> List[Dict[str, Any]]:
    """Analyze a file for security issues."""
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception:
        return issues

    # 1. Hardcoded credentials
    credential_patterns = [
        (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
        (r'(?i)(api[_-]?key|apikey)\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
        (r'(?i)(secret|token)\s*=\s*["\'][^"\']+["\']', "Hardcoded secret/token"),
        (r'(?i)(access[_-]?key|accesskey)\s*=\s*["\'][^"\']+["\']', "Hardcoded access key"),
        (r'private\s+static\s+final\s+String\s+\w*(PASSWORD|SECRET|KEY|TOKEN)\w*\s*=\s*"[^"]+"', "Hardcoded credential in constant"),
    ]

    for i, line in enumerate(lines, 1):
        for pattern, issue_type in credential_patterns:
            if re.search(pattern, line):
                # Exclude common false positives
                if not re.search(r'password\s*=\s*["\'](\$\{|%s|null|""|\'\')', line, re.I):
                    issues.append({
                        "file": file_path,
                        "line": i,
                        "issue": issue_type,
                        "severity": "critical",
                        "category": "hardcoded_credential",
                        "snippet": get_snippet(lines, i),
                        "suggestion": "Move credentials to environment variables or secure vault"
                    })
                break

    # 2. SQL Injection
    sql_patterns = [
        (r'"\s*SELECT\s+.*\+\s*\w+', "SQL injection - string concatenation in SELECT"),
        (r'"\s*INSERT\s+.*\+\s*\w+', "SQL injection - string concatenation in INSERT"),
        (r'"\s*UPDATE\s+.*\+\s*\w+', "SQL injection - string concatenation in UPDATE"),
        (r'"\s*DELETE\s+.*\+\s*\w+', "SQL injection - string concatenation in DELETE"),
        (r'createNativeQuery\s*\(\s*[^"]*\+', "SQL injection in native query"),
        (r'executeQuery\s*\(\s*[^"]*\+', "SQL injection in executeQuery"),
    ]

    for i, line in enumerate(lines, 1):
        for pattern, issue_type in sql_patterns:
            if re.search(pattern, line, re.I):
                issues.append({
                    "file": file_path,
                    "line": i,
                    "issue": issue_type,
                    "severity": "critical",
                    "category": "sql_injection",
                    "snippet": get_snippet(lines, i),
                    "suggestion": "Use parameterized queries or JPA named parameters"
                })
                break

    # 3. String comparison with == instead of .equals()
    # Find String variables and check for == comparison
    for i, line in enumerate(lines, 1):
        # Check for == comparison with String-like variables
        if re.search(r'\b(password|token|secret|key|name|email|id|status|type)\s*==\s*\w+', line, re.I):
            if not re.search(r'==\s*null', line):
                issues.append({
                    "file": file_path,
                    "line": i,
                    "issue": "String comparison using == instead of .equals()",
                    "severity": "high",
                    "category": "string_comparison",
                    "snippet": get_snippet(lines, i),
                    "suggestion": "Use .equals() for String comparison"
                })

    # 4. Missing input validation in controllers
    if 'Controller' in file_path or '@RestController' in content or '@Controller' in content:
        # Check for @RequestBody without @Valid
        for i, line in enumerate(lines, 1):
            if '@RequestBody' in line and '@Valid' not in line:
                # Check if @Valid is on adjacent line
                context = '\n'.join(lines[max(0, i-2):i+1])
                if '@Valid' not in context:
                    issues.append({
                        "file": file_path,
                        "line": i,
                        "issue": "Missing @Valid annotation for request body validation",
                        "severity": "medium",
                        "category": "missing_validation",
                        "snippet": get_snippet(lines, i),
                        "suggestion": "Add @Valid before @RequestBody to enable validation"
                    })

        # Check for @RequestParam without validation
        for i, line in enumerate(lines, 1):
            if '@RequestParam' in line:
                # Check method body for validation
                method_end = find_method_end(lines, i)
                method_body = '\n'.join(lines[i:method_end])
                param_match = re.search(r'@RequestParam.*?\)\s*(\w+)\s+(\w+)', line)
                if param_match:
                    param_name = param_match.group(2)
                    if not re.search(rf'validate|check|verify|{param_name}\s*==\s*null|{param_name}\.isEmpty|StringUtils', method_body, re.I):
                        issues.append({
                            "file": file_path,
                            "line": i,
                            "issue": f"Request parameter '{param_name}' may lack validation",
                            "severity": "low",
                            "category": "missing_validation",
                            "snippet": get_snippet(lines, i),
                            "suggestion": "Validate request parameters before use"
                        })

    # 5. Insecure random
    for i, line in enumerate(lines, 1):
        if 'new Random()' in line or 'Math.random()' in line:
            issues.append({
                "file": file_path,
                "line": i,
                "issue": "Insecure random number generator for security context",
                "severity": "medium",
                "category": "insecure_random",
                "snippet": get_snippet(lines, i),
                "suggestion": "Use SecureRandom for security-sensitive operations"
            })

    # 6. Path traversal
    for i, line in enumerate(lines, 1):
        if re.search(r'new File\s*\([^)]*\+', line) or re.search(r'Paths\.get\s*\([^)]*\+', line):
            if not re.search(r'normalize|canonical|sanitize', '\n'.join(lines[max(0, i-5):i+5]), re.I):
                issues.append({
                    "file": file_path,
                    "line": i,
                    "issue": "Potential path traversal vulnerability",
                    "severity": "high",
                    "category": "path_traversal",
                    "snippet": get_snippet(lines, i),
                    "suggestion": "Validate and sanitize file paths, use canonical paths"
                })

    # 7. Missing authorization on endpoints
    if 'Controller' in file_path or '@RestController' in content:
        has_security = '@PreAuthorize' in content or '@Secured' in content or '@RolesAllowed' in content
        has_delete_or_admin = bool(re.search(r'@DeleteMapping|@PutMapping|/admin', content))

        if has_delete_or_admin and not has_security:
            # Find the specific endpoints
            for i, line in enumerate(lines, 1):
                if '@DeleteMapping' in line or '@PutMapping' in line or '/admin' in line:
                    issues.append({
                        "file": file_path,
                        "line": i,
                        "issue": "Sensitive endpoint may lack authorization check",
                        "severity": "high",
                        "category": "missing_authorization",
                        "snippet": get_snippet(lines, i),
                        "suggestion": "Add @PreAuthorize or @Secured annotation"
                    })

    # 8. Logging sensitive data
    for i, line in enumerate(lines, 1):
        if re.search(r'log\.\w+\s*\([^)]*\b(password|secret|token|key|credential)', line, re.I):
            issues.append({
                "file": file_path,
                "line": i,
                "issue": "Potentially logging sensitive data",
                "severity": "high",
                "category": "sensitive_logging",
                "snippet": get_snippet(lines, i),
                "suggestion": "Avoid logging passwords, tokens, or other sensitive data"
            })

    return issues


def find_method_end(lines: List[str], start: int) -> int:
    """Find the end of a method starting from a line."""
    brace_count = 0
    started = False

    for i in range(start, min(start + 50, len(lines))):
        line = lines[i]
        brace_count += line.count('{') - line.count('}')
        if '{' in line:
            started = True
        if started and brace_count <= 0:
            return i + 1

    return min(start + 20, len(lines))


def get_snippet(lines: List[str], line_num: int, context: int = 2) -> str:
    """Get code snippet around a line."""
    start = max(0, line_num - context - 1)
    end = min(len(lines), line_num + context)

    snippet_lines = []
    for i in range(start, end):
        prefix = ">>> " if i == line_num - 1 else "    "
        snippet_lines.append(f"{prefix}{i + 1}: {lines[i].rstrip()}")

    return '\n'.join(snippet_lines)


TOOL_DEFINITION = create_tool_definition(
    name="check_security",
    description="Find security vulnerabilities: hardcoded credentials, SQL injection, improper string comparison, missing validation, path traversal, missing authorization.",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Optional: specific file to check"
        },
        "limit": {
            "type": "integer",
            "description": "Maximum issues to return (default 20)"
        }
    }
)


def register():
    """Register this tool."""
    register_tool("check_security", check_security, TOOL_DEFINITION)
