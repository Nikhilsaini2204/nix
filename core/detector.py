import os
from llm import client


def find_build_file():
    """Find pom.xml or build.gradle in current directory"""
    project_root = os.getcwd()

    # Check for pom.xml first (Maven)
    pom_path = os.path.join(project_root, "pom.xml")
    if os.path.exists(pom_path):
        return pom_path, "maven"

    # Check for build.gradle (Gradle)
    gradle_path = os.path.join(project_root, "build.gradle")
    if os.path.exists(gradle_path):
        return gradle_path, "gradle"

    return None, None


def read_build_file(file_path):
    """Read build file content"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        raise Exception(f"Failed to read build file: {str(e)}")


def is_springboot_project():
    """
    Detect if current directory is a Spring Boot project
    Returns: (is_springboot: bool, version: str or None)
    """
    # Find build file
    build_file_path, build_type = find_build_file()

    if not build_file_path:
        return False, None

    # Read build file content
    try:
        content = read_build_file(build_file_path)
    except Exception as e:
        print(f"Error reading build file: {str(e)}")
        return False, None

    # Ask LLM to confirm if Spring Boot and get version
    try:
        is_springboot, version = client.check_springboot(content, build_type)
        return is_springboot, version
    except Exception as e:
        print(f"Error checking with LLM: {str(e)}")
        return False, None


def count_java_files():
    """Count total .java files in project"""
    count = 0
    project_root = os.getcwd()

    for root, dirs, files in os.walk(project_root):
        # Skip .niks folder
        if '.niks' in root:
            continue
        for file in files:
            if file.endswith('.java'):
                count += 1

    return count