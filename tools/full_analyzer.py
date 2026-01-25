"""Full project analyzer - returns cached codebase understanding."""

from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result


def full_analysis():
    """
    Return comprehensive project understanding from cache.
    All analysis is done during 'nix init' - this just retrieves it.

    Returns:
        dict with comprehensive project analysis
    """
    print_tool_start("full_analysis")

    # Try to load cached context (built during init)
    try:
        from indexer.context_builder import ContextBuilder
        context = ContextBuilder.load_context()

        if context:
            print_tool_result("Retrieved codebase context")

            # Build user-friendly message from cached context
            project = context.get("project", {})
            services = context.get("services", [])
            controllers = context.get("controllers", [])
            entities = context.get("entities", [])
            endpoints = context.get("endpoints", [])
            summaries = context.get("summaries", {})

            # Get the full summary
            full_summary = summaries.get("full_summary", "")
            if not full_summary:
                full_summary = project.get("description", "This is a Spring Boot application.")

            # Build detailed message
            message_parts = [full_summary]

            # Add service details
            if services:
                svc_names = [s["name"] for s in services[:4]]
                message_parts.append(f"\nServices: {', '.join(svc_names)}")
                for svc in services[:3]:
                    message_parts.append(f"  - {svc['name']}: {svc.get('purpose', '')}")

            # Add endpoint examples
            if endpoints:
                message_parts.append(f"\nAPI Endpoints ({len(endpoints)} total):")
                for ep in endpoints[:5]:
                    message_parts.append(f"  - {ep['method']} {ep['path']}: {ep.get('description', '')}")

            # Add entity info
            if entities:
                entity_names = [e["name"] for e in entities]
                message_parts.append(f"\nData Models: {', '.join(entity_names)}")

            message_parts.append("\nWant me to dive deeper into any specific part?")

            user_message = "\n".join(message_parts)

            return {
                "project": project,
                "services": services,
                "controllers": controllers,
                "entities": entities,
                "endpoints": endpoints[:10],  # Limit for response size
                "summary": user_message,
                "_skip_llm": True,
                "_message": user_message
            }

    except Exception as e:
        pass

    # Fallback: No cached context, need to build it
    print_tool_result("No cached context found, analyzing...")
    return _analyze_fresh()


def _analyze_fresh():
    """Fallback: Analyze project fresh if no cache exists."""
    from utils.output import set_quiet_mode

    results = {}
    set_quiet_mode(True)

    # Quick analysis
    try:
        from tools.code_analyzer import analyze_code_structure
        code = analyze_code_structure()
        if "error" not in code:
            results["code"] = code
    except:
        pass

    try:
        from tools.endpoint_analyzer import analyze_endpoints
        endpoints = analyze_endpoints()
        if "error" not in endpoints:
            results["endpoints"] = endpoints
    except:
        pass

    try:
        from tools.entity_analyzer import analyze_entities
        entities = analyze_entities()
        if "error" not in entities:
            results["entities"] = entities
    except:
        pass

    set_quiet_mode(False)

    # Build message
    code_stats = results.get("code", {})
    endpoint_count = results.get("endpoints", {}).get("endpoint_count", 0)
    entity_count = results.get("entities", {}).get("entity_count", 0)

    message = f"This is a Spring Boot application with {code_stats.get('file_count', 0)} Java files"
    if endpoint_count > 0:
        message += f", {endpoint_count} REST endpoints"
    if entity_count > 0:
        message += f", and {entity_count} data entities"
    message += ". Run 'nix init' to build full codebase understanding for faster responses."

    return {
        "results": results,
        "summary": message,
        "_skip_llm": True,
        "_message": message
    }


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="full_analysis",
    description="THE tool for 'analyze everything', 'what is this project', 'what does my code do', 'full analysis', 'tell me about this project'. Returns comprehensive codebase understanding."
)


def register():
    """Register this tool with the registry."""
    register_tool("full_analysis", full_analysis, TOOL_DEFINITION)
