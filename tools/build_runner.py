"""Build runner tool for Spring Boot projects."""

import os
import re
import subprocess
from typing import Dict, List, Any, Optional, Tuple

from core.tools_registry import register_tool, create_tool_definition
from utils.output import (
    print_tool_start, print_tool_result, is_quiet,
    print_code_snippet, bold, error, warn, success, muted, highlight
)

# Import lazily to avoid circular imports
_get_quick_suggestion = None

def get_quick_suggestion_safe(error_message: str):
    """Get quick suggestion, importing lazily."""
    global _get_quick_suggestion
    if _get_quick_suggestion is None:
        try:
            from tools.fix_suggester import get_quick_suggestion
            _get_quick_suggestion = get_quick_suggestion
        except ImportError:
            return None
    return _get_quick_suggestion(error_message)


def build_project(clean: bool = False) -> Dict[str, Any]:
    """
    Build/compile the project using Maven or Gradle.

    Args:
        clean: If True, run clean before compile

    Returns:
        dict with build status, errors if any, and parsed error locations
    """
    if not is_quiet():
        print_tool_start("build_project")

    build_file, build_type = find_build_tool()

    if not build_file:
        if not is_quiet():
            print_tool_result("No build file found")
        return {
            "success": False,
            "error": "No build file found. This doesn't appear to be a Maven or Gradle project.",
            "suggestion": "Make sure you're in a Maven or Gradle project directory"
        }

    try:
        if build_type == "maven":
            result = run_maven_build(clean)
        else:
            result = run_gradle_build(clean)

        if not is_quiet():
            if result['success']:
                print_tool_result(success("Build successful"))
            else:
                errors = result.get('errors', [])
                print_tool_result(error(f"Build failed with {len(errors)} errors"))

                # Print colored error snippets with inline suggestions
                for i, err in enumerate(errors[:5], 1):
                    file_path = err.get('file')
                    line = err.get('line')
                    message = err.get('message', 'Unknown error')

                    print(f"\n{error(f'[Error {i}]')} {bold(message)}")
                    if file_path and line:
                        if os.path.exists(file_path):
                            print_code_snippet(file_path, line, context=2)
                        else:
                            file_name = os.path.basename(file_path) if file_path else 'unknown'
                            print(f"  {muted('at')} {highlight(file_name)}:{warn(str(line))}")

                    # Show inline quick fix suggestion
                    quick_fix = get_quick_suggestion_safe(message)
                    if quick_fix:
                        print(f"  {success('Quick Fix:')} {quick_fix}")

                if len(errors) > 5:
                    print(f"\n{muted(f'... and {len(errors) - 5} more errors')}")

        return result

    except Exception as e:
        if not is_quiet():
            print_tool_result(f"Error: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to run build: {str(e)}",
            "build_tool": build_type
        }


def find_build_tool() -> Tuple[Optional[str], Optional[str]]:
    """Find build file in current directory.

    Returns:
        (file_path, build_type) or (None, None)
    """
    project_root = os.getcwd()

    candidates = [
        ("pom.xml", "maven"),
        ("build.gradle", "gradle"),
        ("build.gradle.kts", "gradle"),
    ]

    for filename, build_type in candidates:
        path = os.path.join(project_root, filename)
        if os.path.exists(path):
            return path, build_type

    return None, None


def run_maven_build(clean: bool = False) -> Dict[str, Any]:
    """Run Maven compile command.

    Args:
        clean: If True, run mvn clean compile instead of just compile

    Returns:
        dict with success status and parsed errors
    """
    # Check for mvnw first
    mvnw = "./mvnw" if os.path.exists("mvnw") else "mvn"

    command = [mvnw, "clean", "compile"] if clean else [mvnw, "compile"]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        output = result.stdout + result.stderr
        success = result.returncode == 0

        errors = []
        if not success:
            errors = parse_maven_errors(output)

        return {
            "success": success,
            "build_tool": "maven",
            "command": " ".join(command),
            "errors": errors,
            "error_count": len(errors),
            "output_summary": summarize_output(output, success)
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "build_tool": "maven",
            "error": "Build timed out after 5 minutes",
            "errors": []
        }
    except FileNotFoundError:
        return {
            "success": False,
            "build_tool": "maven",
            "error": "Maven not found. Make sure mvn or mvnw is available.",
            "errors": []
        }


def run_gradle_build(clean: bool = False) -> Dict[str, Any]:
    """Run Gradle compile command.

    Args:
        clean: If True, run gradle clean build instead of just build

    Returns:
        dict with success status and parsed errors
    """
    # Check for gradlew first
    gradlew = "./gradlew" if os.path.exists("gradlew") else "gradle"

    command = [gradlew, "clean", "compileJava"] if clean else [gradlew, "compileJava"]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300
        )

        output = result.stdout + result.stderr
        success = result.returncode == 0

        errors = []
        if not success:
            errors = parse_gradle_errors(output)

        return {
            "success": success,
            "build_tool": "gradle",
            "command": " ".join(command),
            "errors": errors,
            "error_count": len(errors),
            "output_summary": summarize_output(output, success)
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "build_tool": "gradle",
            "error": "Build timed out after 5 minutes",
            "errors": []
        }
    except FileNotFoundError:
        return {
            "success": False,
            "build_tool": "gradle",
            "error": "Gradle not found. Make sure gradle or gradlew is available.",
            "errors": []
        }


def parse_maven_errors(output: str) -> List[Dict[str, Any]]:
    """Parse Maven compiler output for errors.

    Args:
        output: Maven output text

    Returns:
        List of error dictionaries with file, line, message, snippet, and suggestion
    """
    errors = []
    seen_errors = set()  # Track unique errors by file:line:message

    # Maven compiler error format:
    # [ERROR] /path/to/File.java:[line,col] message
    # or [ERROR] /path/to/File.java:[line,col] error: message
    pattern = r'\[ERROR\]\s+([^:]+\.java):\[(\d+),(\d+)\]\s+(?:error:\s*)?(.+)'

    for match in re.finditer(pattern, output):
        file_path = match.group(1)
        line = int(match.group(2))
        message = match.group(4).strip()

        # Skip duplicates
        error_key = f"{file_path}:{line}:{message}"
        if error_key in seen_errors:
            continue
        seen_errors.add(error_key)

        error_entry = {
            "file": file_path,
            "line": line,
            "column": int(match.group(3)),
            "message": message,
            "issue": message,  # For compatibility with issue display
            "type": "error",
            "severity": "critical"
        }
        # Add code snippet
        snippet = get_code_snippet(file_path, line, context=2)
        if snippet:
            error_entry["snippet"] = snippet
        # Add quick suggestion
        suggestion = get_quick_suggestion_safe(message)
        if suggestion:
            error_entry["suggestion"] = suggestion
        errors.append(error_entry)

    # Also catch simpler error format:
    # [ERROR] /path/to/File.java:[line] error: message
    pattern2 = r'\[ERROR\]\s+([^:]+\.java):(\d+):\s+error:\s+(.+)'

    for match in re.finditer(pattern2, output):
        file_path = match.group(1)
        line = int(match.group(2))
        message = match.group(3).strip()

        # Skip duplicates
        error_key = f"{file_path}:{line}:{message}"
        if error_key in seen_errors:
            continue
        seen_errors.add(error_key)

        error_entry = {
            "file": file_path,
            "line": line,
            "column": 0,
            "message": message,
            "issue": message,
            "type": "error",
            "severity": "critical"
        }
        # Add code snippet
        snippet = get_code_snippet(file_path, line, context=2)
        if snippet:
            error_entry["snippet"] = snippet
        # Add quick suggestion
        suggestion = get_quick_suggestion_safe(message)
        if suggestion:
            error_entry["suggestion"] = suggestion
        errors.append(error_entry)

    # Only add general error messages if no specific errors found
    # Skip meta messages like "re-run Maven with -e switch"
    # These are not actual errors, just Maven suggestions

    return errors


def parse_gradle_errors(output: str) -> List[Dict[str, Any]]:
    """Parse Gradle compiler output for errors.

    Args:
        output: Gradle output text

    Returns:
        List of error dictionaries with file, line, message, and suggestion
    """
    errors = []

    # Gradle compiler error format:
    # /path/to/File.java:line: error: message
    pattern = r'([^:\s]+\.java):(\d+):\s+error:\s+(.+)'

    for match in re.finditer(pattern, output):
        message = match.group(3).strip()
        error_entry = {
            "file": match.group(1),
            "line": int(match.group(2)),
            "column": 0,
            "message": message,
            "type": "error"
        }
        # Add quick suggestion
        suggestion = get_quick_suggestion_safe(message)
        if suggestion:
            error_entry["suggestion"] = suggestion
        errors.append(error_entry)

    # Gradle task failure format
    pattern2 = r'> Task :(\w+) FAILED'
    for match in re.finditer(pattern2, output):
        task = match.group(1)
        if not any(e.get('task') == task for e in errors):
            errors.append({
                "file": None,
                "line": None,
                "task": task,
                "message": f"Task {task} failed",
                "type": "task_failure"
            })

    return errors


def summarize_output(output: str, success: bool) -> str:
    """Create a brief summary of the build output.

    Args:
        output: Full build output
        success: Whether build succeeded

    Returns:
        Summary string
    """
    if success:
        # Look for BUILD SUCCESS or similar
        if "BUILD SUCCESS" in output:
            return "Maven build completed successfully"
        elif "BUILD SUCCESSFUL" in output:
            return "Gradle build completed successfully"
        else:
            return "Build completed successfully"

    # For failures, extract key message
    lines = output.split('\n')
    error_lines = [l for l in lines if 'error' in l.lower() or 'failed' in l.lower()]

    if error_lines:
        return error_lines[0][:200]  # First error line, truncated

    return "Build failed. Check errors for details."


def get_code_snippet(file_path: str, line: int, context: int = 3) -> Optional[str]:
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


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="build_project",
    description="Compile/build the project using Maven or Gradle. Parses and returns any compiler errors with file:line locations. Use when user says: build, compile, check for errors, run build.",
    parameters={
        "clean": {
            "type": "boolean",
            "description": "If true, run clean before compile"
        }
    }
)


def register():
    """Register this tool with the registry."""
    register_tool("build_project", build_project, TOOL_DEFINITION)
