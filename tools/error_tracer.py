"""Error tracer tool for diagnosing issues from stack traces or vague descriptions."""

import os
import re
from typing import Dict, List, Any, Optional, Tuple

from core.tools_registry import register_tool, create_tool_definition
from utils.output import (
    print_tool_start, print_tool_result, is_quiet,
    print_code_snippet, format_code_snippet, format_issue_with_snippet,
    bold, error, warn, success, muted, highlight, Colors
)


def trace_error(error_input: str = None, error_type: str = None) -> Dict[str, Any]:
    """
    Trace an error from a stack trace or vague description.

    Handles both:
    - Specific stack traces (pasted by user)
    - Vague descriptions like "my project has NPE"

    Args:
        error_input: Stack trace text or error description
        error_type: Type hint like "NPE", "NullPointer", "ClassNotFound"

    Returns:
        dict with error analysis, relevant code locations, and suggestions
    """
    if not is_quiet():
        print_tool_start("trace_error")

    if not error_input and not error_type:
        return {
            "error": "Please provide either an error description or stack trace",
            "suggestion": "Try: trace_error('NullPointerException at UserService.java:45')"
        }

    # Determine if this is a stack trace or vague description
    input_text = error_input or error_type or ""

    if is_stack_trace(input_text):
        result = analyze_stack_trace_internal(input_text)
    else:
        result = analyze_vague_description(input_text, error_type)

    if not is_quiet():
        if result.get('locations'):
            print_tool_result(f"Found {len(result['locations'])} relevant locations")
            # Print colored snippets for top locations
            print()
            for i, loc in enumerate(result['locations'][:5], 1):
                file_path = loc.get('file')
                line = loc.get('line')
                if file_path and line and os.path.exists(file_path):
                    method = loc.get('method', '')
                    print(f"{error('>')} {bold(f'Location {i}:')} {method}")
                    print_code_snippet(file_path, line, context=2)
        else:
            print_tool_result("No specific locations found")

    return result


def analyze_stack_trace(stack_trace: str) -> Dict[str, Any]:
    """
    Parse a Java stack trace and map to source code.

    Args:
        stack_trace: Full stack trace text

    Returns:
        dict with parsed frames, source locations, and code snippets
    """
    if not is_quiet():
        print_tool_start("analyze_stack_trace")

    result = analyze_stack_trace_internal(stack_trace)

    if not is_quiet():
        frames = result.get('frames', [])
        print_tool_result(f"Parsed {len(frames)} stack frames")

        # Print exception info
        exc_type = result.get('exception_type')
        exc_msg = result.get('exception_message')
        if exc_type:
            print(f"\n{error('Exception:')} {bold(exc_type)}")
            if exc_msg:
                print(f"  {muted(exc_msg)}")

        # Print root cause with colored snippet
        root_cause = result.get('root_cause')
        if root_cause:
            file_path = root_cause.get('file_path')
            line = root_cause.get('line')
            if file_path and line and os.path.exists(file_path):
                print(f"\n{error('Root Cause:')}")
                print_code_snippet(file_path, line, context=3,
                                   message=f"{root_cause.get('class', '')}.{root_cause.get('method', '')}")

        # Print suggestions
        suggestions = result.get('suggestions', [])
        if suggestions:
            print(f"\n{success('Suggestions:')}")
            for sug in suggestions[:3]:
                print(f"  {success('•')} {sug}")

    return result


def is_stack_trace(text: str) -> bool:
    """Check if text looks like a Java stack trace.

    Args:
        text: Input text

    Returns:
        True if it looks like a stack trace
    """
    # Common stack trace indicators
    indicators = [
        r'at\s+[\w.]+\([\w.]+:\d+\)',  # at com.example.Class(File.java:123)
        r'Exception',
        r'Error',
        r'^\s+at\s+',  # Indented "at" lines
        r'Caused by:',
        r'\.java:\d+',  # File.java:123
    ]

    for pattern in indicators:
        if re.search(pattern, text, re.MULTILINE):
            return True

    return False


def analyze_stack_trace_internal(stack_trace: str) -> Dict[str, Any]:
    """Internal stack trace analysis logic.

    Args:
        stack_trace: Stack trace text

    Returns:
        Analysis result dictionary
    """
    result = {
        "exception_type": None,
        "exception_message": None,
        "frames": [],
        "locations": [],
        "root_cause": None,
        "suggestions": []
    }

    lines = stack_trace.strip().split('\n')

    # Parse exception type and message
    exception_match = re.search(r'([\w.]+(?:Exception|Error))(?::\s*(.+))?', stack_trace)
    if exception_match:
        result["exception_type"] = exception_match.group(1)
        result["exception_message"] = exception_match.group(2)

    # Parse stack frames
    frame_pattern = r'at\s+([\w.$]+)\.([\w<>]+)\(([\w.]+):(\d+)\)'

    for match in re.finditer(frame_pattern, stack_trace):
        class_name = match.group(1)
        method_name = match.group(2)
        file_name = match.group(3)
        line_num = int(match.group(4))

        frame = {
            "class": class_name,
            "method": method_name,
            "file": file_name,
            "line": line_num,
            "fqn": f"{class_name}.{method_name}"
        }

        # Try to find actual file path
        file_path = find_java_file(file_name)
        if file_path:
            frame["file_path"] = file_path
            frame["snippet"] = get_code_snippet(file_path, line_num)

        result["frames"].append(frame)

    # Filter to project-only frames (exclude JDK, Spring internal, etc.)
    project_frames = filter_project_frames(result["frames"])

    # Build locations list (only project code)
    for frame in project_frames:
        location = {
            "file": frame.get("file_path") or frame.get("file"),
            "line": frame["line"],
            "method": f"{frame['class']}.{frame['method']}",
            "snippet": frame.get("snippet")
        }
        result["locations"].append(location)

    # Identify root cause (deepest project frame)
    if project_frames:
        result["root_cause"] = project_frames[-1]

    # Generate suggestions based on exception type
    result["suggestions"] = generate_suggestions(result["exception_type"], result)

    return result


def analyze_vague_description(description: str, error_type: str = None) -> Dict[str, Any]:
    """Analyze a vague error description without a stack trace.

    Args:
        description: Vague description like "my project has NPE"
        error_type: Optional type hint

    Returns:
        Analysis with potential problem locations
    """
    result = {
        "description": description,
        "detected_type": None,
        "locations": [],
        "potential_issues": [],
        "suggestions": []
    }

    # Detect error type from description
    error_types = {
        "NullPointerException": ["npe", "null pointer", "nullpointer", "null reference"],
        "ClassNotFoundException": ["class not found", "classnotfound", "missing class"],
        "NoSuchBeanDefinitionException": ["bean not found", "no bean", "missing bean", "autowired"],
        "BeanCreationException": ["bean creation", "failed to create bean", "circular"],
        "DataIntegrityViolationException": ["constraint violation", "duplicate key", "foreign key"],
        "HttpMessageNotReadableException": ["json parse", "request body", "deserialization"],
    }

    detected_type = error_type
    description_lower = description.lower()

    for exc_type, keywords in error_types.items():
        for keyword in keywords:
            if keyword in description_lower:
                detected_type = exc_type
                break
        if detected_type:
            break

    result["detected_type"] = detected_type

    # Based on type, search for potential problem spots
    if detected_type == "NullPointerException" or "null" in description_lower:
        # Import and use null safety checker
        try:
            from tools.null_safety_checker import check_null_safety
            null_results = check_null_safety(limit=5)
            if null_results.get("issues"):
                result["potential_issues"] = null_results["issues"]
                for issue in null_results["issues"][:5]:
                    result["locations"].append({
                        "file": issue.get("file"),
                        "line": issue.get("line"),
                        "issue": issue.get("issue"),
                        "snippet": issue.get("snippet")
                    })
        except ImportError:
            pass

    elif detected_type in ["NoSuchBeanDefinitionException", "BeanCreationException"]:
        # Check bean wiring
        try:
            from tools.bean_wiring_checker import check_bean_wiring
            bean_results = check_bean_wiring()
            if bean_results.get("issues"):
                result["potential_issues"] = bean_results["issues"]
                for issue in bean_results["issues"][:5]:
                    result["locations"].append({
                        "file": issue.get("file"),
                        "line": issue.get("line"),
                        "issue": issue.get("issue"),
                        "snippet": issue.get("snippet")
                    })
        except ImportError:
            pass

    # Search for file:line references in description
    file_line_pattern = r'([\w]+\.java):(\d+)'
    for match in re.finditer(file_line_pattern, description):
        file_name = match.group(1)
        line_num = int(match.group(2))

        file_path = find_java_file(file_name)
        if file_path:
            result["locations"].append({
                "file": file_path,
                "line": line_num,
                "snippet": get_code_snippet(file_path, line_num),
                "source": "mentioned_in_description"
            })

    # Generate suggestions
    result["suggestions"] = generate_suggestions(detected_type, result)

    return result


def filter_project_frames(frames: List[Dict]) -> List[Dict]:
    """Filter stack frames to only include project code.

    Args:
        frames: List of parsed stack frames

    Returns:
        Filtered list of project-only frames
    """
    # Packages to exclude (JDK, Spring internal, libraries)
    exclude_prefixes = [
        "java.", "javax.", "jakarta.",
        "sun.", "com.sun.",
        "org.springframework.aop",
        "org.springframework.cglib",
        "org.springframework.core",
        "org.springframework.beans.factory",
        "org.springframework.context",
        "org.springframework.web.servlet",
        "org.springframework.transaction",
        "org.hibernate.",
        "org.apache.",
        "org.junit.",
        "org.mockito.",
        "jdk.internal.",
        "reactor.",
        "io.netty.",
    ]

    project_frames = []
    for frame in frames:
        class_name = frame.get("class", "")
        is_excluded = any(class_name.startswith(prefix) for prefix in exclude_prefixes)

        # Include if file was found in project
        has_file = frame.get("file_path") is not None

        if not is_excluded or has_file:
            project_frames.append(frame)

    return project_frames


def find_java_file(file_name: str) -> Optional[str]:
    """Find a Java file in the project by name.

    Args:
        file_name: File name like "UserService.java"

    Returns:
        Full path to file or None if not found
    """
    project_root = os.getcwd()

    # Search in src directories
    src_dirs = ["src/main/java", "src/test/java", "src"]

    for src_dir in src_dirs:
        src_path = os.path.join(project_root, src_dir)
        if os.path.exists(src_path):
            for root, _, files in os.walk(src_path):
                if file_name in files:
                    return os.path.join(root, file_name)

    return None


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


def generate_suggestions(exception_type: str, analysis: Dict) -> List[str]:
    """Generate suggestions based on exception type and analysis.

    Args:
        exception_type: Type of exception
        analysis: Current analysis result

    Returns:
        List of suggestion strings
    """
    suggestions = []

    if exception_type == "NullPointerException":
        suggestions.append("Check if objects are properly initialized before use")
        suggestions.append("Consider using Optional<T> for nullable values")
        suggestions.append("Add null checks before method calls on potentially null objects")

        if analysis.get("root_cause"):
            frame = analysis["root_cause"]
            suggestions.append(f"Focus on {frame['class']}.{frame['method']} at line {frame['line']}")

    elif exception_type == "ClassNotFoundException":
        suggestions.append("Verify all required dependencies are in pom.xml/build.gradle")
        suggestions.append("Run 'mvn dependency:tree' or 'gradle dependencies' to check")
        suggestions.append("Make sure the class exists and is correctly imported")

    elif exception_type == "NoSuchBeanDefinitionException":
        suggestions.append("Check that the bean class has @Component, @Service, @Repository, or @Bean")
        suggestions.append("Verify component scanning includes the package with the bean")
        suggestions.append("Check for typos in @Qualifier names")

    elif exception_type == "BeanCreationException":
        suggestions.append("Check for circular dependencies between beans")
        suggestions.append("Verify all @Autowired dependencies can be resolved")
        suggestions.append("Consider using @Lazy to break circular dependencies")

    elif exception_type == "DataIntegrityViolationException":
        suggestions.append("Check database constraints (unique, foreign key)")
        suggestions.append("Verify data being inserted/updated meets constraints")
        suggestions.append("Check for duplicate key insertions")

    else:
        suggestions.append("Review the code at the error location")
        suggestions.append("Add logging to trace the execution flow")
        suggestions.append("Check input values and object initialization")

    return suggestions


# Tool definitions
TRACE_ERROR_DEFINITION = create_tool_definition(
    name="trace_error",
    description="Trace and diagnose errors from stack traces OR vague descriptions. Handles 'NullPointerException at UserService.java:45' AND 'my project has NPE'. Maps errors to source code and suggests fixes.",
    parameters={
        "error_input": {
            "type": "string",
            "description": "Stack trace text or error description"
        },
        "error_type": {
            "type": "string",
            "description": "Optional: error type hint like 'NPE', 'NullPointer', 'ClassNotFound'"
        }
    }
)

ANALYZE_STACK_TRACE_DEFINITION = create_tool_definition(
    name="analyze_stack_trace",
    description="Parse a Java stack trace and map frames to source code. Returns code snippets at error locations.",
    parameters={
        "stack_trace": {
            "type": "string",
            "description": "Full Java stack trace text"
        }
    }
)


def register():
    """Register this tool with the registry."""
    register_tool("trace_error", trace_error, TRACE_ERROR_DEFINITION)
    register_tool("analyze_stack_trace", analyze_stack_trace, ANALYZE_STACK_TRACE_DEFINITION)
