"""Tools package for nix agent."""

from tools.dependency_analyzer import register as register_dependency_analyzer
from tools.code_analyzer import register as register_code_analyzer
from tools.file_reader import register as register_file_reader
from tools.project_explorer import register as register_project_explorer
from tools.endpoint_analyzer import register as register_endpoint_analyzer
from tools.config_analyzer import register as register_config_analyzer
from tools.code_search import register as register_code_search
from tools.bean_analyzer import register as register_bean_analyzer
from tools.entity_analyzer import register as register_entity_analyzer
from tools.full_analyzer import register as register_full_analyzer
from tools.code_describer import register as register_code_describer

# Phase 3: Issue finding tools
from tools.build_runner import register as register_build_runner
from tools.test_runner import register as register_test_runner
from tools.error_tracer import register as register_error_tracer
from tools.call_chain_finder import register as register_call_chain_finder
from tools.null_safety_checker import register as register_null_safety_checker
from tools.bean_wiring_checker import register as register_bean_wiring_checker
from tools.annotation_checker import register as register_annotation_checker
from tools.issue_finder import register as register_issue_finder
from tools.fix_suggester import register as register_fix_suggester
from tools.semantic_search import register as register_semantic_search
from tools.error_diagnostics import register as register_error_diagnostics
from tools.smart_query import register as register_smart_query


def register_all_tools():
    """Register all available tools with the registry."""
    # Core analysis tools
    register_dependency_analyzer()
    register_code_analyzer()

    # File tools
    register_file_reader()
    register_project_explorer()

    # Spring-specific analysis
    register_endpoint_analyzer()
    register_config_analyzer()
    register_bean_analyzer()
    register_entity_analyzer()

    # Code search
    register_code_search()

    # Full analysis (combines all)
    register_full_analyzer()

    # Code describer (local parsing, no LLM tokens)
    register_code_describer()

    # Phase 3: Issue finding tools
    register_build_runner()
    register_test_runner()
    register_error_tracer()
    register_call_chain_finder()
    register_null_safety_checker()
    register_bean_wiring_checker()
    register_annotation_checker()
    register_issue_finder()
    register_fix_suggester()

    # Phase 4: Semantic search (RAG)
    register_semantic_search()

    # Phase 5: Comprehensive error diagnostics
    register_error_diagnostics()

    # Phase 6: Smart query (uses cached context - no LLM)
    register_smart_query()
