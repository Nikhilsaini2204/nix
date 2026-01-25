"""Smart query tool - answers questions using cached context and RAG."""

from typing import Dict, Any

from core.tools_registry import register_tool, create_tool_definition
from utils.output import print_tool_start, print_tool_result, is_quiet


def smart_query(question: str) -> Dict[str, Any]:
    """
    Answer questions about the codebase using cached context and semantic search.
    NO LLM calls - uses pre-built understanding from 'nix init'.

    Args:
        question: Natural language question about the codebase

    Returns:
        Answer based on cached context and/or semantic search
    """
    if not is_quiet():
        print_tool_start("smart_query")

    question_lower = question.lower()

    # Load cached context
    context = None
    try:
        from indexer.context_builder import ContextBuilder
        context = ContextBuilder.load_context()
    except Exception:
        pass

    # Determine question type and find answer
    answer = None

    # Check SPECIFIC keywords FIRST, then fall back to generic ones

    # Configuration questions (check first - includes database connection, port, etc.)
    if any(kw in question_lower for kw in ["config", "property", "setting", "profile", "port", "configuration", "datasource", "connection"]):
        answer = _answer_config_question(context, question_lower)

    # Database-specific questions (could be config or entity - check context)
    elif "database" in question_lower:
        # If asking "what database" or "which database", it's about config
        if any(phrase in question_lower for phrase in ["what database", "which database", "database is used", "database type", "db used"]):
            answer = _answer_config_question(context, question_lower)
        else:
            # Otherwise likely asking about data/entities
            answer = _answer_entity_question(context, question_lower)

    # Dependency questions (includes version/java)
    elif any(kw in question_lower for kw in ["dependency", "dependencies", "library", "version", "java version", "spring version", "pom", "gradle", "maven"]):
        answer = _answer_dependency_question(context, question_lower)

    # Service questions
    elif any(kw in question_lower for kw in ["service", "services", "business logic"]):
        answer = _answer_service_question(context, question_lower)

    # Repository questions
    elif any(kw in question_lower for kw in ["repository", "repositories", "repo", "repos", "data access", "dao"]):
        answer = _answer_repository_question(context, question_lower)

    # Endpoint/API questions
    elif any(kw in question_lower for kw in ["endpoint", "api", "rest", "route", "url"]):
        answer = _answer_endpoint_question(context, question_lower)

    # Entity/Model questions
    elif any(kw in question_lower for kw in ["entity", "entities", "model", "models", "table", "data"]):
        answer = _answer_entity_question(context, question_lower)

    # Controller questions
    elif any(kw in question_lower for kw in ["controller", "handler"]):
        answer = _answer_controller_question(context, question_lower)

    # Project overview questions (LAST - these are generic catch-all keywords)
    elif any(kw in question_lower for kw in ["what is", "what does", "about", "overview", "tell me", "project"]):
        answer = _answer_project_question(context, question_lower)

    # Fall back to semantic search for specific questions
    if not answer:
        answer = _search_semantic(question)

    if not answer:
        answer = "I don't have enough context to answer that. Try asking about services, endpoints, entities, or run 'nix init' to build codebase understanding."

    if not is_quiet():
        print_tool_result("Found answer in context")

    return {
        "question": question,
        "answer": answer,
        "summary": answer,
        "_skip_llm": True,
        "_message": answer
    }


def _answer_project_question(context: Dict, question: str) -> str:
    """Answer project overview questions."""
    if not context:
        return None

    summaries = context.get("summaries", {})
    project = context.get("project", {})

    # Full project overview
    full_summary = summaries.get("full_summary", "")
    if full_summary:
        return full_summary

    return project.get("description", None)


def _answer_service_question(context: Dict, question: str) -> str:
    """Answer service-related questions."""
    if not context:
        return None

    services = context.get("services", [])
    if not services:
        return "No services found in this project."

    # List all services
    parts = [f"This project has {len(services)} services:"]
    for svc in services:
        parts.append(f"\n- {svc['name']}: {svc.get('purpose', 'Service')}")
        if svc.get('methods'):
            methods = svc['methods'][:3]
            parts.append(f"  Methods: {', '.join(methods)}")

    return "\n".join(parts)


def _answer_endpoint_question(context: Dict, question: str) -> str:
    """Answer endpoint-related questions."""
    if not context:
        return None

    endpoints = context.get("endpoints", [])
    if not endpoints:
        return "No REST endpoints found in this project."

    # Check if asking about specific endpoint
    for ep in endpoints:
        path = ep.get("path", "").lower()
        if path and path.replace("/", " ").strip() in question:
            return f"{ep['method']} {ep['path']}: {ep.get('description', 'Endpoint')}"

    # List all endpoints
    parts = [f"This project has {len(endpoints)} REST endpoints:"]
    for ep in endpoints[:10]:
        parts.append(f"\n- {ep['method']} {ep['path']}: {ep.get('description', '')}")

    if len(endpoints) > 10:
        parts.append(f"\n... and {len(endpoints) - 10} more")

    return "\n".join(parts)


def _answer_entity_question(context: Dict, question: str) -> str:
    """Answer entity-related questions."""
    if not context:
        return None

    entities = context.get("entities", [])
    if not entities:
        return "No JPA entities found in this project."

    # Check if asking about specific entity
    for entity in entities:
        name = entity.get("name", "").lower()
        if name in question:
            fields = entity.get("fields", [])
            field_names = [f["name"] for f in fields[:5]]
            return f"{entity['name']}: {entity.get('purpose', 'Entity')}\nFields: {', '.join(field_names)}"

    # List all entities
    parts = [f"This project has {len(entities)} data entities:"]
    for entity in entities:
        parts.append(f"\n- {entity['name']}: {entity.get('purpose', '')}")

    return "\n".join(parts)


def _answer_controller_question(context: Dict, question: str) -> str:
    """Answer controller-related questions."""
    if not context:
        return None

    controllers = context.get("controllers", [])
    if not controllers:
        return "No controllers found in this project."

    parts = [f"This project has {len(controllers)} controllers:"]
    for ctrl in controllers:
        parts.append(f"\n- {ctrl['name']}: {ctrl.get('purpose', 'Controller')}")
        if ctrl.get('endpoints'):
            parts.append(f"  Endpoints: {ctrl['endpoint_count']}")

    return "\n".join(parts)


def _answer_repository_question(context: Dict, question: str) -> str:
    """Answer repository-related questions."""
    if not context:
        return None

    repositories = context.get("repositories", [])
    if not repositories:
        return "No repositories found in this project."

    parts = [f"This project has {len(repositories)} repositories:"]
    for repo in repositories:
        parts.append(f"\n- {repo['name']}: {repo.get('purpose', 'Repository')}")
        if repo.get('entity'):
            parts.append(f"  Entity: {repo['entity']}")

    return "\n".join(parts)


def _answer_config_question(context: Dict, question: str) -> str:
    """Answer configuration questions."""
    if not context:
        return None

    config = context.get("configuration", {})
    if not config:
        return "No configuration analysis available."

    parts = ["Configuration:"]

    if config.get("profiles"):
        parts.append(f"\nProfiles: {', '.join(config['profiles'])}")

    server = config.get("server", {})
    if server:
        parts.append(f"\nServer port: {server.get('port', '8080')}")

    db = config.get("database", {})
    if db.get("url"):
        parts.append(f"\nDatabase: {db['url']}")

    return "\n".join(parts)


def _answer_dependency_question(context: Dict, question: str) -> str:
    """Answer dependency questions."""
    if not context:
        return None

    deps = context.get("dependencies", {})
    if not deps:
        return "No dependency analysis available."

    parts = [f"Build tool: {deps.get('build_tool', 'unknown')}"]

    if deps.get("java_version"):
        parts.append(f"Java version: {deps['java_version']}")

    if deps.get("spring_boot_version"):
        parts.append(f"Spring Boot: {deps['spring_boot_version']}")

    key_deps = deps.get("key_dependencies", [])
    if key_deps:
        parts.append("\nKey dependencies:")
        for dep in key_deps[:8]:
            parts.append(f"  - {dep}")

    return "\n".join(parts)


def _search_semantic(question: str) -> str:
    """Fall back to semantic search for specific questions."""
    try:
        from indexer.vector_store import VectorStore
        store = VectorStore()

        if not store.is_available() or not store.has_index():
            return None

        results = store.search(question, top_k=3)
        if not results:
            return None

        parts = ["Found relevant code:"]
        for r in results:
            method = f"{r.get('class_name', 'Unknown')}.{r.get('method_name', 'unknown')}"
            summary = r.get('summary', '')
            parts.append(f"\n- {method}: {summary}")
            parts.append(f"  File: {r.get('file_path', '')}:{r.get('line', 0)}")

        return "\n".join(parts)

    except Exception:
        return None


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="smart_query",
    description="""Answer questions about the codebase using pre-built context.
Use for questions like:
- "what services do we have"
- "show me the endpoints"
- "what entities exist"
- "what does UserService do"
- "how is authentication handled"

This uses cached context from 'nix init' - no LLM calls needed.""",
    parameters={
        "question": {
            "type": "string",
            "description": "The question about the codebase"
        }
    },
    required=["question"]
)


def register():
    """Register this tool with the registry."""
    register_tool("smart_query", smart_query, TOOL_DEFINITION)
