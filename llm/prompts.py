def get_springboot_detection_prompt(build_file_content, build_type):
    """Generate prompt for Spring Boot detection"""

    build_type_name = "Maven (pom.xml)" if build_type == "maven" else "Gradle (build.gradle)"

    prompt = f"""You are analyzing a {build_type_name} build file to determine if this is a Spring Boot project.

Build file content:
{build_file_content}

Please answer these questions:
1. Is this a Spring Boot project? Answer with Yes or No.
2. If yes, what is the Spring Boot version being used?

Respond clearly and concisely."""

    return prompt