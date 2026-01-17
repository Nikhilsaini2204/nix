"""File reader tool for reading project files."""

import os
import glob as glob_module
from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def read_file(file_path=None, pattern=None):
    """
    Read a file from the project.

    Args:
        file_path: Specific file path to read (e.g., "pom.xml", "src/main/java/App.java")
        pattern: Glob pattern to find files (e.g., "*.xml", "**/*Controller.java")

    Returns:
        dict with file content or error
    """
    project_root = os.getcwd()

    if not is_quiet():
        print_tool_start("read_file")

    # If pattern provided, find matching files
    if pattern:
        matches = glob_module.glob(os.path.join(project_root, pattern), recursive=True)

        # Filter out .nix, .git, target, build directories
        skip_dirs = {'.nix', '.git', 'target', 'build', 'node_modules', '.idea', '__pycache__'}
        matches = [m for m in matches if not any(skip in m for skip in skip_dirs)]

        if not matches:
            if not is_quiet():
                print_tool_result(f"No files found matching: {pattern}")
            return {
                "error": f"No files found matching pattern: {pattern}",
                "suggestion": "Try a different pattern like '*.java' or '**/*.xml'"
            }

        if not is_quiet():
            print_tool_result(f"Found {len(matches)} file(s)")

        # If multiple matches, return list
        if len(matches) > 1:
            relative_paths = [os.path.relpath(m, project_root) for m in matches]
            return {
                "summary": f"Found {len(matches)} files matching '{pattern}'",
                "files": relative_paths,
                "hint": "Specify a file path to read its contents"
            }

        # Single match, read it
        file_path = matches[0]

    # Read specific file
    if file_path:
        # Handle relative paths
        if not os.path.isabs(file_path):
            full_path = os.path.join(project_root, file_path)
        else:
            full_path = file_path

        # Try to find file if exact path doesn't exist
        if not os.path.exists(full_path):
            # Search for file by name
            filename = os.path.basename(file_path)
            search_pattern = f"**/{filename}"
            matches = glob_module.glob(os.path.join(project_root, search_pattern), recursive=True)

            # Filter out unwanted directories
            skip_dirs = {'.nix', '.git', 'target', 'build', 'node_modules', '.idea', '__pycache__'}
            matches = [m for m in matches if not any(skip in m for skip in skip_dirs)]

            if matches:
                full_path = matches[0]
            else:
                if not is_quiet():
                    print_tool_result(f"File not found: {file_path}")
                return {
                    "error": f"File not found: {file_path}",
                    "suggestion": "Check the file path or use a pattern like '**/*.java' to search"
                }

        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Limit content size for LLM context
            max_chars = 10000
            truncated = False
            if len(content) > max_chars:
                content = content[:max_chars]
                truncated = True

            line_count = content.count('\n') + 1
            rel_path = os.path.relpath(full_path, project_root)

            if not is_quiet():
                print_tool_result(f"{rel_path} ({line_count} lines)")

            return {
                "summary": f"Read {os.path.basename(full_path)} ({line_count} lines)",
                "file_path": rel_path,
                "content": content,
                "truncated": truncated,
                "truncated_message": "Content truncated to 10000 characters" if truncated else None
            }

        except Exception as e:
            if not is_quiet():
                print_tool_result(f"Error: {str(e)}")
            return {
                "error": f"Failed to read file: {str(e)}"
            }

    # No file_path or pattern provided
    return {
        "error": "Please specify a file_path or pattern",
        "examples": [
            "read_file(file_path='pom.xml')",
            "read_file(pattern='**/*Controller.java')"
        ]
    }


def list_files(directory=None, pattern=None):
    """
    List files in the project.

    Args:
        directory: Directory to list (default: project root)
        pattern: Optional glob pattern to filter

    Returns:
        dict with file listing
    """
    project_root = os.getcwd()

    if not is_quiet():
        print_tool_start("list_files")

    if directory:
        target_dir = os.path.join(project_root, directory)
    else:
        target_dir = project_root

    if not os.path.isdir(target_dir):
        if not is_quiet():
            print_tool_result(f"Directory not found: {directory}")
        return {
            "error": f"Directory not found: {directory}"
        }

    skip_dirs = {'.nix', '.git', 'target', 'build', 'node_modules', '.idea', '__pycache__', '.gradle'}

    files = []
    dirs = []

    try:
        for item in os.listdir(target_dir):
            if item in skip_dirs or item.startswith('.'):
                continue

            item_path = os.path.join(target_dir, item)
            if os.path.isdir(item_path):
                dirs.append(item + "/")
            else:
                if pattern:
                    if glob_module.fnmatch.fnmatch(item, pattern):
                        files.append(item)
                else:
                    files.append(item)

        dirs.sort()
        files.sort()

        if not is_quiet():
            print_tool_result(f"{len(dirs)} directories, {len(files)} files")

        return {
            "summary": f"Found {len(dirs)} directories and {len(files)} files",
            "directory": directory or ".",
            "directories": dirs,
            "files": files
        }

    except Exception as e:
        if not is_quiet():
            print_tool_result(f"Error: {str(e)}")
        return {
            "error": f"Failed to list directory: {str(e)}"
        }


# Tool definitions
READ_FILE_DEFINITION = create_tool_definition(
    name="read_file",
    description="Read the raw content of a SPECIFIC file when user wants to see actual code or content. NOT for analysis - use analyze_* tools for that. Only use when user explicitly asks to see/read a specific file.",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the file to read (e.g., 'src/main/java/Application.java')"
        },
        "pattern": {
            "type": "string",
            "description": "Glob pattern to search for files (e.g., '**/*Controller.java')"
        }
    }
)

LIST_FILES_DEFINITION = create_tool_definition(
    name="list_files",
    description="List files in ONE directory. For full project structure, use explore_project instead. Only use this for listing a specific subdirectory.",
    parameters={
        "directory": {
            "type": "string",
            "description": "Directory to list (default: project root). E.g., 'src/main/java'"
        },
        "pattern": {
            "type": "string",
            "description": "Optional pattern to filter files (e.g., '*.java')"
        }
    }
)


def register():
    """Register file tools with the registry."""
    register_tool("read_file", read_file, READ_FILE_DEFINITION)
    register_tool("list_files", list_files, LIST_FILES_DEFINITION)
