"""Context builder - generates comprehensive codebase understanding during init."""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from config import get_index_path


class ContextBuilder:
    """Builds and stores comprehensive codebase context during initialization."""

    CONTEXT_FILE = "codebase_context.json"

    def __init__(self):
        self.index_path = get_index_path()
        self.context = {
            "generated_at": None,
            "project": {},
            "services": [],
            "controllers": [],
            "repositories": [],
            "entities": [],
            "endpoints": [],
            "configuration": {},
            "dependencies": {},
            "call_flows": [],
            "summaries": {}
        }

    def build_full_context(
        self,
        classes: List[Dict] = None,
        methods: List[Dict] = None,
        endpoints: List[Dict] = None,
        entities: List[Dict] = None,
        config: Dict = None,
        dependencies: Dict = None,
        method_summaries: List[Dict] = None,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for the entire codebase.
        This is called once during 'nix init' and generates all understanding upfront.

        Args:
            classes: Parsed class information
            methods: Parsed method information
            endpoints: REST endpoints
            entities: JPA entities
            config: Configuration data
            dependencies: Dependency data
            method_summaries: Pre-generated method summaries from code_summarizer
            show_progress: Whether to print progress

        Returns:
            Complete context dictionary
        """
        if show_progress:
            print("  Building codebase context...")

        # 1. Build project overview
        if show_progress:
            print("    - Analyzing project structure...")
        self._build_project_overview(classes, methods, endpoints, entities, dependencies)

        # 2. Analyze services
        if show_progress:
            print("    - Understanding services...")
        self._analyze_services(classes, methods, method_summaries)

        # 3. Analyze controllers
        if show_progress:
            print("    - Mapping controllers and endpoints...")
        self._analyze_controllers(classes, methods, endpoints, method_summaries)

        # 4. Analyze repositories
        if show_progress:
            print("    - Analyzing data access layer...")
        self._analyze_repositories(classes, methods, method_summaries)

        # 5. Analyze entities
        if show_progress:
            print("    - Understanding data models...")
        self._analyze_entities(entities)

        # 6. Store endpoint details
        if show_progress:
            print("    - Documenting API endpoints...")
        self._store_endpoints(endpoints)

        # 7. Analyze configuration
        if show_progress:
            print("    - Reading configuration...")
        self._analyze_configuration(config)

        # 8. Store dependencies
        if show_progress:
            print("    - Cataloging dependencies...")
        self._store_dependencies(dependencies)

        # 9. Build common call flows
        if show_progress:
            print("    - Tracing call flows...")
        self._build_call_flows(methods)

        # 10. Create quick lookup summaries
        if show_progress:
            print("    - Creating quick summaries...")
        self._build_summaries()

        self.context["generated_at"] = datetime.now().isoformat()

        # Save context
        self._save_context()

        if show_progress:
            print("  Context built successfully!")

        return self.context

    def _build_project_overview(self, classes, methods, endpoints, entities, dependencies):
        """Build high-level project overview."""
        # Detect project type
        project_type = "Spring Boot Application"
        domains = []

        # Count components
        controllers = [c for c in (classes or []) if self._has_annotation(c, "Controller")]
        services = [c for c in (classes or []) if self._has_annotation(c, "Service")]
        repos = [c for c in (classes or []) if self._has_annotation(c, "Repository")]

        # Detect domains from class names
        all_names = " ".join([c.get("name", "").lower() for c in (classes or [])])
        domain_keywords = {
            "ecommerce": ["order", "cart", "product", "payment", "checkout"],
            "authentication": ["auth", "login", "user", "token", "security"],
            "messaging": ["message", "notification", "email", "chat"],
            "content": ["article", "post", "blog", "content", "media"],
            "inventory": ["inventory", "stock", "warehouse", "item"],
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in all_names for kw in keywords):
                domains.append(domain)

        # Determine project type
        if len(endpoints or []) > 5:
            project_type = "REST API"
        elif any("WebSocket" in str(c.get("annotations", [])) for c in (classes or [])):
            project_type = "Real-time Application"

        # Build description
        desc_parts = [f"This is a {project_type}"]
        if domains:
            desc_parts.append(f"for {' and '.join(domains[:2])}")
        if endpoints:
            desc_parts.append(f"with {len(endpoints)} REST endpoints")
        if entities:
            desc_parts.append(f"managing {len(entities)} data entities")

        self.context["project"] = {
            "type": project_type,
            "description": " ".join(desc_parts) + ".",
            "domains": domains[:3],
            "stats": {
                "classes": len(classes or []),
                "methods": len(methods or []),
                "controllers": len(controllers),
                "services": len(services),
                "repositories": len(repos),
                "endpoints": len(endpoints or []),
                "entities": len(entities or [])
            }
        }

    def _analyze_services(self, classes, methods, method_summaries):
        """Analyze @Service classes and their purpose."""
        services = [c for c in (classes or []) if self._has_annotation(c, "Service")]

        summary_lookup = {}
        for ms in (method_summaries or []):
            key = f"{ms.get('class_name', '')}.{ms.get('name', '')}"
            summary_lookup[key] = ms.get("summary", "")

        for svc in services:
            svc_name = svc.get("name", "")
            svc_methods = [m for m in (methods or []) if m.get("class_name") == svc_name]

            # Get method summaries for this service
            method_descs = []
            for m in svc_methods[:5]:  # Top 5 methods
                key = f"{svc_name}.{m.get('name', '')}"
                if key in summary_lookup:
                    method_descs.append(summary_lookup[key])

            # Infer service purpose from name and methods
            purpose = self._infer_purpose_from_name(svc_name, "Service")
            if method_descs:
                purpose += " " + " ".join(method_descs[:2])

            self.context["services"].append({
                "name": svc_name,
                "file": svc.get("file_path", ""),
                "purpose": purpose,
                "methods": [m.get("name") for m in svc_methods],
                "method_count": len(svc_methods)
            })

    def _analyze_controllers(self, classes, methods, endpoints, method_summaries):
        """Analyze @Controller classes and map to endpoints."""
        controllers = [c for c in (classes or []) if self._has_annotation(c, "Controller")]

        for ctrl in controllers:
            ctrl_name = ctrl.get("name", "")
            ctrl_file = ctrl.get("file_path", "")

            # Find endpoints for this controller
            ctrl_endpoints = [e for e in (endpoints or []) if e.get("controller") == ctrl_name]

            # Build endpoint list
            endpoint_list = []
            for ep in ctrl_endpoints:
                endpoint_list.append({
                    "method": ep.get("method", "GET"),
                    "path": ep.get("path", ""),
                    "handler": ep.get("handler", ""),
                    "description": self._infer_endpoint_purpose(ep)
                })

            purpose = self._infer_purpose_from_name(ctrl_name, "Controller")

            self.context["controllers"].append({
                "name": ctrl_name,
                "file": ctrl_file,
                "purpose": purpose,
                "base_path": self._extract_base_path(ctrl),
                "endpoints": endpoint_list,
                "endpoint_count": len(endpoint_list)
            })

    def _analyze_repositories(self, classes, methods, method_summaries):
        """Analyze @Repository classes."""
        repos = [c for c in (classes or []) if self._has_annotation(c, "Repository")]

        for repo in repos:
            repo_name = repo.get("name", "")

            # Infer entity from repository name
            entity_name = repo_name.replace("Repository", "").replace("Repo", "")

            self.context["repositories"].append({
                "name": repo_name,
                "file": repo.get("file_path", ""),
                "entity": entity_name,
                "purpose": f"Data access layer for {entity_name} entities"
            })

    def _analyze_entities(self, entities):
        """Analyze JPA entities."""
        for entity in (entities or []):
            entity_name = entity.get("name", "")
            fields = entity.get("fields", [])
            relationships = entity.get("relationships", [])

            # Build field list
            field_list = []
            for f in fields[:10]:  # Top 10 fields
                field_list.append({
                    "name": f.get("name", ""),
                    "type": f.get("type", ""),
                    "annotations": f.get("annotations", [])
                })

            self.context["entities"].append({
                "name": entity_name,
                "file": entity.get("file_path", ""),
                "table": entity.get("table", entity_name.lower()),
                "fields": field_list,
                "relationships": relationships,
                "purpose": f"Represents {self._camel_to_words(entity_name)} data"
            })

    def _store_endpoints(self, endpoints):
        """Store detailed endpoint information."""
        for ep in (endpoints or []):
            self.context["endpoints"].append({
                "method": ep.get("method", "GET"),
                "path": ep.get("path", ""),
                "controller": ep.get("controller", ""),
                "handler": ep.get("handler", ""),
                "parameters": ep.get("parameters", []),
                "description": self._infer_endpoint_purpose(ep)
            })

    def _analyze_configuration(self, config):
        """Analyze configuration properties."""
        if not config:
            return

        self.context["configuration"] = {
            "profiles": config.get("profiles", []),
            "database": self._extract_db_config(config),
            "server": self._extract_server_config(config),
            "security": self._extract_security_config(config),
            "custom": self._extract_custom_config(config)
        }

    def _store_dependencies(self, dependencies):
        """Store dependency information."""
        if not dependencies:
            return

        self.context["dependencies"] = {
            "build_tool": dependencies.get("build_tool", "unknown"),
            "java_version": dependencies.get("java_version", ""),
            "spring_boot_version": dependencies.get("spring_boot_version", ""),
            "key_dependencies": self._extract_key_deps(dependencies),
            "categories": dependencies.get("categories", {})
        }

    def _build_call_flows(self, methods):
        """Build common call flows (Controller -> Service -> Repository)."""
        # This is simplified - in real implementation would trace actual calls
        flows = []

        # Find controller methods that call services
        for method in (methods or []):
            if "Controller" in method.get("class_name", ""):
                calls = method.get("calls", [])
                for call in calls:
                    if "Service" in call:
                        flows.append({
                            "entry": f"{method.get('class_name')}.{method.get('name')}",
                            "calls": call,
                            "type": "controller_to_service"
                        })

        self.context["call_flows"] = flows[:20]  # Top 20 flows

    def _build_summaries(self):
        """Build quick lookup summaries for common questions."""
        project = self.context["project"]
        services = self.context["services"]
        controllers = self.context["controllers"]
        entities = self.context["entities"]
        endpoints = self.context["endpoints"]

        # What does this project do?
        self.context["summaries"]["project_overview"] = project.get("description", "")

        # What are the main services?
        if services:
            svc_list = ", ".join([s["name"] for s in services[:5]])
            self.context["summaries"]["services_overview"] = f"Main services: {svc_list}"

        # What endpoints are available?
        if endpoints:
            ep_examples = [f"{e['method']} {e['path']}" for e in endpoints[:5]]
            self.context["summaries"]["endpoints_overview"] = f"API endpoints include: {', '.join(ep_examples)}"

        # What data models exist?
        if entities:
            entity_list = ", ".join([e["name"] for e in entities])
            self.context["summaries"]["entities_overview"] = f"Data models: {entity_list}"

        # Full project summary
        full_summary_parts = [project.get("description", "")]
        if services:
            full_summary_parts.append(f"It has {len(services)} services: {', '.join([s['name'] for s in services[:3]])}.")
        if endpoints:
            full_summary_parts.append(f"Exposes {len(endpoints)} REST endpoints.")
        if entities:
            full_summary_parts.append(f"Manages {len(entities)} data entities: {', '.join([e['name'] for e in entities[:3]])}.")

        self.context["summaries"]["full_summary"] = " ".join(full_summary_parts)

    # Helper methods

    def _has_annotation(self, class_info: Dict, annotation: str) -> bool:
        """Check if class has annotation."""
        annotations = class_info.get("annotations", [])
        return any(annotation in str(a) for a in annotations)

    def _infer_purpose_from_name(self, name: str, suffix: str) -> str:
        """Infer purpose from class name."""
        # Remove suffix
        base = name.replace(suffix, "")
        words = self._camel_to_words(base)
        return f"Handles {words} operations."

    def _infer_endpoint_purpose(self, endpoint: Dict) -> str:
        """Infer endpoint purpose from method and path."""
        method = endpoint.get("method", "GET")
        path = endpoint.get("path", "")
        handler = endpoint.get("handler", "")

        # Extract resource from path
        parts = [p for p in path.split("/") if p and not p.startswith("{")]
        resource = parts[-1] if parts else "resource"

        actions = {
            "GET": "Retrieves",
            "POST": "Creates",
            "PUT": "Updates",
            "PATCH": "Partially updates",
            "DELETE": "Deletes"
        }

        action = actions.get(method, "Handles")
        return f"{action} {resource}"

    def _extract_base_path(self, controller: Dict) -> str:
        """Extract base path from controller annotations."""
        annotations = controller.get("annotations", [])
        for ann in annotations:
            if "RequestMapping" in str(ann):
                # Try to extract path
                if isinstance(ann, dict):
                    return ann.get("value", "")
        return ""

    def _camel_to_words(self, name: str) -> str:
        """Convert CamelCase to words."""
        import re
        if not name:
            return ""
        words = re.sub(r'([A-Z])', r' \1', name).strip().lower()
        return words

    def _extract_db_config(self, config: Dict) -> Dict:
        """Extract database configuration."""
        props = config.get("properties", {})
        return {
            "url": props.get("spring.datasource.url", ""),
            "driver": props.get("spring.datasource.driver-class-name", "")
        }

    def _extract_server_config(self, config: Dict) -> Dict:
        """Extract server configuration."""
        props = config.get("properties", {})
        return {
            "port": props.get("server.port", "8080"),
            "context_path": props.get("server.servlet.context-path", "/")
        }

    def _extract_security_config(self, config: Dict) -> Dict:
        """Extract security configuration."""
        props = config.get("properties", {})
        security_props = {k: v for k, v in props.items() if "security" in k.lower()}
        return {"enabled": len(security_props) > 0}

    def _extract_custom_config(self, config: Dict) -> Dict:
        """Extract custom application properties."""
        props = config.get("properties", {})
        # Filter out spring.* properties
        custom = {k: v for k, v in props.items()
                  if not k.startswith("spring.") and not k.startswith("server.")}
        return dict(list(custom.items())[:10])  # Top 10

    def _extract_key_deps(self, dependencies: Dict) -> List[str]:
        """Extract key dependencies."""
        deps = dependencies.get("dependencies", [])
        key_deps = []

        for dep in deps:
            artifact = dep.get("artifact", "")
            if any(kw in artifact for kw in ["spring-boot-starter", "spring-security", "spring-data"]):
                key_deps.append(artifact)

        return key_deps[:10]

    def _save_context(self):
        """Save context to file."""
        try:
            os.makedirs(self.index_path, exist_ok=True)
            context_file = os.path.join(self.index_path, self.CONTEXT_FILE)
            with open(context_file, 'w', encoding='utf-8') as f:
                json.dump(self.context, f, indent=2)
        except Exception:
            pass

    @classmethod
    def load_context(cls) -> Optional[Dict[str, Any]]:
        """Load saved context from file."""
        try:
            index_path = get_index_path()
            context_file = os.path.join(index_path, cls.CONTEXT_FILE)
            if os.path.exists(context_file):
                with open(context_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    @classmethod
    def get_quick_answer(cls, question_type: str) -> Optional[str]:
        """Get quick answer from cached context."""
        context = cls.load_context()
        if not context:
            return None

        summaries = context.get("summaries", {})

        # Map question types to summaries
        if question_type in ["project", "overview", "about", "what"]:
            return summaries.get("full_summary")
        elif question_type in ["services"]:
            return summaries.get("services_overview")
        elif question_type in ["endpoints", "api"]:
            return summaries.get("endpoints_overview")
        elif question_type in ["entities", "models", "data"]:
            return summaries.get("entities_overview")

        return summaries.get("full_summary")
