"""Bean wiring checker tool for detecting Spring bean issues."""

import os
import re
from typing import Dict, List, Any, Optional, Set

from core.tools_registry import register_tool, create_tool_definition
from utils.output import (
    print_tool_start, print_tool_result, is_quiet,
    print_issues_summary, bold, error, warn, success, muted, highlight
)


def check_bean_wiring(file_path: str = None) -> Dict[str, Any]:
    """
    Check for Spring bean wiring issues.

    Detects:
    - Missing @Autowired on injected fields
    - Circular dependency patterns
    - Missing @Component/@Service/@Repository annotations
    - @Autowired on non-bean classes
    - Injection of concrete classes instead of interfaces

    Args:
        file_path: Optional specific file to check. If None, checks all Java files.

    Returns:
        dict with found issues, their locations, and suggestions
    """
    if not is_quiet():
        print_tool_start("check_bean_wiring")

    project_root = os.getcwd()
    issues = []

    # First pass: collect all beans and their dependencies
    beans = {}  # class_name -> bean_info
    dependencies = {}  # class_name -> list of dependency class names

    # Find all Java files
    if file_path:
        java_files = [file_path] if os.path.exists(file_path) else []
    else:
        java_files = find_java_files(project_root)

    # Scan for beans and dependencies
    for java_file in java_files:
        file_beans, file_deps, file_issues = analyze_file_for_beans(java_file)
        beans.update(file_beans)
        dependencies.update(file_deps)
        issues.extend(file_issues)

    # Check for circular dependencies
    circular_issues = detect_circular_dependencies(dependencies)
    issues.extend(circular_issues)

    # Check for missing beans (dependencies that don't exist as beans)
    missing_issues = detect_missing_beans(beans, dependencies)
    issues.extend(missing_issues)

    result = {
        "total_issues": len(issues),
        "total_beans": len(beans),
        "issues": issues,
        "beans": list(beans.keys()),
        "summary": f"Found {len(issues)} bean wiring issues among {len(beans)} beans"
    }

    if not is_quiet():
        print_tool_result(result["summary"])
        # Print colored issues with snippets
        if issues:
            print_issues_summary(issues[:10], "Bean Wiring Issues")

    return result


def find_java_files(project_root: str) -> List[str]:
    """Find all Java files in the project."""
    java_files = []
    src_dirs = ["src/main/java", "src"]

    for src_dir in src_dirs:
        src_path = os.path.join(project_root, src_dir)
        if os.path.exists(src_path):
            for root, _, files in os.walk(src_path):
                if 'test' in root.lower():
                    continue
                for file in files:
                    if file.endswith('.java'):
                        java_files.append(os.path.join(root, file))

    return java_files


def analyze_file_for_beans(file_path: str) -> tuple:
    """Analyze a single file for bean definitions and dependencies.

    Args:
        file_path: Path to the Java file

    Returns:
        Tuple of (beans dict, dependencies dict, issues list)
    """
    beans = {}
    dependencies = {}
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception:
        return beans, dependencies, issues

    # Spring bean annotations
    bean_annotations = {
        '@Component', '@Service', '@Repository', '@Controller',
        '@RestController', '@Configuration', '@Bean'
    }

    # Find class declaration
    class_match = re.search(r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)', content)
    if not class_match:
        return beans, dependencies, issues

    class_name = class_match.group(1)

    # Check if this class is a bean
    is_bean = False
    for annotation in bean_annotations:
        if annotation in content:
            is_bean = True
            break

    if is_bean:
        beans[class_name] = {
            "file": file_path,
            "class": class_name
        }
        dependencies[class_name] = []

    # Find @Autowired fields
    autowired_pattern = r'@Autowired\s+(?:private\s+)?(\w+)\s+(\w+)'
    for match in re.finditer(autowired_pattern, content):
        dep_type = match.group(1)
        dep_name = match.group(2)

        if is_bean:
            dependencies[class_name].append(dep_type)

    # Find constructor injection
    constructor_pattern = rf'{class_name}\s*\(([^)]+)\)'
    constructor_match = re.search(constructor_pattern, content)
    if constructor_match:
        params = constructor_match.group(1)
        # Parse parameters
        param_pattern = r'(?:@\w+\s+)*(\w+)\s+\w+'
        for param_match in re.finditer(param_pattern, params):
            param_type = param_match.group(1)
            if is_bean and param_type not in ['String', 'int', 'Integer', 'boolean', 'Boolean', 'long', 'Long', 'List', 'Map', 'Set']:
                dependencies[class_name].append(param_type)

    # Check for field injection without @Autowired
    field_pattern = r'private\s+(?!static)(?!final)(\w+)\s+(\w+);'
    for i, line in enumerate(lines, 1):
        match = re.search(field_pattern, line)
        if match:
            field_type = match.group(1)
            field_name = match.group(2)

            # Check if this field type is a known bean type
            if field_type in ['Service', 'Repository', 'Controller'] or field_type.endswith('Service') or field_type.endswith('Repository'):
                # Check if there's @Autowired before this line
                context_start = max(0, i - 3)
                context = '\n'.join(lines[context_start:i])
                if '@Autowired' not in context and '@Inject' not in context:
                    # Check if it's set in constructor
                    if not is_set_in_constructor(content, class_name, field_name):
                        issues.append({
                            "file": file_path,
                            "line": i,
                            "issue": f"Field '{field_name}' of type '{field_type}' may need @Autowired",
                            "severity": "medium",
                            "pattern": "missing_autowired",
                            "snippet": get_snippet(lines, i),
                            "suggestion": "Add @Autowired annotation or inject via constructor"
                        })

    # Check for @Autowired on non-bean class
    if not is_bean:
        autowired_count = len(re.findall(r'@Autowired', content))
        if autowired_count > 0:
            class_line = 1
            for i, line in enumerate(lines, 1):
                if f'class {class_name}' in line:
                    class_line = i
                    break

            issues.append({
                "file": file_path,
                "line": class_line,
                "issue": f"Class '{class_name}' has @Autowired fields but is not a Spring bean",
                "severity": "high",
                "pattern": "autowired_non_bean",
                "snippet": get_snippet(lines, class_line),
                "suggestion": "Add @Component, @Service, or @Repository annotation to make it a bean"
            })

    # Check for injection of concrete classes instead of interfaces
    for i, line in enumerate(lines, 1):
        if '@Autowired' in line or (i > 0 and '@Autowired' in lines[i - 2]):
            next_line = lines[i] if i < len(lines) else ""
            # Look for concrete class injection (ends with Impl or doesn't start with I)
            impl_match = re.search(r'private\s+(\w+Impl)\s+', line + next_line)
            if impl_match:
                impl_class = impl_match.group(1)
                issues.append({
                    "file": file_path,
                    "line": i,
                    "issue": f"Injecting concrete class '{impl_class}' instead of interface",
                    "severity": "low",
                    "pattern": "concrete_injection",
                    "snippet": get_snippet(lines, i),
                    "suggestion": "Consider injecting the interface instead for loose coupling"
                })

    return beans, dependencies, issues


def is_set_in_constructor(content: str, class_name: str, field_name: str) -> bool:
    """Check if a field is set in the constructor.

    Args:
        content: File content
        class_name: Class name
        field_name: Field name

    Returns:
        True if field is set in constructor
    """
    # Look for constructor
    constructor_pattern = rf'{class_name}\s*\([^)]*\)\s*\{{[^}}]*this\.{field_name}\s*='
    return bool(re.search(constructor_pattern, content, re.DOTALL))


def detect_circular_dependencies(dependencies: Dict[str, List[str]]) -> List[Dict]:
    """Detect circular dependencies between beans.

    Args:
        dependencies: Map of class name to its dependencies

    Returns:
        List of circular dependency issues
    """
    issues = []
    visited = set()
    rec_stack = set()

    def find_cycle(node: str, path: List[str]) -> Optional[List[str]]:
        if node in rec_stack:
            # Found cycle
            cycle_start = path.index(node)
            return path[cycle_start:] + [node]

        if node in visited:
            return None

        visited.add(node)
        rec_stack.add(node)

        for dep in dependencies.get(node, []):
            if dep in dependencies:  # Only follow if it's a known bean
                cycle = find_cycle(dep, path + [node])
                if cycle:
                    return cycle

        rec_stack.remove(node)
        return None

    # Check each bean
    for bean in dependencies:
        cycle = find_cycle(bean, [])
        if cycle:
            cycle_str = " -> ".join(cycle)
            if cycle_str not in [i.get("cycle_str") for i in issues]:
                issues.append({
                    "file": None,
                    "line": None,
                    "issue": f"Circular dependency detected: {cycle_str}",
                    "severity": "high",
                    "pattern": "circular_dependency",
                    "cycle": cycle,
                    "cycle_str": cycle_str,
                    "suggestion": "Consider using @Lazy, setter injection, or restructuring the dependencies"
                })

        visited.clear()
        rec_stack.clear()

    return issues


def detect_missing_beans(beans: Dict, dependencies: Dict) -> List[Dict]:
    """Detect dependencies on classes that aren't beans.

    Args:
        beans: Map of known beans
        dependencies: Map of dependencies

    Returns:
        List of missing bean issues
    """
    issues = []
    checked = set()

    for bean_name, deps in dependencies.items():
        for dep in deps:
            if dep not in beans and dep not in checked:
                # Skip common non-bean types
                skip_types = {'String', 'Integer', 'Long', 'Boolean', 'List', 'Map', 'Set',
                              'Optional', 'Object', 'Environment', 'ApplicationContext'}
                if dep in skip_types:
                    continue

                checked.add(dep)
                # This dependency might be missing as a bean
                # But only warn if it looks like a service/repo name
                if dep.endswith('Service') or dep.endswith('Repository') or dep.endswith('Controller'):
                    issues.append({
                        "file": None,
                        "line": None,
                        "issue": f"'{bean_name}' depends on '{dep}' which may not be a registered bean",
                        "severity": "medium",
                        "pattern": "missing_bean",
                        "suggestion": f"Make sure {dep} is annotated with @Component, @Service, or @Repository"
                    })

    return issues


def get_snippet(lines: List[str], line_num: int, context: int = 2) -> str:
    """Get a code snippet around a specific line."""
    start = max(0, line_num - context - 1)
    end = min(len(lines), line_num + context)

    snippet_lines = []
    for i in range(start, end):
        prefix = ">>> " if i == line_num - 1 else "    "
        snippet_lines.append(f"{prefix}{i + 1}: {lines[i].rstrip()}")

    return '\n'.join(snippet_lines)


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="check_bean_wiring",
    description="Check for Spring bean wiring issues. Detects: missing @Autowired, circular dependencies, @Autowired on non-beans, missing bean definitions.",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Optional: specific file to check. If not provided, checks all Java files."
        }
    }
)


def register():
    """Register this tool with the registry."""
    register_tool("check_bean_wiring", check_bean_wiring, TOOL_DEFINITION)
