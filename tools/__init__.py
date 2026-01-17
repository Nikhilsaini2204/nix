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
