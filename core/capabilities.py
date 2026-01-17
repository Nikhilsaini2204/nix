"""Capabilities for guiding users."""

CAPABILITIES = [
    {
        "name": "dependencies",
        "description": "versions, Spring libraries, outdated packages",
        "tool": "analyze_dependencies",
        "keywords": ["dependencies", "deps", "pom", "gradle", "versions", "libraries", "packages", "outdated", "maven"]
    },
    {
        "name": "code structure",
        "description": "packages, classes, Spring components",
        "tool": "analyze_code_structure",
        "keywords": ["code", "structure", "packages", "classes", "java", "components"]
    },
    {
        "name": "endpoints",
        "description": "REST API routes and methods",
        "tool": "analyze_endpoints",
        "keywords": ["endpoints", "api", "rest", "routes", "urls", "mapping", "controller"]
    },
    {
        "name": "configuration",
        "description": "application.properties, profiles, settings",
        "tool": "analyze_configuration",
        "keywords": ["config", "configuration", "properties", "yml", "yaml", "settings", "profiles"]
    },
    {
        "name": "beans",
        "description": "services, repositories, components",
        "tool": "analyze_beans",
        "keywords": ["beans", "services", "repositories", "components", "autowired", "injection"]
    },
    {
        "name": "entities",
        "description": "JPA entities, tables, relationships",
        "tool": "analyze_entities",
        "keywords": ["entities", "entity", "jpa", "tables", "database", "relationships", "models"]
    },
    {
        "name": "project structure",
        "description": "folder tree, all files",
        "tool": "explore_project",
        "keywords": ["project", "structure", "tree", "folders", "files", "directory"]
    },
    {
        "name": "everything",
        "description": "full project analysis",
        "tool": "all",
        "keywords": ["everything", "all", "full", "complete", "entire", "overview", "whole"]
    }
]

VAGUE_INPUTS = [
    "analyze",
    "analyse",
    "check",
    "scan",
    "show",
    "tell me",
    "what",
    "help",
    "?"
]


def is_vague_input(user_input):
    """Check if input is too vague and needs guidance."""
    normalized = user_input.lower().strip()

    # Very short inputs are vague
    if len(normalized) < 10:
        for vague in VAGUE_INPUTS:
            if normalized == vague or normalized.startswith(vague + " ") and len(normalized) < 15:
                return True

    return False


def get_capability_by_choice(choice):
    """Get capability by keyword match."""
    choice = choice.lower().strip()

    # Check by keyword
    for cap in CAPABILITIES:
        for keyword in cap["keywords"]:
            if keyword in choice:
                return cap
        if cap["name"].lower() in choice:
            return cap

    return None


def show_capabilities_prompt():
    """Display a conversational prompt about capabilities."""
    from utils.output import bold, muted
    print()
    print("What would you like me to analyze?")
    print()
    print(muted("I can look at:"))
    print(f"  {bold('dependencies')} - {muted('versions, Spring libraries')}")
    print(f"  {bold('code structure')} - {muted('packages, classes, components')}")
    print(f"  {bold('endpoints')} - {muted('REST API routes')}")
    print(f"  {bold('configuration')} - {muted('properties, profiles')}")
    print(f"  {bold('beans')} - {muted('services, repositories')}")
    print(f"  {bold('entities')} - {muted('JPA entities, relationships')}")
    print(f"  {bold('project structure')} - {muted('folder tree')}")
    print(f"  {bold('everything')} - {muted('full analysis')}")
    print()


def get_tool_for_capability(capability):
    """Get the tool name(s) for a capability."""
    if capability["tool"] == "all":
        # Use full_analysis for "everything" - it runs all analyzers in one call
        return ["full_analysis"]
    return [capability["tool"]]
