"""Spring configuration analyzer for application.properties/yml files."""

import os
import re
from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def analyze_configuration():
    """
    Analyze Spring Boot configuration files.

    Returns:
        dict with all configuration properties, profiles, and settings
    """
    if not is_quiet():
        print_tool_start("analyze_configuration")

    project_root = os.getcwd()
    config_files = find_config_files(project_root)

    if not config_files:
        if not is_quiet():
            print_tool_result("No config files found")
        return {
            "error": "No application.properties or application.yml found",
            "searched": [
                "application.properties",
                "application.yml",
                "application.yaml",
                "src/main/resources/application.*"
            ],
            "suggestion": "Make sure you're in a Spring Boot project"
        }

    all_configs = []
    all_properties = {}
    profiles = set()

    for config_file in config_files:
        config = parse_config_file(config_file)
        all_configs.append(config)

        # Merge properties
        for key, value in config.get("properties", {}).items():
            all_properties[key] = value

        # Collect profiles
        if config.get("profile"):
            profiles.add(config["profile"])

    # Categorize properties
    categories = categorize_properties(all_properties)

    if not is_quiet():
        print_tool_result(f"{len(all_properties)} properties in {len(config_files)} file(s)")
        # Show some properties
        for key, value in list(all_properties.items())[:5]:
            # Truncate long values
            val_str = str(value)[:30] + "..." if len(str(value)) > 30 else str(value)
            print_tool_result(f"  {key}={val_str}")
        if len(all_properties) > 5:
            print_tool_result(f"  ... and {len(all_properties) - 5} more")

    return {
        "summary": f"Found {len(all_properties)} properties in {len(config_files)} files",
        "file_count": len(config_files),
        "property_count": len(all_properties),
        "files": [c["file"] for c in all_configs],
        "profiles": list(profiles),
        "properties": all_properties,
        "categories": categories,
        "configs": all_configs
    }


def find_config_files(project_root):
    """Find all Spring configuration files."""
    config_files = []

    # Common locations
    locations = [
        "",
        "src/main/resources",
        "config",
        "src/main/resources/config"
    ]

    patterns = [
        "application.properties",
        "application.yml",
        "application.yaml",
        "application-*.properties",
        "application-*.yml",
        "application-*.yaml",
        "bootstrap.properties",
        "bootstrap.yml"
    ]

    import glob as glob_module

    for loc in locations:
        base = os.path.join(project_root, loc) if loc else project_root
        if not os.path.isdir(base):
            continue

        for pattern in patterns:
            matches = glob_module.glob(os.path.join(base, pattern))
            config_files.extend(matches)

    # Remove duplicates
    return list(set(config_files))


def parse_config_file(file_path):
    """Parse a configuration file (properties or yaml)."""
    filename = os.path.basename(file_path)
    rel_path = os.path.relpath(file_path, os.getcwd())

    # Detect profile from filename
    profile = None
    profile_match = re.search(r'application-(\w+)\.(properties|ya?ml)', filename)
    if profile_match:
        profile = profile_match.group(1)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return {
            "file": rel_path,
            "profile": profile,
            "error": str(e),
            "properties": {}
        }

    if filename.endswith('.properties'):
        properties = parse_properties_file(content)
    else:
        properties = parse_yaml_file(content)

    return {
        "file": rel_path,
        "profile": profile,
        "format": "properties" if filename.endswith('.properties') else "yaml",
        "properties": properties,
        "line_count": content.count('\n') + 1
    }


def parse_properties_file(content):
    """Parse Java properties file format."""
    properties = {}

    for line in content.split('\n'):
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith('#') or line.startswith('!'):
            continue

        # Handle key=value or key:value
        if '=' in line:
            key, _, value = line.partition('=')
        elif ':' in line:
            key, _, value = line.partition(':')
        else:
            continue

        key = key.strip()
        value = value.strip()

        # Handle multi-line values (ending with \)
        # For simplicity, we just take the first line

        properties[key] = value

    return properties


def parse_yaml_file(content):
    """Parse YAML file (simplified parser without external dependencies)."""
    properties = {}
    current_path = []
    indent_stack = [0]

    for line in content.split('\n'):
        # Skip comments and empty lines
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Calculate indent
        indent = len(line) - len(line.lstrip())

        # Handle indent changes
        while indent_stack and indent <= indent_stack[-1] and len(indent_stack) > 1:
            indent_stack.pop()
            if current_path:
                current_path.pop()

        # Parse key: value
        if ':' in stripped:
            key, _, value = stripped.partition(':')
            key = key.strip()
            value = value.strip()

            if value:
                # It's a key-value pair
                full_key = '.'.join(current_path + [key])
                properties[full_key] = value
            else:
                # It's a parent key
                current_path.append(key)
                indent_stack.append(indent)

    return properties


def categorize_properties(properties):
    """Categorize properties by their prefix."""
    categories = {
        "server": [],
        "spring.datasource": [],
        "spring.jpa": [],
        "spring.security": [],
        "logging": [],
        "management": [],
        "custom": []
    }

    for key, value in properties.items():
        categorized = False
        for category in categories:
            if category != "custom" and key.startswith(category):
                categories[category].append({"key": key, "value": value})
                categorized = True
                break

        if not categorized:
            categories["custom"].append({"key": key, "value": value})

    # Remove empty categories
    return {k: v for k, v in categories.items() if v}


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="analyze_configuration",
    description="Analyze Spring Boot configuration files (application.properties, application.yml). Returns all properties, profiles, and categorized settings."
)


def register():
    """Register this tool with the registry."""
    register_tool("analyze_configuration", analyze_configuration, TOOL_DEFINITION)
