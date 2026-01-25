"""Dependency analyzer tool for Spring Boot projects."""

import os
import re
import xml.etree.ElementTree as ET
from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def analyze_dependencies():
    """
    Analyze project dependencies from build file.

    Returns:
        dict with summary, dependencies list, and build tool info
    """
    if not is_quiet():
        print_tool_start("analyze_dependencies")

    build_file, build_type = find_build_file()

    if not build_file:
        if not is_quiet():
            print_tool_result("No build file found")
        return {
            "error": "No build file found in this directory. This doesn't appear to be a Maven or Gradle project.",
            "searched": ["pom.xml", "build.gradle", "build.gradle.kts"],
            "suggestion": "Make sure you're in a Maven or Gradle project directory"
        }

    try:
        if build_type == "maven":
            dependencies = parse_maven_dependencies(build_file)
            metadata = parse_maven_metadata(build_file)
        else:
            dependencies = parse_gradle_dependencies(build_file)
            metadata = parse_gradle_metadata(build_file)

        # Categorize dependencies
        spring_deps = [d for d in dependencies if "spring" in d.get("group", "").lower()]
        test_deps = [d for d in dependencies if d.get("scope") == "test"]

        if not is_quiet():
            print_tool_result(f"{len(dependencies)} dependencies ({len(spring_deps)} Spring, {len(test_deps)} test)")
            # Show key dependencies
            for dep in dependencies[:5]:
                name = dep.get('artifact', dep.get('name', 'unknown'))
                version = dep.get('version', '')
                print_tool_result(f"  {name}{':' + version if version else ''}")
            if len(dependencies) > 5:
                print_tool_result(f"  ... and {len(dependencies) - 5} more")

        return {
            "summary": f"Found {len(dependencies)} dependencies ({len(spring_deps)} Spring-related, {len(test_deps)} test dependencies)",
            "build_tool": build_type,
            "build_file": os.path.basename(build_file),
            "total_count": len(dependencies),
            "dependencies": dependencies,
            "java_version": metadata.get("java_version"),
            "spring_boot_version": metadata.get("spring_boot_version"),
            "categories": {
                "spring": len(spring_deps),
                "test": len(test_deps),
                "other": len(dependencies) - len(spring_deps) - len(test_deps)
            }
        }

    except Exception as e:
        if not is_quiet():
            print_tool_result(f"Error: {str(e)}")
        return {
            "error": f"Failed to parse {build_type} dependencies: {str(e)}",
            "build_file": os.path.basename(build_file),
            "build_tool": build_type
        }


def find_build_file():
    """
    Find build file in current directory.
    Tries multiple patterns for better discovery.

    Returns:
        (file_path, build_type) or (None, None)
    """
    project_root = os.getcwd()

    # Check locations in order of priority
    candidates = [
        ("pom.xml", "maven"),
        ("build.gradle", "gradle"),
        ("build.gradle.kts", "gradle"),
    ]

    for filename, build_type in candidates:
        path = os.path.join(project_root, filename)
        if os.path.exists(path):
            return path, build_type

    # Try subdirectories if not found in root
    for subdir in ["app", "application", "service"]:
        subpath = os.path.join(project_root, subdir)
        if os.path.isdir(subpath):
            for filename, build_type in candidates:
                path = os.path.join(subpath, filename)
                if os.path.exists(path):
                    return path, build_type

    return None, None


def parse_maven_metadata(pom_path):
    """
    Parse Java version and Spring Boot version from pom.xml.

    Returns:
        Dict with java_version, spring_boot_version
    """
    metadata = {
        "java_version": None,
        "spring_boot_version": None
    }

    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()

        # Handle Maven namespace
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}

        # Find Java version in properties
        # Look for: java.version, maven.compiler.source, maven.compiler.target
        properties = root.find("m:properties", ns)
        if properties is None:
            properties = root.find("properties")

        if properties is not None:
            # Check java.version
            java_ver = properties.find("m:java.version", ns)
            if java_ver is None:
                java_ver = properties.find("java.version")
            if java_ver is not None and java_ver.text:
                metadata["java_version"] = java_ver.text

            # Check maven.compiler.source as fallback
            if not metadata["java_version"]:
                compiler_source = properties.find("m:maven.compiler.source", ns)
                if compiler_source is None:
                    compiler_source = properties.find("maven.compiler.source")
                if compiler_source is not None and compiler_source.text:
                    metadata["java_version"] = compiler_source.text

        # Find Spring Boot version from parent
        parent = root.find("m:parent", ns)
        if parent is None:
            parent = root.find("parent")

        if parent is not None:
            parent_artifact = parent.find("m:artifactId", ns)
            if parent_artifact is None:
                parent_artifact = parent.find("artifactId")

            if parent_artifact is not None and "spring-boot" in (parent_artifact.text or "").lower():
                parent_version = parent.find("m:version", ns)
                if parent_version is None:
                    parent_version = parent.find("version")
                if parent_version is not None:
                    metadata["spring_boot_version"] = parent_version.text

    except Exception:
        pass

    return metadata


def parse_maven_dependencies(pom_path):
    """
    Parse dependencies from pom.xml.

    Returns:
        List of dependency dicts
    """
    dependencies = []

    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()

        # Handle Maven namespace
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}

        # Try with namespace first, then without
        dep_elements = root.findall(".//m:dependency", ns)
        if not dep_elements:
            dep_elements = root.findall(".//dependency")

        for dep in dep_elements:
            dependency = {}

            # Try with namespace
            group = dep.find("m:groupId", ns)
            if group is None:
                group = dep.find("groupId")
            if group is not None:
                dependency["group"] = group.text

            artifact = dep.find("m:artifactId", ns)
            if artifact is None:
                artifact = dep.find("artifactId")
            if artifact is not None:
                dependency["artifact"] = artifact.text

            version = dep.find("m:version", ns)
            if version is None:
                version = dep.find("version")
            if version is not None:
                dependency["version"] = version.text
            else:
                dependency["version"] = "managed"

            scope = dep.find("m:scope", ns)
            if scope is None:
                scope = dep.find("scope")
            if scope is not None:
                dependency["scope"] = scope.text
            else:
                dependency["scope"] = "compile"

            if dependency.get("artifact"):
                dependencies.append(dependency)

    except ET.ParseError as e:
        raise Exception(f"Invalid XML in pom.xml: {str(e)}")

    return dependencies


def parse_gradle_metadata(gradle_path):
    """
    Parse Java version and Spring Boot version from build.gradle.

    Returns:
        Dict with java_version, spring_boot_version
    """
    metadata = {
        "java_version": None,
        "spring_boot_version": None
    }

    try:
        with open(gradle_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Look for Java version patterns
        # sourceCompatibility = '17' or sourceCompatibility = JavaVersion.VERSION_17
        java_patterns = [
            r"sourceCompatibility\s*=\s*['\"]?(\d+)['\"]?",
            r"sourceCompatibility\s*=\s*JavaVersion\.VERSION_(\d+)",
            r"jvmTarget\s*=\s*['\"](\d+)['\"]",
            r"languageVersion\.set\s*\(\s*JavaLanguageVersion\.of\s*\(\s*(\d+)\s*\)\s*\)",
        ]

        for pattern in java_patterns:
            match = re.search(pattern, content)
            if match:
                metadata["java_version"] = match.group(1)
                break

        # Look for Spring Boot version
        # plugins { id 'org.springframework.boot' version '3.2.0' }
        spring_boot_patterns = [
            r"id\s*['\"]org\.springframework\.boot['\"]\s*version\s*['\"]([^'\"]+)['\"]",
            r"org\.springframework\.boot:spring-boot[^:]*:([^'\"]+)['\"]",
        ]

        for pattern in spring_boot_patterns:
            match = re.search(pattern, content)
            if match:
                metadata["spring_boot_version"] = match.group(1)
                break

    except Exception:
        pass

    return metadata


def parse_gradle_dependencies(gradle_path):
    """
    Parse dependencies from build.gradle or build.gradle.kts.

    Returns:
        List of dependency dicts
    """
    dependencies = []

    try:
        with open(gradle_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Pattern for various Gradle dependency formats
        patterns = [
            # implementation 'group:artifact:version'
            r"(implementation|api|compileOnly|runtimeOnly|testImplementation|testRuntimeOnly)\s*['\"]([^:]+):([^:]+):([^'\"]+)['\"]",
            # implementation("group:artifact:version")
            r"(implementation|api|compileOnly|runtimeOnly|testImplementation|testRuntimeOnly)\s*\(\s*['\"]([^:]+):([^:]+):([^'\"]+)['\"]\s*\)",
            # implementation group: 'x', name: 'y', version: 'z'
            r"(implementation|api|compileOnly|runtimeOnly|testImplementation|testRuntimeOnly)\s+group:\s*['\"]([^'\"]+)['\"],\s*name:\s*['\"]([^'\"]+)['\"],\s*version:\s*['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                scope_map = {
                    "implementation": "compile",
                    "api": "compile",
                    "compileOnly": "provided",
                    "runtimeOnly": "runtime",
                    "testImplementation": "test",
                    "testRuntimeOnly": "test"
                }

                dependency = {
                    "group": match[1],
                    "artifact": match[2],
                    "version": match[3],
                    "scope": scope_map.get(match[0], "compile")
                }
                dependencies.append(dependency)

        # Also check for dependencies without version (BOM managed)
        bom_patterns = [
            r"(implementation|api|testImplementation)\s*['\"]([^:]+):([^:'\"]+)['\"]",
            r"(implementation|api|testImplementation)\s*\(\s*['\"]([^:]+):([^:'\"]+)['\"]\s*\)",
        ]

        for pattern in bom_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Check if this is a 2-part dependency (no version)
                if len(match) == 3:
                    scope_map = {
                        "implementation": "compile",
                        "api": "compile",
                        "testImplementation": "test"
                    }
                    dependency = {
                        "group": match[1],
                        "artifact": match[2],
                        "version": "managed",
                        "scope": scope_map.get(match[0], "compile")
                    }
                    # Avoid duplicates
                    if not any(d["artifact"] == dependency["artifact"] and d["group"] == dependency["group"] for d in dependencies):
                        dependencies.append(dependency)

    except Exception as e:
        raise Exception(f"Failed to read Gradle file: {str(e)}")

    return dependencies


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="analyze_dependencies",
    description="THE tool for dependency questions. Analyzes pom.xml or build.gradle and returns all dependencies with versions. Use this when user asks about: dependencies, libraries, versions, packages, Maven, Gradle, what's in pom.xml."
)


def register():
    """Register this tool with the registry."""
    register_tool("analyze_dependencies", analyze_dependencies, TOOL_DEFINITION)
