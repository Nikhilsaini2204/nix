"""JPA Entity analyzer for finding entities and their relationships."""

import os
import re
from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def analyze_entities():
    """
    Find all JPA entities in the project.

    Returns:
        dict with all entities, their fields, and relationships
    """
    if not is_quiet():
        print_tool_start("analyze_entities")

    java_files = find_java_files()

    if not java_files:
        if not is_quiet():
            print_tool_result("No Java files found")
        return {
            "error": "No Java files found in this directory",
            "suggestion": "Make sure you're in a Spring Boot project"
        }

    entities = []

    for file_path in java_files:
        entity = extract_entity_from_file(file_path)
        if entity:
            entities.append(entity)

    # Build relationship summary
    relationships = []
    for entity in entities:
        for rel in entity.get("relationships", []):
            relationships.append({
                "from": entity["name"],
                "to": rel["target"],
                "type": rel["type"]
            })

    if not is_quiet():
        print_tool_result(f"{len(entities)} entities with {len(relationships)} relationships")
        # Show entities with details
        for entity in entities[:5]:
            name = entity.get('name', '')
            table = entity.get('table', '')
            field_count = entity.get('field_count', 0)
            rel_count = entity.get('relationship_count', 0)
            print_tool_result(f"  {name} → {table} ({field_count} fields, {rel_count} relations)")
        if len(entities) > 5:
            print_tool_result(f"  ... and {len(entities) - 5} more")
        # Show relationships
        if relationships:
            print_tool_result(f"  Relationships:")
            for rel in relationships[:4]:
                print_tool_result(f"    {rel['from']} --{rel['type']}--> {rel['to']}")
            if len(relationships) > 4:
                print_tool_result(f"    ... and {len(relationships) - 4} more")

    return {
        "summary": f"Found {len(entities)} JPA entities with {len(relationships)} relationships",
        "entity_count": len(entities),
        "relationship_count": len(relationships),
        "entities": entities,
        "relationships": relationships
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


def extract_entity_from_file(file_path):
    """Extract JPA entity information from a Java file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return None

    # Check if it's an entity
    if '@Entity' not in content:
        return None

    rel_path = os.path.relpath(file_path, os.getcwd())

    # Extract class name
    class_match = re.search(r'class\s+(\w+)', content)
    if not class_match:
        return None

    class_name = class_match.group(1)

    # Get table name
    table_name = class_name.lower()  # default
    table_match = re.search(r'@Table\s*\([^)]*name\s*=\s*["\'](\w+)["\']', content)
    if table_match:
        table_name = table_match.group(1)

    # Find fields
    fields = extract_fields(content)

    # Find relationships
    relationships = extract_relationships(content)

    # Find ID field
    id_field = None
    for field in fields:
        if field.get("is_id"):
            id_field = field
            break

    return {
        "name": class_name,
        "table": table_name,
        "file": rel_path,
        "id_field": id_field,
        "fields": fields,
        "relationships": relationships,
        "field_count": len(fields),
        "relationship_count": len(relationships)
    }


def extract_fields(content):
    """Extract entity fields with their annotations."""
    fields = []

    # Pattern to match field declarations with annotations
    # This is a simplified pattern - real Java parsing would be more complex

    # Split content by field-like patterns
    lines = content.split('\n')
    current_annotations = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Collect annotations
        if stripped.startswith('@'):
            annotation_match = re.match(r'@(\w+)', stripped)
            if annotation_match:
                current_annotations.append(annotation_match.group(1))

        # Look for field declarations
        field_match = re.match(
            r'(?:private|protected|public)\s+(\w+(?:<[^>]+>)?)\s+(\w+)\s*[;=]',
            stripped
        )

        if field_match:
            field_type = field_match.group(1)
            field_name = field_match.group(2)

            field_info = {
                "name": field_name,
                "type": field_type,
                "annotations": current_annotations.copy(),
                "is_id": "Id" in current_annotations,
                "is_nullable": "Column" not in str(current_annotations) or "nullable" not in stripped.lower(),
            }

            # Check for column name
            for j in range(max(0, i - 5), i):
                col_match = re.search(r'@Column\s*\([^)]*name\s*=\s*["\'](\w+)["\']', lines[j])
                if col_match:
                    field_info["column"] = col_match.group(1)
                    break

            fields.append(field_info)
            current_annotations = []
        elif not stripped.startswith('@') and stripped:
            current_annotations = []

    return fields


def extract_relationships(content):
    """Extract entity relationships."""
    relationships = []

    # Relationship annotations
    rel_patterns = [
        (r'@OneToMany[^)]*\)', 'OneToMany'),
        (r'@ManyToOne[^)]*\)', 'ManyToOne'),
        (r'@OneToOne[^)]*\)', 'OneToOne'),
        (r'@ManyToMany[^)]*\)', 'ManyToMany'),
    ]

    for pattern, rel_type in rel_patterns:
        for match in re.finditer(pattern, content):
            # Find the field after this annotation
            remaining = content[match.end():match.end() + 200]

            field_match = re.search(
                r'(?:private|protected|public)\s+(?:List<|Set<)?(\w+)>?\s+(\w+)',
                remaining
            )

            if field_match:
                target_type = field_match.group(1)
                field_name = field_match.group(2)

                relationships.append({
                    "type": rel_type,
                    "target": target_type,
                    "field": field_name
                })

    return relationships


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="analyze_entities",
    description="Find all JPA entities in the project. Returns entity names, table mappings, fields, and relationships (OneToMany, ManyToOne, etc.)."
)


def register():
    """Register this tool with the registry."""
    register_tool("analyze_entities", analyze_entities, TOOL_DEFINITION)
