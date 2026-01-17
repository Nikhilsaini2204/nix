"""Agentic loop for natural language processing."""

import json
from llm.client import call_groq_with_tools, RateLimitExhaustedError
from llm.system_prompts import get_system_prompt
from core.tools_registry import get_tool_definitions, execute_tool, validate_tool_call


MAX_ITERATIONS = 10
MAX_TOOL_RESULT_SIZE = 8000  # Limit tool results to prevent context overflow


def truncate_result(result, max_size=MAX_TOOL_RESULT_SIZE):
    """Truncate large tool results to prevent context overflow."""
    result_str = json.dumps(result)
    if len(result_str) <= max_size:
        return result

    # If result has a 'tree' field (from explore_project), truncate it
    if isinstance(result, dict):
        if 'tree' in result and len(result['tree']) > max_size // 2:
            result = result.copy()
            result['tree'] = result['tree'][:max_size // 2] + "\n... (truncated)"
            result['truncated'] = True
            return result

        # If result has 'results' list (from search_code), limit entries
        if 'results' in result and isinstance(result['results'], list):
            result = result.copy()
            if len(json.dumps(result['results'])) > max_size:
                result['results'] = result['results'][:20]
                result['truncated'] = True
            return result

        # If result has 'dependencies' list, limit entries
        if 'dependencies' in result and isinstance(result['dependencies'], list):
            result = result.copy()
            if len(result['dependencies']) > 50:
                result['dependencies'] = result['dependencies'][:50]
                result['truncated'] = True
            return result

        # If result has 'classes' list, limit entries
        if 'classes' in result and isinstance(result['classes'], list):
            result = result.copy()
            if len(result['classes']) > 30:
                result['classes'] = result['classes'][:30]
                result['truncated'] = True
            return result

    return result


class Agent:
    """Stateful agent that maintains conversation history."""

    MAX_HISTORY_LENGTH = 12  # Keep last N messages to avoid context overflow

    def __init__(self):
        self.conversation_history = [
            {"role": "system", "content": get_system_prompt()}
        ]
        self.tools = get_tool_definitions()

    def _trim_history(self):
        """Trim conversation history to avoid context overflow."""
        if len(self.conversation_history) > self.MAX_HISTORY_LENGTH:
            # Keep system prompt + last N messages
            system_prompt = self.conversation_history[0]
            recent = self.conversation_history[-(self.MAX_HISTORY_LENGTH - 1):]
            self.conversation_history = [system_prompt] + recent

    def run(self, user_input):
        """
        Process user input and return response.

        Args:
            user_input: Natural language from user

        Returns:
            Response string
        """
        # Trim history to avoid context overflow
        self._trim_history()

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })

        # Track tool calls for loop detection within this turn
        turn_tool_calls = []
        last_tool_results = None  # Store for rate limit fallback

        for iteration in range(MAX_ITERATIONS):
            try:
                # Call LLM with full history and tools
                response = call_groq_with_tools(self.conversation_history, self.tools)

                # Check if LLM wants to call tools
                if response.get("tool_calls"):
                    tool_results = self._process_tool_calls(
                        response["tool_calls"],
                        turn_tool_calls
                    )
                    last_tool_results = tool_results  # Save for fallback

                    if tool_results.get("loop_detected"):
                        assistant_msg = "I seem to be repeating myself. Let me summarize what I found."
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": assistant_msg
                        })
                        return assistant_msg

                    # Add assistant message with tool calls to history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response.get("content") or "",
                        "tool_calls": self._format_tool_calls(response["tool_calls"])
                    })

                    # Add tool results to history
                    for tool_result in tool_results["results"]:
                        self.conversation_history.append({
                            "role": "tool",
                            "tool_call_id": tool_result["id"],
                            "content": json.dumps(tool_result["result"])
                        })

                    # Track for loop detection
                    turn_tool_calls.extend(
                        (tc["name"], json.dumps(tc["arguments"], sort_keys=True))
                        for tc in response["tool_calls"]
                    )

                    # Check if any tool wants to skip LLM response (self-sufficient tools)
                    for tool_result in tool_results["results"]:
                        result = tool_result.get("result", {})
                        if isinstance(result, dict) and result.get("_skip_llm"):
                            msg = result.get("_message", "Done.")
                            self.conversation_history.append({
                                "role": "assistant",
                                "content": result.get("summary", msg)
                            })
                            return msg

                    continue

                # No tool calls - LLM has final answer
                content = response.get("content")
                if content:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": content
                    })
                    return content
                else:
                    msg = "I couldn't generate a response. Please try rephrasing."
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": msg
                    })
                    return msg

            except RateLimitExhaustedError as e:
                # If we have tool results, use them instead of failing
                if last_tool_results:
                    for tr in last_tool_results.get("results", []):
                        result = tr.get("result", {})
                        if isinstance(result, dict):
                            summary = result.get("summary", "Analysis complete. See output above.")
                            self.conversation_history.append({
                                "role": "assistant",
                                "content": summary
                            })
                            return summary
                    return "Analysis complete. See the output above for details."
                # No tool results - show rate limit message
                from utils.output import warn
                return warn(str(e))
            except Exception as e:
                error_msg = f"An error occurred: {str(e)}"
                return error_msg

        # Max iterations reached
        msg = "I've done multiple analysis steps. Here's what I found based on the results above."
        self.conversation_history.append({
            "role": "assistant",
            "content": msg
        })
        return msg

    def _process_tool_calls(self, tool_calls, previous_calls):
        """Process tool calls and return results."""
        from utils.output import color, Colors

        # Show tool count in purple
        if len(tool_calls) == 1:
            print(color(f"\nUsing 1 tool...", Colors.MAGENTA))
        else:
            print(color(f"\nUsing {len(tool_calls)} tools...", Colors.MAGENTA))

        results = []
        loop_detected = False

        for tool_call in tool_calls:
            name = tool_call["name"]
            arguments = tool_call["arguments"]

            # Loop detection
            call_signature = (name, json.dumps(arguments, sort_keys=True))
            if call_signature in previous_calls:
                loop_detected = True
                results.append({
                    "id": tool_call["id"],
                    "result": {"error": "Already called with same arguments"}
                })
                continue

            # Validate
            is_valid, error = validate_tool_call(name, arguments)
            if not is_valid:
                results.append({
                    "id": tool_call["id"],
                    "result": {"error": error}
                })
                continue

            # Execute (silently - tool will print its own progress)
            result = execute_tool(name, arguments)

            # Truncate large results to prevent context overflow
            result = truncate_result(result)

            results.append({
                "id": tool_call["id"],
                "result": result
            })

        return {"results": results, "loop_detected": loop_detected}

    def _format_tool_calls(self, tool_calls):
        """Format tool calls for conversation history."""
        return [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc["arguments"])
                }
            }
            for tc in tool_calls
        ]

    def clear_history(self):
        """Clear conversation history (keep system prompt)."""
        self.conversation_history = [
            {"role": "system", "content": get_system_prompt()}
        ]


# Global agent instance for REPL
_agent_instance = None


def get_agent():
    """Get or create the global agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = Agent()
    return _agent_instance


def reset_agent():
    """Reset the agent (clear history)."""
    global _agent_instance
    _agent_instance = None


def run_agent(user_input):
    """
    Run the agent with user input.
    Maintains conversation history across calls.

    Args:
        user_input: Natural language from user

    Returns:
        Response string
    """
    agent = get_agent()
    return agent.run(user_input)
