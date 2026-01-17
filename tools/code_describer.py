"""Code describer tool - parses Java files locally without using LLM tokens."""

import os
import re
from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def describe_file(file_path):
    """
    Parse and describe a Java file locally (no LLM tokens used).
    Extracts class info, methods, annotations, and structure.

    Args:
        file_path: Path to the Java file

    Returns:
        dict with parsed file structure
    """
    if not is_quiet():
        print_tool_start("describe_file")

    project_root = os.getcwd()

    # Find the file
    if not os.path.isabs(file_path):
        full_path = os.path.join(project_root, file_path)
    else:
        full_path = file_path

    # Try to find file if not exists
    if not os.path.exists(full_path):
        import glob as glob_module
        filename = os.path.basename(file_path)
        matches = glob_module.glob(os.path.join(project_root, f"**/{filename}"), recursive=True)
        skip_dirs = {'.git', '.nix', 'target', 'build', 'node_modules'}
        matches = [m for m in matches if not any(skip in m for skip in skip_dirs)]

        if matches:
            full_path = matches[0]
        else:
            if not is_quiet():
                print_tool_result(f"File not found: {file_path}")
            return {"error": f"File not found: {file_path}"}

    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}

    rel_path = os.path.relpath(full_path, project_root)

    # Parse the file
    result = parse_java_file(content, rel_path)

    if not is_quiet():
        methods_count = len(result.get("methods", []))
        print_tool_result(f"{result.get('class_name', 'Unknown')} - {methods_count} methods")

    return result


def parse_java_file(content, file_path):
    """Parse Java file and extract structure."""

    # Extract package
    package_match = re.search(r'^\s*package\s+([\w.]+)\s*;', content, re.MULTILINE)
    package = package_match.group(1) if package_match else "default"

    # Extract imports
    imports = re.findall(r'^\s*import\s+([\w.*]+)\s*;', content, re.MULTILINE)

    # Extract class info
    class_match = re.search(
        r'(@\w+(?:\([^)]*\))?\s*)*(?:public\s+)?(?:abstract\s+)?(?:final\s+)?(class|interface|enum|record)\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?',
        content
    )

    if not class_match:
        return {
            "file": file_path,
            "error": "Could not parse class structure",
            "content_preview": content[:500]
        }

    class_type = class_match.group(len(class_match.groups()) - 3) or "class"
    class_name = class_match.group(len(class_match.groups()) - 2)
    extends = class_match.group(len(class_match.groups()) - 1)
    implements = class_match.group(len(class_match.groups()))

    # Extract class-level annotations
    class_annotations = extract_annotations_before(content, class_match.start())

    # Extract methods with their annotations and signatures
    methods = extract_methods(content)

    # Extract fields
    fields = extract_fields(content)

    # Build description
    description = build_description(class_name, class_type, class_annotations, methods)

    return {
        "file": file_path,
        "package": package,
        "class_name": class_name,
        "class_type": class_type,
        "annotations": class_annotations,
        "extends": extends,
        "implements": implements.replace(" ", "").split(",") if implements else [],
        "fields": fields,
        "methods": methods,
        "imports_count": len(imports),
        "description": description,
        "summary": f"{class_name} is a {class_type} with {len(methods)} methods and {len(fields)} fields"
    }


def extract_annotations_before(content, position):
    """Extract annotations appearing before a position."""
    # Look at the 500 chars before position
    before = content[max(0, position - 500):position]
    annotations = re.findall(r'@(\w+)(?:\([^)]*\))?', before)
    return annotations


def extract_methods(content):
    """Extract method signatures with annotations."""
    methods = []

    # Pattern for method with optional annotations
    # Matches: @Annotation public ReturnType methodName(params)
    method_pattern = re.compile(
        r'((?:@\w+(?:\([^)]*\))?\s+)+)?'  # Annotations (optional)
        r'(public|private|protected)\s+'  # Access modifier
        r'(?:static\s+)?(?:final\s+)?'  # Optional modifiers
        r'([\w<>\[\],]+)\s+'  # Return type
        r'(\w+)\s*'  # Method name
        r'\(([^)]*)\)',  # Parameters
        re.MULTILINE
    )

    for match in method_pattern.finditer(content):
        annotations_str = match.group(1) or ""
        # Groups: 1=annotations, 2=access, 3=return_type, 4=method_name, 5=params
        return_type = match.group(3).strip()
        method_name = match.group(4)
        params_str = match.group(5).strip()

        # Skip constructors (return type same as likely class name starting with capital)
        if return_type and return_type[0].isupper() and return_type == method_name:
            continue

        # Parse annotations
        annotations = re.findall(r'@(\w+)(?:\(([^)]*)\))?', annotations_str)
        parsed_annotations = []
        http_method = None
        path = None

        for ann_name, ann_value in annotations:
            parsed_annotations.append(ann_name)

            # Extract HTTP mapping info
            if ann_name in ['GetMapping', 'PostMapping', 'PutMapping', 'DeleteMapping', 'PatchMapping']:
                http_method = ann_name.replace('Mapping', '').upper()
                path_match = re.search(r'["\']([^"\']+)["\']', ann_value) if ann_value else None
                path = path_match.group(1) if path_match else "/"
            elif ann_name == 'RequestMapping':
                method_match = re.search(r'method\s*=\s*RequestMethod\.(\w+)', ann_value) if ann_value else None
                http_method = method_match.group(1) if method_match else "GET"
                path_match = re.search(r'["\']([^"\']+)["\']', ann_value) if ann_value else None
                path = path_match.group(1) if path_match else "/"

        # Parse parameters
        params = []
        if params_str:
            param_parts = split_params(params_str)
            for part in param_parts:
                part = part.strip()
                if part:
                    # Extract @RequestBody, @PathVariable, etc.
                    param_ann_match = re.match(r'@(\w+)(?:\([^)]*\))?\s*(.*)', part)
                    if param_ann_match:
                        param_ann = param_ann_match.group(1)
                        rest = param_ann_match.group(2).strip()
                        type_name = rest.rsplit(' ', 1)
                        if len(type_name) == 2:
                            params.append({"annotation": param_ann, "type": type_name[0], "name": type_name[1]})
                        else:
                            params.append({"annotation": param_ann, "type": rest, "name": ""})
                    else:
                        type_name = part.rsplit(' ', 1)
                        if len(type_name) == 2:
                            params.append({"type": type_name[0], "name": type_name[1]})

        method_info = {
            "name": method_name,
            "return_type": return_type,
            "annotations": parsed_annotations,
            "parameters": params
        }

        if http_method:
            method_info["http_method"] = http_method
            method_info["path"] = path

        methods.append(method_info)

    return methods


def split_params(params_str):
    """Split parameters handling generics like List<String>."""
    result = []
    current = ""
    depth = 0

    for char in params_str:
        if char == '<':
            depth += 1
        elif char == '>':
            depth -= 1
        elif char == ',' and depth == 0:
            result.append(current)
            current = ""
            continue
        current += char

    if current.strip():
        result.append(current)

    return result


def extract_fields(content):
    """Extract class fields."""
    fields = []

    # Pattern for field declarations
    field_pattern = re.compile(
        r'((?:@\w+(?:\([^)]*\))?\s*)*)'  # Annotations
        r'(?:private|protected|public)\s+'  # Access modifier
        r'(?:static\s+)?(?:final\s+)?'  # Modifiers
        r'([\w<>\[\],\s]+?)\s+'  # Type
        r'(\w+)\s*'  # Field name
        r'(?:=\s*[^;]+)?;',  # Optional initialization
        re.MULTILINE
    )

    for match in field_pattern.finditer(content):
        annotations_str = match.group(1) or ""
        field_type = match.group(2).strip()
        field_name = match.group(3)

        # Skip if it looks like a method
        if '(' in field_type or ')' in field_type:
            continue

        annotations = re.findall(r'@(\w+)', annotations_str)

        fields.append({
            "name": field_name,
            "type": field_type,
            "annotations": annotations
        })

    return fields


def build_description(class_name, class_type, annotations, methods):
    """Build a human-readable description of the class."""
    lines = []

    # Class header
    ann_str = ", ".join(f"@{a}" for a in annotations) if annotations else ""
    lines.append(f"{class_name} ({class_type}){' - ' + ann_str if ann_str else ''}")
    lines.append("")

    # Determine class purpose from annotations
    if "RestController" in annotations or "Controller" in annotations:
        lines.append("Purpose: REST API Controller")
    elif "Service" in annotations:
        lines.append("Purpose: Business Logic Service")
    elif "Repository" in annotations:
        lines.append("Purpose: Data Access Repository")
    elif "Entity" in annotations:
        lines.append("Purpose: JPA Database Entity")
    elif "Configuration" in annotations:
        lines.append("Purpose: Spring Configuration")

    # List endpoints if it's a controller
    endpoints = [m for m in methods if m.get("http_method")]
    if endpoints:
        lines.append("")
        lines.append("Endpoints:")
        for ep in endpoints:
            params = ", ".join(p.get("name", p.get("type", "")) for p in ep.get("parameters", []))
            lines.append(f"  {ep['http_method']:6} {ep.get('path', '/'):<20} → {ep['name']}({params})")

    # List other methods
    other_methods = [m for m in methods if not m.get("http_method")]
    if other_methods:
        lines.append("")
        lines.append("Methods:")
        for m in other_methods[:10]:  # Limit to 10
            params = ", ".join(p.get("name", p.get("type", "")) for p in m.get("parameters", []))
            lines.append(f"  {m['return_type']:<15} {m['name']}({params})")
        if len(other_methods) > 10:
            lines.append(f"  ... and {len(other_methods) - 10} more")

    return "\n".join(lines)


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="describe_file",
    description="Parse and describe a Java file structure WITHOUT using LLM tokens. Shows class info, methods, endpoints, annotations. Use this first to understand code structure, before asking LLM for deeper explanation.",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the Java file (e.g., 'TestController.java' or 'src/main/java/.../TestController.java')"
        }
    },
    required=["file_path"]
)


def register():
    """Register this tool with the registry."""
    register_tool("describe_file", describe_file, TOOL_DEFINITION)
