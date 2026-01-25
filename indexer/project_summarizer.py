"""Project summarizer for generating high-level codebase understanding."""

import os
import re
import json
from typing import Dict, List, Any, Optional
from collections import Counter

from config import get_index_path, get_project_root


def generate_project_summary(
    classes: List[Dict] = None,
    methods: List[Dict] = None,
    endpoints: List[Dict] = None,
    entities: List[Dict] = None,
    config: Dict = None,
    dependencies: Dict = None,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Generate a comprehensive understanding of what the project does.

    This analyzes the codebase structure, naming patterns, and components
    to produce a human-readable summary of the project's purpose.

    Args:
        classes: List of class information dicts
        methods: List of method information dicts
        endpoints: List of REST endpoint dicts
        entities: List of JPA entity dicts
        config: Configuration analysis dict
        dependencies: Dependency analysis dict
        use_llm: Whether to use LLM for final summary generation

    Returns:
        Dict with project understanding:
        - summary: Natural language description
        - domains: Business domains identified
        - purpose: Inferred purpose (api, web, batch, etc.)
        - key_features: Main features/capabilities
        - tech_stack: Technologies detected
    """
    context = ProjectContext()

    # Analyze each component
    if classes:
        context.analyze_classes(classes)
    if methods:
        context.analyze_methods(methods)
    if endpoints:
        context.analyze_endpoints(endpoints)
    if entities:
        context.analyze_entities(entities)
    if config:
        context.analyze_config(config)
    if dependencies:
        context.analyze_dependencies(dependencies)

    # Generate the summary (try LLM first, fallback to rules)
    summary = None
    if use_llm:
        try:
            summary = context.generate_llm_summary()
        except Exception:
            pass

    # Fallback to rule-based if LLM failed or not used
    if not summary:
        summary = context.generate_rule_based_summary()

    return {
        "summary": summary,
        "domains": context.domains,
        "purpose": context.purpose,
        "key_features": context.features,
        "tech_stack": context.tech_stack,
        "components": {
            "controllers": context.controllers,
            "services": context.services,
            "repositories": context.repositories,
            "entities": context.entity_names
        },
        "stats": context.stats
    }


class ProjectContext:
    """Collects and analyzes project information to build understanding."""

    # Common domain keywords to detect
    DOMAIN_KEYWORDS = {
        "ecommerce": ["order", "cart", "product", "payment", "checkout", "invoice", "shop", "store", "catalog", "price"],
        "authentication": ["auth", "login", "logout", "user", "password", "token", "session", "credential", "oauth", "jwt"],
        "messaging": ["message", "chat", "notification", "email", "sms", "push", "inbox", "conversation"],
        "booking": ["booking", "reservation", "appointment", "schedule", "calendar", "slot", "availability"],
        "content": ["article", "post", "blog", "content", "comment", "media", "document", "file", "upload"],
        "social": ["friend", "follow", "like", "share", "feed", "profile", "social", "connection"],
        "analytics": ["metric", "report", "analytics", "dashboard", "statistics", "tracking", "event"],
        "finance": ["account", "transaction", "balance", "transfer", "bank", "wallet", "ledger", "money"],
        "inventory": ["inventory", "stock", "warehouse", "supply", "item", "quantity"],
        "crm": ["customer", "lead", "contact", "client", "opportunity", "sales", "deal"],
        "hr": ["employee", "staff", "leave", "payroll", "attendance", "department", "position"],
    }

    # Application type indicators
    APP_TYPE_INDICATORS = {
        "rest_api": ["RestController", "GetMapping", "PostMapping", "RequestMapping", "ResponseBody"],
        "web_app": ["Controller", "ThymeLeaf", "Model", "View", "template"],
        "batch": ["Scheduled", "Job", "Step", "Tasklet", "Batch"],
        "microservice": ["FeignClient", "Eureka", "Config", "Gateway", "Discovery"],
        "graphql": ["GraphQL", "Query", "Mutation", "Resolver"],
    }

    def __init__(self):
        self.domains = []
        self.purpose = "application"
        self.features = []
        self.tech_stack = []
        self.controllers = []
        self.services = []
        self.repositories = []
        self.entity_names = []
        self.endpoint_patterns = []
        self.all_names = []  # Collect all class/method names for domain detection
        self.stats = {}
        self.config_hints = []
        self.package_name = None

    def analyze_classes(self, classes: List[Dict]):
        """Analyze class information."""
        self.stats["classes"] = len(classes)

        for cls in classes:
            name = cls.get("name", "")
            annotations = cls.get("annotations", [])
            package = cls.get("package", "")

            # Extract package name (first 2-3 parts)
            if package and not self.package_name:
                parts = package.split(".")
                if len(parts) >= 2:
                    self.package_name = ".".join(parts[:3])

            self.all_names.append(name.lower())

            # Categorize by stereotype
            if any("Controller" in a for a in annotations):
                self.controllers.append(name)
            elif any("Service" in a for a in annotations):
                self.services.append(name)
            elif any("Repository" in a for a in annotations):
                self.repositories.append(name)

            # Detect app type from annotations
            for app_type, indicators in self.APP_TYPE_INDICATORS.items():
                if any(ind in str(annotations) for ind in indicators):
                    if app_type not in self.features:
                        self.features.append(app_type)

    def analyze_methods(self, methods: List[Dict]):
        """Analyze method information."""
        self.stats["methods"] = len(methods)

        for method in methods:
            name = method.get("name", "")
            self.all_names.append(name.lower())

            # Check for summaries (from semantic index)
            summary = method.get("summary", "")
            if summary:
                # Extract key verbs and nouns from summaries
                words = summary.lower().split()
                self.all_names.extend(words)

    def analyze_endpoints(self, endpoints: List[Dict]):
        """Analyze REST endpoints."""
        if not endpoints:
            return

        self.stats["endpoints"] = len(endpoints)

        # Group by path patterns
        path_segments = []
        methods_used = set()

        for ep in endpoints:
            path = ep.get("path", "")
            method = ep.get("method", "GET")
            methods_used.add(method)

            # Extract meaningful path segments
            segments = [s for s in path.split("/") if s and not s.startswith("{")]
            path_segments.extend(segments)

            # Store patterns
            if path:
                self.endpoint_patterns.append(path)

        # Count path segments to identify main resources
        segment_counts = Counter(path_segments)
        top_resources = [seg for seg, _ in segment_counts.most_common(5)]

        self.all_names.extend(top_resources)

        # Detect API style
        if methods_used == {"GET", "POST", "PUT", "DELETE"} or len(methods_used) >= 3:
            if "rest_api" not in self.features:
                self.features.append("rest_api")

    def analyze_entities(self, entities: List[Dict]):
        """Analyze JPA entities."""
        if not entities:
            return

        self.stats["entities"] = len(entities)

        for entity in entities:
            name = entity.get("name", "")
            self.entity_names.append(name)
            self.all_names.append(name.lower())

        if self.entity_names:
            self.tech_stack.append("JPA/Hibernate")

    def analyze_config(self, config: Dict):
        """Analyze configuration for hints."""
        if not config:
            return

        properties = config.get("properties", {})
        profiles = config.get("profiles", [])

        self.stats["config_properties"] = len(properties)

        # Check for technology indicators in config
        config_str = str(properties).lower()

        if "redis" in config_str:
            self.tech_stack.append("Redis")
        if "kafka" in config_str:
            self.tech_stack.append("Kafka")
        if "rabbitmq" in config_str or "amqp" in config_str:
            self.tech_stack.append("RabbitMQ")
        if "mongodb" in config_str:
            self.tech_stack.append("MongoDB")
        if "elasticsearch" in config_str:
            self.tech_stack.append("Elasticsearch")
        if "mysql" in config_str:
            self.tech_stack.append("MySQL")
        if "postgresql" in config_str or "postgres" in config_str:
            self.tech_stack.append("PostgreSQL")
        if "oauth" in config_str or "jwt" in config_str:
            self.tech_stack.append("OAuth/JWT")

        # Store profiles
        if profiles:
            self.config_hints.extend(profiles)

    def analyze_dependencies(self, deps: Dict):
        """Analyze dependencies for tech stack."""
        if not deps:
            return

        dep_list = deps.get("dependencies", [])
        self.stats["dependencies"] = len(dep_list)

        for dep in dep_list:
            artifact = dep.get("artifact", "").lower()
            group = dep.get("group", "").lower()

            # Detect technologies
            if "spring-boot-starter-web" in artifact:
                self.tech_stack.append("Spring Web")
            if "spring-boot-starter-data-jpa" in artifact:
                self.tech_stack.append("Spring Data JPA")
            if "spring-security" in artifact:
                self.tech_stack.append("Spring Security")
            if "spring-cloud" in group:
                self.tech_stack.append("Spring Cloud")
            if "lombok" in artifact:
                self.tech_stack.append("Lombok")
            if "mapstruct" in artifact:
                self.tech_stack.append("MapStruct")
            if "swagger" in artifact or "springdoc" in artifact:
                self.tech_stack.append("OpenAPI/Swagger")
            if "flyway" in artifact:
                self.tech_stack.append("Flyway")
            if "liquibase" in artifact:
                self.tech_stack.append("Liquibase")

    def _detect_domains(self) -> List[str]:
        """Detect business domains from collected names."""
        detected = []
        name_text = " ".join(self.all_names)

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in name_text)
            if matches >= 2:  # At least 2 keyword matches
                detected.append(domain)

        return detected[:3]  # Top 3 domains

    def _infer_purpose(self) -> str:
        """Infer the main purpose of the application."""
        if "rest_api" in self.features:
            if len(self.entity_names) > 3:
                return "REST API backend"
            return "REST API service"
        elif "batch" in self.features:
            return "batch processing application"
        elif "microservice" in self.features:
            return "microservice"
        elif "graphql" in self.features:
            return "GraphQL API"
        elif "web_app" in self.features:
            return "web application"
        elif self.controllers:
            return "web service"
        else:
            return "Spring Boot application"

    def _extract_key_features(self) -> List[str]:
        """Extract key features from analysis."""
        features = []

        # From endpoints
        if self.stats.get("endpoints", 0) > 0:
            features.append(f"exposes {self.stats['endpoints']} REST endpoints")

        # From entities
        if self.entity_names:
            entity_str = ", ".join(self.entity_names[:3])
            if len(self.entity_names) > 3:
                entity_str += f" and {len(self.entity_names) - 3} more"
            features.append(f"manages data models: {entity_str}")

        # From services
        if len(self.services) > 2:
            features.append(f"has {len(self.services)} business services")

        # From tech stack
        if "Spring Security" in self.tech_stack:
            features.append("includes authentication/authorization")
        if any("SQL" in t or "Postgres" in t or "MongoDB" in t for t in self.tech_stack):
            features.append("uses database persistence")

        return features[:4]

    def generate_rule_based_summary(self) -> str:
        """Generate summary using rule-based approach (no LLM)."""
        self.domains = self._detect_domains()
        self.purpose = self._infer_purpose()
        self.features = self._extract_key_features()

        # Remove duplicates from tech stack
        self.tech_stack = list(dict.fromkeys(self.tech_stack))

        # Build summary
        parts = []

        # Main description
        if self.domains:
            domain_str = " and ".join(self.domains[:2])
            parts.append(f"This is a {domain_str} {self.purpose}")
        else:
            parts.append(f"This is a {self.purpose}")

        # Add entity info
        if self.entity_names:
            entity_examples = ", ".join(self.entity_names[:3])
            parts.append(f"that manages {entity_examples} data")

        # Add endpoint info
        if self.stats.get("endpoints", 0) > 0:
            parts.append(f"with {self.stats['endpoints']} REST endpoints")

        summary = " ".join(parts) + "."

        # Add tech highlights
        if self.tech_stack:
            tech_str = ", ".join(self.tech_stack[:4])
            summary += f" Built with {tech_str}."

        return summary

    def generate_llm_summary(self) -> str:
        """Generate summary using LLM for natural language."""
        # First get rule-based analysis
        self.domains = self._detect_domains()
        self.purpose = self._infer_purpose()
        self.features = self._extract_key_features()
        self.tech_stack = list(dict.fromkeys(self.tech_stack))

        # Build context for LLM
        context_parts = []

        if self.package_name:
            context_parts.append(f"Package: {self.package_name}")

        if self.controllers:
            context_parts.append(f"Controllers: {', '.join(self.controllers[:5])}")

        if self.services:
            context_parts.append(f"Services: {', '.join(self.services[:5])}")

        if self.entity_names:
            context_parts.append(f"Entities: {', '.join(self.entity_names[:5])}")

        if self.endpoint_patterns:
            context_parts.append(f"Endpoints: {', '.join(self.endpoint_patterns[:5])}")

        if self.domains:
            context_parts.append(f"Detected domains: {', '.join(self.domains)}")

        if self.tech_stack:
            context_parts.append(f"Tech stack: {', '.join(self.tech_stack[:5])}")

        context = "\n".join(context_parts)

        # Call LLM for natural summary
        try:
            summary = self._call_llm_for_summary(context)
            if summary:
                return summary
        except Exception:
            pass

        # Fallback to rule-based
        return self.generate_rule_based_summary()

    def _call_llm_for_summary(self, context: str) -> Optional[str]:
        """Call LLM to generate natural summary."""
        import requests
        from llm.client import get_api_key, GROQ_API_URL, AGENT_MODEL, FALLBACK_MODEL

        api_key = get_api_key()
        if not api_key:
            return None

        prompt = f"""Based on this Spring Boot project analysis, write a 2-3 sentence summary of what this project does.
Focus on the business purpose, not technical details. Write in plain English.

{context}

Write ONLY the summary, nothing else. Example format:
"This is an e-commerce backend that handles product catalog, shopping cart, and order processing. It provides REST APIs for a storefront application and manages customer accounts and payment integration."

Summary:"""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": AGENT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 200
        }

        try:
            response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=30)

            if response.status_code == 429:
                payload["model"] = FALLBACK_MODEL
                response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=30)

            if response.status_code >= 400:
                return None

            data = response.json()
            summary = data["choices"][0]["message"]["content"].strip()

            # Clean up the summary
            summary = summary.strip('"\'')
            if not summary.endswith('.'):
                summary += '.'

            return summary

        except Exception:
            return None


def save_project_context(context: Dict[str, Any]) -> bool:
    """Save project context to .nix folder.

    Args:
        context: Project context dictionary

    Returns:
        True if saved successfully
    """
    try:
        index_path = get_index_path()
        context_file = os.path.join(index_path, "project_context.json")

        from datetime import datetime
        context["generated_at"] = datetime.now().isoformat()

        with open(context_file, 'w', encoding='utf-8') as f:
            json.dump(context, f, indent=2)

        return True
    except Exception:
        return False


def load_project_context() -> Optional[Dict[str, Any]]:
    """Load project context from .nix folder.

    Returns:
        Project context dict or None if not found
    """
    try:
        index_path = get_index_path()
        context_file = os.path.join(index_path, "project_context.json")

        if os.path.exists(context_file):
            with open(context_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass

    return None


def get_project_summary() -> str:
    """Get cached project summary or generate if not available.

    Returns:
        Project summary string
    """
    context = load_project_context()
    if context and context.get("summary"):
        return context["summary"]
    return "Project context not available. Run 'nix init' to analyze the project."
