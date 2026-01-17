"""Project explorer tool - shows entire project structure in one call."""

import os
from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def explore_project(max_depth=5):
    """
    Explore entire project structure in one call.

    Args:
        max_depth: Maximum directory depth to explore (default: 5)

    Returns:
        dict with complete project tree
    """
    project_root = os.getcwd()

    if not is_quiet():
        print_tool_start("explore_project")

    skip_dirs = {
        '.nix', '.git', 'target', 'build', 'node_modules',
        '.idea', '__pycache__', '.gradle', 'bin', 'out',
        '.settings', '.mvn', 'logs'
    }

    skip_extensions = {'.class', '.jar', '.war', '.pyc', '.pyo'}

    tree = []
    file_count = 0
    dir_count = 0

    def build_tree(path, prefix="", depth=0):
        nonlocal file_count, dir_count

        if depth > max_depth:
            return

        try:
            items = sorted(os.listdir(path))
        except PermissionError:
            return

        # Separate dirs and files
        dirs = []
        files = []

        for item in items:
            if item.startswith('.'):
                continue

            item_path = os.path.join(path, item)

            if os.path.isdir(item_path):
                if item not in skip_dirs:
                    dirs.append(item)
            else:
                ext = os.path.splitext(item)[1]
                if ext not in skip_extensions:
                    files.append(item)

        # Add directories
        for i, d in enumerate(dirs):
            is_last_dir = (i == len(dirs) - 1) and len(files) == 0
            connector = "└── " if is_last_dir else "├── "
            tree.append(f"{prefix}{connector}{d}/")
            dir_count += 1

            new_prefix = prefix + ("    " if is_last_dir else "│   ")
            build_tree(os.path.join(path, d), new_prefix, depth + 1)

        # Add files
        for i, f in enumerate(files):
            is_last = i == len(files) - 1
            connector = "└── " if is_last else "├── "
            tree.append(f"{prefix}{connector}{f}")
            file_count += 1

    # Get project name
    project_name = os.path.basename(project_root)
    tree.append(f"{project_name}/")

    build_tree(project_root, "", 0)

    if not is_quiet():
        print_tool_result(f"{dir_count} directories, {file_count} files")
        # Show tree preview (first 8 lines)
        tree_lines = tree[:8]
        for line in tree_lines:
            print_tool_result(f"  {line}")
        if len(tree) > 8:
            print_tool_result(f"  ... and {len(tree) - 8} more")

    # Build text representation
    tree_text = "\n".join(tree)

    return {
        "summary": f"Project '{project_name}' has {dir_count} directories and {file_count} files",
        "tree": tree_text,
        "directory_count": dir_count,
        "file_count": file_count
    }


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="explore_project",
    description="THE tool for project structure questions. Shows complete directory tree in ONE call. Use when user asks about: project structure, folders, files, what's in the project, directory tree, overview."
)


def register():
    """Register this tool with the registry."""
    register_tool("explore_project", explore_project, TOOL_DEFINITION)
