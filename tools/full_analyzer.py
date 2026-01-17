"""Full project analyzer - runs all analyses in one tool call."""

from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, set_quiet_mode


def full_analysis():
    """
    Run complete project analysis in ONE tool call.
    Executes all analyzers locally without extra LLM API calls.

    Returns:
        dict with comprehensive project analysis
    """
    results = {}
    errors = []
    summary_lines = []

    # Suppress individual tool output
    set_quiet_mode(True)

    # 1. Project Structure
    print_tool_start("Exploring project structure")
    try:
        from tools.project_explorer import explore_project
        structure = explore_project()
        dirs = structure.get("directory_count", 0)
        files = structure.get("file_count", 0)
        print_tool_result(f"{dirs} directories, {files} files")
        results["structure"] = {"directories": dirs, "files": files}
        summary_lines.append(f"{dirs} directories, {files} files")
    except Exception as e:
        print_tool_result(f"Error: {str(e)}")
        errors.append(f"Structure: {str(e)}")

    # 2. Dependencies
    print_tool_start("Analyzing dependencies")
    try:
        from tools.dependency_analyzer import analyze_dependencies
        deps = analyze_dependencies()
        if "error" not in deps:
            total = deps.get("total_count", 0)
            build_tool = deps.get("build_tool", "unknown")
            spring = deps.get("categories", {}).get("spring", 0)
            print_tool_result(f"{total} dependencies ({spring} Spring) via {build_tool}")
            results["dependencies"] = {"total": total, "spring": spring, "build_tool": build_tool}
            summary_lines.append(f"{total} dependencies")
        else:
            print_tool_result(f"Skipped: {deps.get('error')}")
    except Exception as e:
        print_tool_result(f"Error: {str(e)}")
        errors.append(f"Dependencies: {str(e)}")

    # 3. Code Structure
    print_tool_start("Analyzing code structure")
    try:
        from tools.code_analyzer import analyze_code_structure
        code = analyze_code_structure()
        if "error" not in code:
            files = code.get("file_count", 0)
            packages = code.get("package_count", 0)
            components = code.get("components", {})
            controllers = components.get("controllers", 0)
            services = components.get("services", 0)
            repos = components.get("repositories", 0)
            print_tool_result(f"{files} Java files, {packages} packages")
            print_tool_result(f"{controllers} controllers, {services} services, {repos} repositories")
            results["code"] = {"files": files, "packages": packages, "components": components}
            summary_lines.append(f"{files} Java files")
        else:
            print_tool_result(f"Skipped: {code.get('error')}")
    except Exception as e:
        print_tool_result(f"Error: {str(e)}")
        errors.append(f"Code: {str(e)}")

    # 4. REST Endpoints
    print_tool_start("Finding REST endpoints")
    try:
        from tools.endpoint_analyzer import analyze_endpoints
        endpoints = analyze_endpoints()
        if "error" not in endpoints:
            count = endpoints.get("endpoint_count", 0)
            controllers = endpoints.get("controller_count", 0)
            by_method = endpoints.get("by_method", {})
            method_str = ", ".join([f"{v} {k}" for k, v in by_method.items()])
            print_tool_result(f"{count} endpoints in {controllers} controllers")
            if method_str:
                print_tool_result(f"Methods: {method_str}")
            results["endpoints"] = {"count": count, "controllers": controllers, "by_method": by_method}
            summary_lines.append(f"{count} REST endpoints")
        else:
            print_tool_result(f"Skipped: {endpoints.get('error')}")
    except Exception as e:
        print_tool_result(f"Error: {str(e)}")
        errors.append(f"Endpoints: {str(e)}")

    # 5. Configuration
    print_tool_start("Reading configuration")
    try:
        from tools.config_analyzer import analyze_configuration
        config = analyze_configuration()
        if "error" not in config:
            file_count = config.get("file_count", 0)
            props = config.get("property_count", 0)
            profiles = config.get("profiles", [])
            print_tool_result(f"{props} properties in {file_count} file(s)")
            if profiles:
                print_tool_result(f"Profiles: {', '.join(profiles)}")
            results["configuration"] = {"files": file_count, "properties": props, "profiles": profiles}
            summary_lines.append(f"{props} config properties")
        else:
            print_tool_result(f"Skipped: {config.get('error')}")
    except Exception as e:
        print_tool_result(f"Error: {str(e)}")
        errors.append(f"Configuration: {str(e)}")

    # 6. Spring Beans
    print_tool_start("Scanning Spring beans")
    try:
        from tools.bean_analyzer import analyze_beans
        beans = analyze_beans()
        if "error" not in beans:
            total = beans.get("total_beans", 0)
            components = beans.get("components", {})
            print_tool_result(f"{total} beans total")
            results["beans"] = {"total": total, "components": components}
            summary_lines.append(f"{total} Spring beans")
        else:
            print_tool_result(f"Skipped: {beans.get('error')}")
    except Exception as e:
        print_tool_result(f"Error: {str(e)}")
        errors.append(f"Beans: {str(e)}")

    # 7. JPA Entities
    print_tool_start("Finding JPA entities")
    try:
        from tools.entity_analyzer import analyze_entities
        entities = analyze_entities()
        if "error" not in entities:
            count = entities.get("entity_count", 0)
            rels = entities.get("relationship_count", 0)
            print_tool_result(f"{count} entities, {rels} relationships")
            results["entities"] = {"count": count, "relationships": rels}
            if count > 0:
                summary_lines.append(f"{count} JPA entities")
        else:
            print_tool_result(f"Skipped: {entities.get('error')}")
    except Exception as e:
        print_tool_result(f"Error: {str(e)}")
        errors.append(f"Entities: {str(e)}")

    # Restore normal output mode
    set_quiet_mode(False)

    # Print completion
    print()

    # Build a ready-to-use summary for LLM
    summary = "Project overview: " + ", ".join(summary_lines) + "."

    return {
        "summary": summary,
        "results": results,
        "errors": errors if errors else None,
        # Skip LLM response - output already printed to user
        "_skip_llm": True,
        "_message": "That's the full overview. Want me to dive deeper into anything specific?"
    }


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="full_analysis",
    description="THE tool for 'analyze everything', 'full analysis', 'check all', 'complete analysis' requests. Runs ALL analyzers in ONE call. Returns comprehensive overview."
)


def register():
    """Register this tool with the registry."""
    register_tool("full_analysis", full_analysis, TOOL_DEFINITION)
