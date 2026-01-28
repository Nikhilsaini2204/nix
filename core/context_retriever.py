"""Smart context retriever - fetches only relevant context for each query."""

import json
import re
from typing import Dict, List, Any, Optional
from indexer.context_builder import ContextBuilder


# Maximum tokens we want to send as context (roughly 4 chars per token)
MAX_CONTEXT_CHARS = 6000  # ~1500 tokens for context, leaving room for system prompt and response


class ContextRetriever:
    """Retrieves relevant context for queries without sending entire codebase."""

    def __init__(self):
        self.context = ContextBuilder.load_context()
        self._keywords_cache = {}

    def get_relevant_context(self, query: str) -> str:
        """
        Get only the relevant context for a query.
        Returns a compact string suitable for LLM consumption.

        Args:
            query: User's question/query

        Returns:
            Compact context string
        """
        if not self.context:
            return "No project context available. Please run 'nix init' first."

        query_lower = query.lower()
        context_parts = []

        # Always include brief project overview
        project = self.context.get("project", {})
        if project:
            context_parts.append(f"Project: {project.get('description', 'Spring Boot application')}")
            stats = project.get("stats", {})
            if stats:
                context_parts.append(
                    f"Stats: {stats.get('controllers', 0)} controllers, "
                    f"{stats.get('services', 0)} services, "
                    f"{stats.get('endpoints', 0)} endpoints, "
                    f"{stats.get('entities', 0)} entities"
                )

        # Determine what context is relevant based on query
        needs_endpoints = self._query_needs(query_lower, ["endpoint", "api", "rest", "url", "path", "route", "get", "post", "put", "delete", "request", "mapping"])
        needs_services = self._query_needs(query_lower, ["service", "business", "logic", "layer"])
        needs_entities = self._query_needs(query_lower, ["entity", "model", "table", "database", "jpa", "field", "column", "relationship"])
        needs_controllers = self._query_needs(query_lower, ["controller", "handler", "rest", "api"])
        needs_config = self._query_needs(query_lower, ["config", "property", "properties", "application.yml", "application.properties", "setting", "port", "database", "datasource"])
        needs_dependencies = self._query_needs(query_lower, ["dependency", "dependencies", "pom", "gradle", "library", "version", "spring boot"])
        needs_repos = self._query_needs(query_lower, ["repository", "repo", "dao", "data access", "crud"])

        # If query is general/vague, include summaries of everything
        is_general = self._query_needs(query_lower, ["overview", "explain", "describe", "what is", "tell me about", "summary", "structure", "architecture", "how does"])

        if is_general or not any([needs_endpoints, needs_services, needs_entities, needs_controllers, needs_config, needs_dependencies, needs_repos]):
            # General query - include brief summaries
            summaries = self.context.get("summaries", {})
            if summaries.get("full_summary"):
                context_parts.append(f"\n{summaries['full_summary']}")
            needs_endpoints = needs_services = needs_entities = True  # Include some of each

        # Add relevant endpoints
        if needs_endpoints:
            endpoints = self._get_relevant_endpoints(query_lower)
            if endpoints:
                context_parts.append(f"\nEndpoints ({len(endpoints)} shown):")
                for ep in endpoints[:15]:  # Max 15 endpoints
                    desc = ep.get('description', '')
                    context_parts.append(f"  {ep.get('method', 'GET')} {ep.get('path', '')} - {desc}")

        # Add relevant services
        if needs_services:
            services = self._get_relevant_services(query_lower)
            if services:
                context_parts.append(f"\nServices ({len(services)} shown):")
                for svc in services[:10]:  # Max 10 services
                    methods = svc.get('methods', [])[:5]
                    context_parts.append(f"  {svc.get('name', '')}: {svc.get('purpose', '')}")
                    if methods:
                        context_parts.append(f"    Methods: {', '.join(methods)}")

        # Add relevant entities
        if needs_entities:
            entities = self._get_relevant_entities(query_lower)
            if entities:
                context_parts.append(f"\nEntities ({len(entities)} shown):")
                for entity in entities[:10]:  # Max 10 entities
                    fields = [f.get('name', '') for f in entity.get('fields', [])[:5]]
                    rels = entity.get('relationships', [])
                    context_parts.append(f"  {entity.get('name', '')}: {entity.get('purpose', '')}")
                    if fields:
                        context_parts.append(f"    Fields: {', '.join(fields)}")
                    if rels:
                        context_parts.append(f"    Relationships: {', '.join(str(r) for r in rels[:3])}")

        # Add relevant controllers
        if needs_controllers:
            controllers = self._get_relevant_controllers(query_lower)
            if controllers:
                context_parts.append(f"\nControllers ({len(controllers)} shown):")
                for ctrl in controllers[:8]:
                    context_parts.append(f"  {ctrl.get('name', '')}: {ctrl.get('purpose', '')} ({ctrl.get('endpoint_count', 0)} endpoints)")

        # Add relevant config
        if needs_config:
            config = self.context.get("configuration", {})
            if config:
                context_parts.append("\nConfiguration:")
                if config.get("server"):
                    server = config["server"]
                    context_parts.append(f"  Server: port={server.get('port', '8080')}, context={server.get('context_path', '/')}")
                if config.get("database"):
                    db = config["database"]
                    if db.get("url"):
                        context_parts.append(f"  Database: {db.get('url', '')[:50]}...")
                if config.get("profiles"):
                    context_parts.append(f"  Profiles: {', '.join(config['profiles'][:5])}")

        # Add relevant dependencies
        if needs_dependencies:
            deps = self.context.get("dependencies", {})
            if deps:
                context_parts.append("\nDependencies:")
                context_parts.append(f"  Spring Boot: {deps.get('spring_boot_version', 'unknown')}")
                context_parts.append(f"  Java: {deps.get('java_version', 'unknown')}")
                key_deps = deps.get("key_dependencies", [])[:8]
                if key_deps:
                    context_parts.append(f"  Key: {', '.join(key_deps)}")

        # Add repositories if needed
        if needs_repos:
            repos = self.context.get("repositories", [])
            if repos:
                context_parts.append(f"\nRepositories ({len(repos)} total):")
                for repo in repos[:8]:
                    context_parts.append(f"  {repo.get('name', '')}: {repo.get('purpose', '')}")

        # Build final context and truncate if needed
        context_str = "\n".join(context_parts)

        if len(context_str) > MAX_CONTEXT_CHARS:
            context_str = context_str[:MAX_CONTEXT_CHARS] + "\n... (truncated for brevity)"

        return context_str

    def _query_needs(self, query: str, keywords: List[str]) -> bool:
        """Check if query needs certain type of context."""
        return any(kw in query for kw in keywords)

    def _get_relevant_endpoints(self, query: str) -> List[Dict]:
        """Get endpoints relevant to the query."""
        endpoints = self.context.get("endpoints", [])
        if not endpoints:
            return []

        # Extract search terms from query
        search_terms = self._extract_search_terms(query)

        # Score and sort endpoints by relevance
        scored = []
        for ep in endpoints:
            score = self._score_relevance(ep, search_terms, ["path", "handler", "controller", "description"])
            scored.append((score, ep))

        # Sort by score and return top matches
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for score, ep in scored if score > 0][:15] or endpoints[:10]

    def _get_relevant_services(self, query: str) -> List[Dict]:
        """Get services relevant to the query."""
        services = self.context.get("services", [])
        if not services:
            return []

        search_terms = self._extract_search_terms(query)

        scored = []
        for svc in services:
            score = self._score_relevance(svc, search_terms, ["name", "purpose"])
            # Also check method names
            for method in svc.get("methods", []):
                if any(term in method.lower() for term in search_terms):
                    score += 1
            scored.append((score, svc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [svc for score, svc in scored if score > 0][:10] or services[:5]

    def _get_relevant_entities(self, query: str) -> List[Dict]:
        """Get entities relevant to the query."""
        entities = self.context.get("entities", [])
        if not entities:
            return []

        search_terms = self._extract_search_terms(query)

        scored = []
        for entity in entities:
            score = self._score_relevance(entity, search_terms, ["name", "table", "purpose"])
            # Also check field names
            for field in entity.get("fields", []):
                if any(term in field.get("name", "").lower() for term in search_terms):
                    score += 1
            scored.append((score, entity))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for score, e in scored if score > 0][:10] or entities[:5]

    def _get_relevant_controllers(self, query: str) -> List[Dict]:
        """Get controllers relevant to the query."""
        controllers = self.context.get("controllers", [])
        if not controllers:
            return []

        search_terms = self._extract_search_terms(query)

        scored = []
        for ctrl in controllers:
            score = self._score_relevance(ctrl, search_terms, ["name", "purpose", "base_path"])
            scored.append((score, ctrl))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for score, c in scored if score > 0][:8] or controllers[:5]

    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract meaningful search terms from query."""
        # Remove common words
        stop_words = {"the", "a", "an", "is", "are", "what", "how", "where", "which", "show", "me",
                      "list", "all", "find", "get", "tell", "about", "my", "this", "that", "for",
                      "in", "on", "to", "of", "and", "or", "with", "can", "do", "does", "have", "has"}

        words = re.findall(r'\b\w+\b', query.lower())
        terms = [w for w in words if w not in stop_words and len(w) > 2]
        return terms

    def _score_relevance(self, item: Dict, search_terms: List[str], fields: List[str]) -> int:
        """Score item relevance based on search terms."""
        score = 0
        for field in fields:
            value = str(item.get(field, "")).lower()
            for term in search_terms:
                if term in value:
                    score += 2 if field == "name" else 1
        return score

    def get_compact_project_summary(self) -> str:
        """Get a very compact project summary for system prompt."""
        if not self.context:
            return ""

        project = self.context.get("project", {})
        stats = project.get("stats", {})

        parts = [project.get("description", "Spring Boot application")]
        if stats:
            parts.append(f"({stats.get('endpoints', 0)} endpoints, {stats.get('services', 0)} services, {stats.get('entities', 0)} entities)")

        return " ".join(parts)


# Global retriever instance
_retriever_instance = None


def get_retriever() -> ContextRetriever:
    """Get or create the global retriever instance."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = ContextRetriever()
    return _retriever_instance


def reset_retriever():
    """Reset the retriever (reload context)."""
    global _retriever_instance
    _retriever_instance = None


def get_relevant_context(query: str) -> str:
    """Get relevant context for a query."""
    return get_retriever().get_relevant_context(query)
