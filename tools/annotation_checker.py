"""Annotation checker tool for detecting missing or incorrect annotations."""

import os
import re
from typing import Dict, List, Any, Optional

from core.tools_registry import register_tool, create_tool_definition
from utils.output import (
    print_tool_start, print_tool_result, is_quiet,
    print_issues_summary, bold, error, warn, success, muted, highlight
)


def check_annotations(file_path: str = None) -> Dict[str, Any]:
    """
    Check for missing or incorrect annotations in Spring Boot code.

    Detects:
    - Missing @Override on overridden methods
    - @Entity without @Id
    - @Service without interface implementation
    - Missing @Transactional on service methods
    - @RestController without @RequestMapping
    - @Autowired without @Component/@Service/@Repository

    Args:
        file_path: Optional specific file to check. If None, checks all Java files.

    Returns:
        dict with found issues, their locations, and suggestions
    """
    if not is_quiet():
        print_tool_start("check_annotations")

    project_root = os.getcwd()
    issues = []

    # Find all Java files
    if file_path:
        java_files = [file_path] if os.path.exists(file_path) else []
    else:
        java_files = find_java_files(project_root)

    for java_file in java_files:
        file_issues = analyze_file_for_annotation_issues(java_file)
        issues.extend(file_issues)

    # Sort by severity
    issues = sorted(issues, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", "low"), 3))

    result = {
        "total_issues": len(issues),
        "issues": issues,
        "summary": f"Found {len(issues)} annotation issues"
    }

    if not is_quiet():
        print_tool_result(result["summary"])
        # Print colored issues with snippets
        if issues:
            print_issues_summary(issues[:10], "Annotation Issues")

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


def analyze_file_for_annotation_issues(file_path: str) -> List[Dict[str, Any]]:
    """Analyze a single file for annotation issues.

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

    # Get class info
    class_match = re.search(r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?', content)
    class_name = class_match.group(1) if class_match else None
    extends_class = class_match.group(2) if class_match and class_match.group(2) else None
    implements = class_match.group(3).split(',') if class_match and class_match.group(3) else []
    implements = [i.strip() for i in implements]

    # Check 1: @Entity without @Id
    if '@Entity' in content:
        if '@Id' not in content:
            entity_line = find_annotation_line(lines, '@Entity')
            issues.append({
                "file": file_path,
                "line": entity_line,
                "issue": "@Entity class missing @Id annotation on primary key field",
                "severity": "high",
                "pattern": "entity_no_id",
                "snippet": get_snippet(lines, entity_line) if entity_line else None,
                "suggestion": "Add @Id annotation to the primary key field"
            })

    # Check 2: @Entity without @Table (optional but common)
    if '@Entity' in content and '@Table' not in content:
        entity_line = find_annotation_line(lines, '@Entity')
        issues.append({
            "file": file_path,
            "line": entity_line,
            "issue": "@Entity without @Table - table name will be inferred from class name",
            "severity": "low",
            "pattern": "entity_no_table",
            "snippet": get_snippet(lines, entity_line) if entity_line else None,
            "suggestion": "Consider adding @Table(name = \"...\") for explicit table mapping"
        })

    # Check 3: Missing @Override on overridden methods
    if extends_class or implements:
        # Look for common override methods without @Override
        override_candidates = ['toString', 'equals', 'hashCode', 'clone', 'compareTo']
        for method in override_candidates:
            pattern = rf'public\s+(?:\w+\s+)?{method}\s*\('
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    # Check if @Override is present in previous lines
                    context_start = max(0, i - 3)
                    context = '\n'.join(lines[context_start:i])
                    if '@Override' not in context:
                        issues.append({
                            "file": file_path,
                            "line": i,
                            "issue": f"Method '{method}' should have @Override annotation",
                            "severity": "low",
                            "pattern": "missing_override",
                            "snippet": get_snippet(lines, i),
                            "suggestion": "Add @Override annotation for overridden methods"
                        })

    # Check 4: @RestController without mapping
    if '@RestController' in content:
        if '@RequestMapping' not in content and '@GetMapping' not in content and '@PostMapping' not in content:
            controller_line = find_annotation_line(lines, '@RestController')
            issues.append({
                "file": file_path,
                "line": controller_line,
                "issue": "@RestController without any request mapping",
                "severity": "medium",
                "pattern": "controller_no_mapping",
                "snippet": get_snippet(lines, controller_line) if controller_line else None,
                "suggestion": "Add @RequestMapping to define the base path for this controller"
            })

    # Check 5: @Column with nullable=false but field not validated
    column_pattern = r'@Column\([^)]*nullable\s*=\s*false[^)]*\)'
    for i, line in enumerate(lines, 1):
        if re.search(column_pattern, line):
            # Check next few lines for @NotNull/@NotBlank
            context = '\n'.join(lines[i:min(i + 3, len(lines))])
            if '@NotNull' not in context and '@NotBlank' not in context and '@NotEmpty' not in context:
                issues.append({
                    "file": file_path,
                    "line": i,
                    "issue": "@Column(nullable=false) without validation annotation",
                    "severity": "low",
                    "pattern": "column_no_validation",
                    "snippet": get_snippet(lines, i),
                    "suggestion": "Consider adding @NotNull or @NotBlank for input validation"
                })

    # Check 6: @Transactional issues
    is_service = '@Service' in content
    if is_service:
        # Check for public methods that modify data without @Transactional
        method_pattern = r'public\s+(?:void|boolean|int|\w+)\s+(\w+)\s*\([^)]*\)'
        modifying_prefixes = ['save', 'update', 'delete', 'create', 'add', 'remove', 'set', 'insert']

        for i, line in enumerate(lines, 1):
            match = re.search(method_pattern, line)
            if match:
                method_name = match.group(1)
                if any(method_name.lower().startswith(prefix) for prefix in modifying_prefixes):
                    # Check for @Transactional
                    context_start = max(0, i - 3)
                    context = '\n'.join(lines[context_start:i])
                    if '@Transactional' not in context and '@Transactional' not in content.split(f'public')[0]:
                        issues.append({
                            "file": file_path,
                            "line": i,
                            "issue": f"Data-modifying method '{method_name}' may need @Transactional",
                            "severity": "medium",
                            "pattern": "missing_transactional",
                            "snippet": get_snippet(lines, i),
                            "suggestion": "Add @Transactional to ensure database operations are atomic"
                        })

    # Check 7: @Autowired in non-bean class
    if '@Autowired' in content or '@Inject' in content:
        bean_annotations = ['@Component', '@Service', '@Repository', '@Controller', '@RestController', '@Configuration']
        is_bean = any(ann in content for ann in bean_annotations)
        if not is_bean:
            autowired_line = find_annotation_line(lines, '@Autowired') or find_annotation_line(lines, '@Inject')
            class_line = find_class_line(lines)
            issues.append({
                "file": file_path,
                "line": class_line or autowired_line,
                "issue": "Class uses @Autowired but is not a Spring-managed bean",
                "severity": "high",
                "pattern": "autowired_non_bean",
                "snippet": get_snippet(lines, class_line or autowired_line or 1),
                "suggestion": "Add @Component, @Service, or @Repository to make this class a Spring bean"
            })

    # Check 8: @Value without default
    value_pattern = r'@Value\("\$\{([^}]+)\}"\)'
    for i, line in enumerate(lines, 1):
        match = re.search(value_pattern, line)
        if match:
            property_expr = match.group(1)
            if ':' not in property_expr:  # No default value
                issues.append({
                    "file": file_path,
                    "line": i,
                    "issue": f"@Value for '{property_expr}' has no default - will fail if property is missing",
                    "severity": "medium",
                    "pattern": "value_no_default",
                    "snippet": get_snippet(lines, i),
                    "suggestion": "Consider adding a default: @Value(\"${property:defaultValue}\")"
                })

    # Check 9: @PathVariable/@RequestParam without required=false and no default
    for i, line in enumerate(lines, 1):
        if '@PathVariable' in line or '@RequestParam' in line:
            if 'required' not in line and 'defaultValue' not in line:
                # Check if parameter type is Optional
                if 'Optional' not in line:
                    param_match = re.search(r'@(PathVariable|RequestParam)\s+\w+\s+(\w+)', line)
                    if param_match:
                        param_name = param_match.group(2)
                        issues.append({
                            "file": file_path,
                            "line": i,
                            "issue": f"Parameter '{param_name}' is required by default",
                            "severity": "low",
                            "pattern": "param_required",
                            "snippet": get_snippet(lines, i),
                            "suggestion": "Consider adding required=false or defaultValue for optional parameters"
                        })

    return issues


def find_annotation_line(lines: List[str], annotation: str) -> Optional[int]:
    """Find the line number where an annotation appears.

    Args:
        lines: List of file lines
        annotation: Annotation to find

    Returns:
        Line number (1-indexed) or None
    """
    for i, line in enumerate(lines, 1):
        if annotation in line:
            return i
    return None


def find_class_line(lines: List[str]) -> Optional[int]:
    """Find the line number where the class is declared.

    Args:
        lines: List of file lines

    Returns:
        Line number (1-indexed) or None
    """
    for i, line in enumerate(lines, 1):
        if re.search(r'(?:public\s+)?(?:abstract\s+)?class\s+\w+', line):
            return i
    return None


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
    name="check_annotations",
    description="Check for missing or incorrect Spring/JPA annotations. Detects: missing @Override, @Entity without @Id, @Service without @Transactional, @RestController without mappings.",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Optional: specific file to check. If not provided, checks all Java files."
        }
    }
)


def register():
    """Register this tool with the registry."""
    register_tool("check_annotations", check_annotations, TOOL_DEFINITION)
