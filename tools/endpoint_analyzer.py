"""REST API endpoint analyzer for Spring Boot projects."""

import os
import re
from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def analyze_endpoints():
    """
    Find all REST API endpoints in the project.

    Returns:
        dict with all endpoints, their HTTP methods, and paths
    """
    if not is_quiet():
        print_tool_start("analyze_endpoints")

    java_files = find_java_files()

    if not java_files:
        if not is_quiet():
            print_tool_result("No Java files found")
        return {
            "error": "No Java files found in this directory",
            "suggestion": "Make sure you're in a Spring Boot project"
        }

    endpoints = []
    controllers = []

    for file_path in java_files:
        file_endpoints, controller_info = extract_endpoints_from_file(file_path)
        if file_endpoints:
            endpoints.extend(file_endpoints)
        if controller_info:
            controllers.append(controller_info)

    if not is_quiet():
        print_tool_result(f"{len(endpoints)} endpoints in {len(controllers)} controllers")
        # Show endpoints
        for ep in endpoints[:6]:
            method = ep.get('method', 'GET')
            path = ep.get('path', '/')
            handler = ep.get('handler', '')
            print_tool_result(f"  {method:6} {path} → {handler}()")
        if len(endpoints) > 6:
            print_tool_result(f"  ... and {len(endpoints) - 6} more")

    # Group by controller
    by_controller = {}
    for ep in endpoints:
        ctrl = ep.get("controller", "Unknown")
        if ctrl not in by_controller:
            by_controller[ctrl] = []
        by_controller[ctrl].append(ep)

    # Group by HTTP method
    by_method = {}
    for ep in endpoints:
        method = ep.get("method", "GET")
        if method not in by_method:
            by_method[method] = 0
        by_method[method] += 1

    return {
        "summary": f"Found {len(endpoints)} endpoints in {len(controllers)} controllers",
        "endpoint_count": len(endpoints),
        "controller_count": len(controllers),
        "controllers": controllers,
        "endpoints": endpoints,
        "by_method": by_method,
        "by_controller": by_controller
    }


def find_java_files():
    """Find all Java files in the project."""
    project_root = os.getcwd()
    java_files = []

    skip_dirs = {'.git', '.nix', 'target', 'build', 'node_modules', '.idea', '__pycache__'}

    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            if file.endswith('.java'):
                java_files.append(os.path.join(root, file))

    return java_files


def extract_endpoints_from_file(file_path):
    """
    Extract REST endpoints from a Java file.

    Returns:
        (endpoints_list, controller_info)
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return [], None

    # Check if it's a controller
    is_rest_controller = '@RestController' in content
    is_controller = '@Controller' in content

    if not (is_rest_controller or is_controller):
        return [], None

    # Extract class name
    class_match = re.search(r'class\s+(\w+)', content)
    class_name = class_match.group(1) if class_match else "Unknown"

    # Get base path from class-level @RequestMapping
    base_path = ""
    class_mapping = re.search(
        r'@RequestMapping\s*\(\s*["\']([^"\']+)["\']',
        content[:content.find('class ') if 'class ' in content else len(content)]
    )
    if class_mapping:
        base_path = class_mapping.group(1)

    # Also check for @RequestMapping with value=
    if not base_path:
        class_mapping = re.search(
            r'@RequestMapping\s*\([^)]*value\s*=\s*["\']([^"\']+)["\']',
            content[:content.find('class ') if 'class ' in content else len(content)]
        )
        if class_mapping:
            base_path = class_mapping.group(1)

    controller_info = {
        "name": class_name,
        "type": "RestController" if is_rest_controller else "Controller",
        "base_path": base_path,
        "file": os.path.relpath(file_path, os.getcwd())
    }

    endpoints = []

    # Patterns for different mapping annotations
    mapping_patterns = [
        (r'@GetMapping\s*\(\s*["\']([^"\']*)["\']', 'GET'),
        (r'@GetMapping\s*\(\s*value\s*=\s*["\']([^"\']*)["\']', 'GET'),
        (r'@GetMapping\s*(?:\(\s*\))?', 'GET'),  # @GetMapping without path
        (r'@PostMapping\s*\(\s*["\']([^"\']*)["\']', 'POST'),
        (r'@PostMapping\s*\(\s*value\s*=\s*["\']([^"\']*)["\']', 'POST'),
        (r'@PostMapping\s*(?:\(\s*\))?', 'POST'),
        (r'@PutMapping\s*\(\s*["\']([^"\']*)["\']', 'PUT'),
        (r'@PutMapping\s*\(\s*value\s*=\s*["\']([^"\']*)["\']', 'PUT'),
        (r'@PutMapping\s*(?:\(\s*\))?', 'PUT'),
        (r'@DeleteMapping\s*\(\s*["\']([^"\']*)["\']', 'DELETE'),
        (r'@DeleteMapping\s*\(\s*value\s*=\s*["\']([^"\']*)["\']', 'DELETE'),
        (r'@DeleteMapping\s*(?:\(\s*\))?', 'DELETE'),
        (r'@PatchMapping\s*\(\s*["\']([^"\']*)["\']', 'PATCH'),
        (r'@PatchMapping\s*\(\s*value\s*=\s*["\']([^"\']*)["\']', 'PATCH'),
        (r'@PatchMapping\s*(?:\(\s*\))?', 'PATCH'),
    ]

    # Also handle @RequestMapping with method
    request_mapping_pattern = r'@RequestMapping\s*\([^)]*method\s*=\s*RequestMethod\.(\w+)[^)]*["\']([^"\']*)["\']'

    for match in re.finditer(request_mapping_pattern, content):
        method = match.group(1)
        path = match.group(2)
        full_path = (base_path + path).replace("//", "/")

        # Find method name
        method_name = find_method_name(content, match.end())

        endpoints.append({
            "method": method,
            "path": full_path or "/",
            "controller": class_name,
            "handler": method_name,
            "file": os.path.relpath(file_path, os.getcwd())
        })

    # Process other mapping patterns
    for pattern, http_method in mapping_patterns:
        for match in re.finditer(pattern, content):
            path = match.group(1) if match.lastindex else ""
            full_path = (base_path + "/" + path).replace("//", "/")
            if full_path and not full_path.startswith("/"):
                full_path = "/" + full_path

            method_name = find_method_name(content, match.end())

            endpoints.append({
                "method": http_method,
                "path": full_path or "/",
                "controller": class_name,
                "handler": method_name,
                "file": os.path.relpath(file_path, os.getcwd())
            })

    # Remove duplicates
    seen = set()
    unique_endpoints = []
    for ep in endpoints:
        key = (ep["method"], ep["path"], ep["handler"])
        if key not in seen:
            seen.add(key)
            unique_endpoints.append(ep)

    return unique_endpoints, controller_info


def find_method_name(content, position):
    """Find the method name after a mapping annotation."""
    # Look for method signature after the annotation
    remaining = content[position:position + 500]

    # Pattern: public/private/protected ReturnType methodName(
    method_match = re.search(
        r'(?:public|private|protected)?\s*(?:[\w<>\[\],\s]+)\s+(\w+)\s*\(',
        remaining
    )

    if method_match:
        return method_match.group(1)

    return "unknown"


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="analyze_endpoints",
    description="Find all REST API endpoints in the Spring Boot project. Returns HTTP methods, paths, controllers, and handler methods."
)


def register():
    """Register this tool with the registry."""
    register_tool("analyze_endpoints", analyze_endpoints, TOOL_DEFINITION)
