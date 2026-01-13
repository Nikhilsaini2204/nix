import os


def is_java_file(filename):
    """Check if file is a Java file"""
    return filename.endswith('.java')


def walk_directory(directory, skip_folders=None):
    """
    Walk through directory and yield all files
    skip_folders: list of folder names to skip
    """
    if skip_folders is None:
        skip_folders = ['.nix', '.git', 'target', 'build', 'node_modules']

    for root, dirs, files in os.walk(directory):
        # Remove skip folders from dirs to prevent walking into them
        dirs[:] = [d for d in dirs if d not in skip_folders]

        for file in files:
            yield os.path.join(root, file)