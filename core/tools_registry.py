"""Tool registry for managing and executing agent tools."""

import json

# Tool handlers will be registered here
_TOOL_HANDLERS = {}


def register_tool(name, handler, definition):
    """
    Register a tool with its handler and definition.

    Args:
        name: Tool name (must match definition)
        handler: Function to execute when tool is called
        definition: OpenAI-format tool definition
    """
    _TOOL_HANDLERS[name] = {
        "handler": handler,
        "definition": definition
    }


def get_tool_definitions():
    """
    Get all tool definitions in OpenAI function calling format.

    Returns:
        List of tool definitions for API calls
    """
    return [tool["definition"] for tool in _TOOL_HANDLERS.values()]


def execute_tool(name, arguments):
    """
    Execute a tool by name with given arguments.

    Args:
        name: Tool name to execute
        arguments: Dict of arguments to pass to tool

    Returns:
        Tool result as dict with summary and data
    """
    if name not in _TOOL_HANDLERS:
        return {
            "error": f"Unknown tool: {name}",
            "available_tools": list(_TOOL_HANDLERS.keys())
        }

    handler = _TOOL_HANDLERS[name]["handler"]

    try:
        result = handler(**arguments)
        return result
    except TypeError as e:
        return {
            "error": f"Invalid arguments for {name}: {str(e)}"
        }
    except Exception as e:
        return {
            "error": f"Tool execution failed: {str(e)}"
        }


def validate_tool_call(name, arguments):
    """
    Validate a tool call before execution.

    Args:
        name: Tool name
        arguments: Arguments dict

    Returns:
        (is_valid, error_message)
    """
    if name not in _TOOL_HANDLERS:
        return False, f"Unknown tool: {name}. Available: {list(_TOOL_HANDLERS.keys())}"

    return True, None


def get_available_tools():
    """Return list of available tool names."""
    return list(_TOOL_HANDLERS.keys())


# Tool definition helpers

def create_tool_definition(name, description, parameters=None, required=None):
    """
    Create an OpenAI-format tool definition.

    Args:
        name: Function name
        description: What the tool does
        parameters: Dict of parameter definitions (optional)
        required: List of required parameter names (optional, defaults to none)

    Returns:
        Tool definition dict
    """
    definition = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
        }
    }

    if parameters:
        definition["function"]["parameters"] = {
            "type": "object",
            "properties": parameters,
            "required": required or []
        }
    else:
        definition["function"]["parameters"] = {
            "type": "object",
            "properties": {},
            "required": []
        }

    return definition
