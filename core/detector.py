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
    import re

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

    # Try LLM detection first
    try:
        is_springboot, version = client.check_springboot(content, build_type)
        return is_springboot, version
    except Exception as e:
        error_msg = str(e)
        # Check if it's an auth error - raise so caller can handle
        if "401" in error_msg or "Unauthorized" in error_msg:
            raise Exception("API key is invalid. Please run: nix config <your_groq_api_key>\nGet your key at: https://console.groq.com/keys")

        # Fallback to local detection if LLM fails for other reasons
        print(f"LLM unavailable, using local detection...")

    # Local detection fallback
    content_lower = content.lower()

    # Check for Spring Boot markers
    spring_boot_markers = [
        'spring-boot-starter',
        'org.springframework.boot',
        'spring-boot-maven-plugin',
        'spring-boot-gradle-plugin',
        'springBootVersion',
    ]

    is_spring_boot = any(marker.lower() in content_lower for marker in spring_boot_markers)

    if not is_spring_boot:
        return False, None

    # Try to extract version locally
    version = "Unknown"

    # Maven version patterns
    version_patterns = [
        r'<version>(\d+\.\d+\.\d+)</version>',
        r'spring-boot-starter-parent.*?<version>(\d+\.\d+\.\d+)',
        r'springBootVersion\s*=\s*[\'"](\d+\.\d+\.\d+)[\'"]',
    ]

    for pattern in version_patterns:
        match = re.search(pattern, content)
        if match:
            version = match.group(1)
            break

    return True, version


def count_java_files():
    """Count total .java files in project"""
    count = 0
    project_root = os.getcwd()

    for root, dirs, files in os.walk(project_root):
        # Skip .nix folder
        if '.nix' in root:
            continue
        for file in files:
            if file.endswith('.java'):
                count += 1

    return count