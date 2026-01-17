"""Spring Bean analyzer for finding beans and configurations."""

import os
import re
from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def analyze_beans():
    """
    Find all Spring beans in the project.

    Returns:
        dict with all beans, configurations, and their relationships
    """
    if not is_quiet():
        print_tool_start("analyze_beans")

    java_files = find_java_files()

    if not java_files:
        if not is_quiet():
            print_tool_result("No Java files found")
        return {
            "error": "No Java files found in this directory",
            "suggestion": "Make sure you're in a Spring Boot project"
        }

    beans = []
    configurations = []
    components = {
        "services": [],
        "repositories": [],
        "controllers": [],
        "components": [],
        "beans": []
    }

    for file_path in java_files:
        file_beans = extract_beans_from_file(file_path)
        beans.extend(file_beans)

        for bean in file_beans:
            bean_type = bean.get("type", "").lower()
            if bean_type == "service":
                components["services"].append(bean)
            elif bean_type == "repository":
                components["repositories"].append(bean)
            elif bean_type in ["controller", "restcontroller"]:
                components["controllers"].append(bean)
            elif bean_type == "configuration":
                configurations.append(bean)
            elif bean_type == "bean":
                components["beans"].append(bean)
            else:
                components["components"].append(bean)

    if not is_quiet():
        print_tool_result(f"{len(beans)} beans found")
        # Show beans breakdown
        print_tool_result(f"  Services: {len(components['services'])}, Repos: {len(components['repositories'])}, Controllers: {len(components['controllers'])}")
        # Show some beans
        for b in beans[:5]:
            btype = b.get('type', 'unknown')
            name = b.get('name', '')
            print_tool_result(f"  [{btype}] {name}")
        if len(beans) > 5:
            print_tool_result(f"  ... and {len(beans) - 5} more")

    return {
        "summary": f"Found {len(beans)} beans: {len(components['services'])} services, {len(components['repositories'])} repositories, {len(components['controllers'])} controllers",
        "total_beans": len(beans),
        "configurations": len(configurations),
        "components": {
            "services": len(components["services"]),
            "repositories": len(components["repositories"]),
            "controllers": len(components["controllers"]),
            "components": len(components["components"]),
            "beans": len(components["beans"])
        },
        "beans": beans,
        "details": components
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


def extract_beans_from_file(file_path):
    """Extract Spring beans from a Java file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return []

    beans = []
    rel_path = os.path.relpath(file_path, os.getcwd())

    # Bean annotations to look for
    annotations = {
        '@Service': 'Service',
        '@Repository': 'Repository',
        '@Controller': 'Controller',
        '@RestController': 'RestController',
        '@Component': 'Component',
        '@Configuration': 'Configuration',
    }

    # Check class-level annotations
    for annotation, bean_type in annotations.items():
        if annotation in content:
            class_match = re.search(r'class\s+(\w+)', content)
            if class_match:
                class_name = class_match.group(1)

                # Find dependencies (constructor injection)
                dependencies = find_dependencies(content)

                # Find @Bean methods in configurations
                bean_methods = []
                if bean_type == 'Configuration':
                    bean_methods = find_bean_methods(content)

                beans.append({
                    "name": class_name,
                    "type": bean_type,
                    "file": rel_path,
                    "dependencies": dependencies,
                    "bean_methods": bean_methods
                })
                break

    # Also find @Bean methods outside @Configuration (in other configs)
    bean_methods = find_bean_methods(content)
    for method in bean_methods:
        # Check if already added as part of configuration
        already_added = any(
            b.get("name") == method.get("class_name") and b.get("type") == "Configuration"
            for b in beans
        )
        if not already_added and method.get("method_name"):
            beans.append({
                "name": method.get("method_name"),
                "type": "Bean",
                "file": rel_path,
                "return_type": method.get("return_type"),
                "defined_in": method.get("class_name")
            })

    return beans


def find_dependencies(content):
    """Find injected dependencies from constructor."""
    dependencies = []

    # Look for constructor with @Autowired or without
    constructor_pattern = r'(?:@Autowired\s+)?(?:public\s+)?(\w+)\s*\(([^)]+)\)'

    for match in re.finditer(constructor_pattern, content):
        params = match.group(2)

        # Parse parameters
        param_pattern = r'(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)'
        for param_match in re.finditer(param_pattern, params):
            dep_type = param_match.group(1)
            dep_name = param_match.group(2)

            # Skip primitive types
            if dep_type.lower() not in ['int', 'string', 'boolean', 'long', 'double', 'float']:
                dependencies.append({
                    "type": dep_type,
                    "name": dep_name
                })

    # Also look for @Autowired fields
    field_pattern = r'@Autowired\s+(?:private|protected|public)?\s*(\w+(?:<[^>]+>)?)\s+(\w+)'
    for match in re.finditer(field_pattern, content):
        dep_type = match.group(1)
        dep_name = match.group(2)
        dependencies.append({
            "type": dep_type,
            "name": dep_name
        })

    return dependencies


def find_bean_methods(content):
    """Find @Bean annotated methods."""
    bean_methods = []

    # Get class name
    class_match = re.search(r'class\s+(\w+)', content)
    class_name = class_match.group(1) if class_match else "Unknown"

    # Pattern for @Bean methods
    bean_pattern = r'@Bean(?:\([^)]*\))?\s+(?:public\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\('

    for match in re.finditer(bean_pattern, content):
        return_type = match.group(1)
        method_name = match.group(2)

        bean_methods.append({
            "class_name": class_name,
            "method_name": method_name,
            "return_type": return_type
        })

    return bean_methods


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="analyze_beans",
    description="Find all Spring beans in the project including @Service, @Repository, @Controller, @Component, @Configuration, and @Bean methods. Shows dependencies and relationships."
)


def register():
    """Register this tool with the registry."""
    register_tool("analyze_beans", analyze_beans, TOOL_DEFINITION)
