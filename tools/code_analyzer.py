"""Code structure analyzer tool for Spring Boot projects."""

import os
import re
from collections import defaultdict
from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def analyze_code_structure():
    """
    Analyze Java code structure in the project.

    Returns:
        dict with summary, packages, classes, and file statistics
    """
    if not is_quiet():
        print_tool_start("analyze_code_structure")

    java_files = find_java_files()

    if not java_files:
        java_files = find_java_files_recursive()

    if not java_files:
        if not is_quiet():
            print_tool_result("No Java files found")
        return {
            "error": "No Java files found in this directory. This doesn't appear to be a Java project.",
            "searched": ["src/main/java", "src/test/java", "**/*.java"],
            "suggestion": "Make sure you're in a Java project directory"
        }

    packages = extract_packages(java_files)
    classes = extract_class_info(java_files)

    # Categorize by Spring annotations
    controllers = [c for c in classes if c.get("type") == "controller"]
    services = [c for c in classes if c.get("type") == "service"]
    repositories = [c for c in classes if c.get("type") == "repository"]
    entities = [c for c in classes if c.get("type") == "entity"]
    configs = [c for c in classes if c.get("type") == "configuration"]

    if not is_quiet():
        print_tool_result(f"{len(java_files)} files, {len(packages)} packages")
        print_tool_result(f"  Controllers: {len(controllers)}, Services: {len(services)}, Repos: {len(repositories)}")
        # Show some classes
        for c in classes[:5]:
            ctype = c.get('type', 'other')
            name = c.get('name', '')
            print_tool_result(f"  [{ctype}] {name}")
        if len(classes) > 5:
            print_tool_result(f"  ... and {len(classes) - 5} more classes")

    # Build package tree for summary
    main_packages = [p for p in packages if not p.startswith("test")]
    test_packages = [p for p in packages if "test" in p.lower()]

    return {
        "summary": f"Project has {len(java_files)} Java files across {len(packages)} packages. Found {len(controllers)} controllers, {len(services)} services, {len(repositories)} repositories.",
        "file_count": len(java_files),
        "package_count": len(packages),
        "packages": list(packages),
        "components": {
            "controllers": len(controllers),
            "services": len(services),
            "repositories": len(repositories),
            "entities": len(entities),
            "configurations": len(configs),
            "other": len(classes) - len(controllers) - len(services) - len(repositories) - len(entities) - len(configs)
        },
        "classes": classes[:50],  # Limit to first 50 to avoid huge responses
        "has_more_classes": len(classes) > 50,
        "total_classes": len(classes)
    }


def find_java_files():
    """
    Find Java files in standard Maven/Gradle source directories.

    Returns:
        List of file paths
    """
    project_root = os.getcwd()
    java_files = []

    # Standard source directories
    source_dirs = [
        "src/main/java",
        "src/test/java",
        "src/main/kotlin",  # Sometimes mixed projects
        "app/src/main/java",  # Android-style
    ]

    for source_dir in source_dirs:
        full_path = os.path.join(project_root, source_dir)
        if os.path.isdir(full_path):
            for root, dirs, files in os.walk(full_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    if file.endswith(".java"):
                        java_files.append(os.path.join(root, file))

    return java_files


def find_java_files_recursive():
    """
    Find Java files recursively from project root.
    Used as fallback when standard directories not found.

    Returns:
        List of file paths
    """
    project_root = os.getcwd()
    java_files = []

    skip_dirs = {".git", ".nix", "target", "build", "node_modules", ".idea", ".gradle", "bin", "out"}

    for root, dirs, files in os.walk(project_root):
        # Skip common non-source directories
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))

    return java_files


def extract_packages(java_files):
    """
    Extract unique package names from Java files.

    Returns:
        Set of package names
    """
    packages = set()
    package_pattern = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)

    for file_path in java_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(2000)  # Read first 2000 chars (package is at top)

            match = package_pattern.search(content)
            if match:
                packages.add(match.group(1))
        except Exception:
            continue

    return packages


def extract_class_info(java_files):
    """
    Extract class information from Java files.

    Returns:
        List of class info dicts
    """
    classes = []

    # Patterns for class detection
    class_pattern = re.compile(
        r"(?:public\s+)?(?:abstract\s+)?(?:final\s+)?(class|interface|enum|record)\s+(\w+)",
        re.MULTILINE
    )

    # Spring annotation patterns
    annotation_patterns = {
        "controller": re.compile(r"@(RestController|Controller)\b"),
        "service": re.compile(r"@Service\b"),
        "repository": re.compile(r"@Repository\b"),
        "entity": re.compile(r"@Entity\b"),
        "configuration": re.compile(r"@Configuration\b"),
        "component": re.compile(r"@Component\b"),
    }

    for file_path in java_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Find class name
            class_match = class_pattern.search(content)
            if not class_match:
                continue

            class_type = class_match.group(1)
            class_name = class_match.group(2)

            # Determine Spring component type
            component_type = "other"
            for comp_type, pattern in annotation_patterns.items():
                if pattern.search(content):
                    component_type = comp_type
                    break

            # Get relative path
            rel_path = os.path.relpath(file_path, os.getcwd())

            # Extract package
            package_match = re.search(r"^\s*package\s+([\w.]+)\s*;", content, re.MULTILINE)
            package = package_match.group(1) if package_match else "default"

            classes.append({
                "name": class_name,
                "kind": class_type,
                "type": component_type,
                "package": package,
                "file": rel_path
            })

        except Exception:
            continue

    # Sort by component type for better readability
    type_order = {"controller": 0, "service": 1, "repository": 2, "entity": 3, "configuration": 4, "component": 5, "other": 6}
    classes.sort(key=lambda c: (type_order.get(c["type"], 99), c["name"]))

    return classes


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="analyze_code_structure",
    description="Analyze Java code structure in the Spring Boot project. Returns packages, classes, and identifies Spring components (controllers, services, repositories, entities, configurations)."
)


def register():
    """Register this tool with the registry."""
    register_tool("analyze_code_structure", analyze_code_structure, TOOL_DEFINITION)
