"""Agentic loop for natural language processing."""

import json
from llm.client import call_groq_with_tools, RateLimitExhaustedError, ContextTooLargeError
from llm.system_prompts import get_system_prompt
from core.tools_registry import get_tool_definitions, execute_tool, validate_tool_call
from core.tool_selector import select_tools_for_query, get_minimal_tool_definitions
from core.context_retriever import get_relevant_context, reset_retriever


MAX_ITERATIONS = 10
MAX_TOOL_RESULT_SIZE = 3000  # Reduced limit to prevent context overflow


def truncate_result(result, max_size=MAX_TOOL_RESULT_SIZE):
    """Truncate large tool results to prevent context overflow."""
    result_str = json.dumps(result)
    if len(result_str) <= max_size:
        return result

    if isinstance(result, dict):
        result = result.copy()

        # If result has a summary, prioritize keeping that
        summary = result.get('summary', '')

        # Aggressively truncate large lists
        list_fields = ['results', 'endpoints', 'services', 'entities', 'classes',
                       'methods', 'dependencies', 'issues', 'controllers', 'repositories']

        for field in list_fields:
            if field in result and isinstance(result[field], list):
                # Keep only first 10 items max
                if len(result[field]) > 10:
                    result[field] = result[field][:10]
                    result['truncated'] = True

        # Truncate tree field
        if 'tree' in result and len(str(result['tree'])) > 1000:
            result['tree'] = str(result['tree'])[:1000] + "\n... (truncated)"
            result['truncated'] = True

        # Remove verbose fields if still too large
        result_str = json.dumps(result)
        if len(result_str) > max_size:
            # Remove less important fields
            for field in ['file_path', 'file', 'source', 'code', 'content', 'details']:
                if field in result:
                    del result[field]

        # Final check - if still too large, keep only summary and counts
        result_str = json.dumps(result)
        if len(result_str) > max_size:
            compact = {'summary': summary, 'truncated': True}
            for field in list_fields:
                if field in result and isinstance(result[field], list):
                    compact[f'{field}_count'] = len(result[field])
                    compact[field] = result[field][:5]  # Keep only 5
            return compact

        return result

    return result


class Agent:
    """Stateful agent that maintains conversation history."""

    MAX_HISTORY_LENGTH = 8  # Keep last N messages to avoid context overflow
    MAX_HISTORY_CHARS = 8000  # Maximum characters in history (rough token estimate)

    def __init__(self):
        self.conversation_history = [
            {"role": "system", "content": get_system_prompt()}
        ]
        self.all_tools = get_tool_definitions()
        self.tools = self.all_tools  # Will be filtered per query

    def _trim_history(self):
        """Trim conversation history to avoid context overflow."""
        # First, trim by message count
        if len(self.conversation_history) > self.MAX_HISTORY_LENGTH:
            system_prompt = self.conversation_history[0]
            recent = self.conversation_history[-(self.MAX_HISTORY_LENGTH - 1):]
            self.conversation_history = [system_prompt] + recent

        # Then, trim by total size (more aggressive)
        total_chars = sum(len(json.dumps(msg)) for msg in self.conversation_history)
        while total_chars > self.MAX_HISTORY_CHARS and len(self.conversation_history) > 2:
            # Remove oldest non-system message
            self.conversation_history.pop(1)
            total_chars = sum(len(json.dumps(msg)) for msg in self.conversation_history)

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

        # Get relevant context for this query (smart retrieval - like Claude Code)
        relevant_context = get_relevant_context(user_input)

        # Build user message with context
        if relevant_context and not relevant_context.startswith("No project context"):
            # Include context only if it's meaningful and not too long
            if len(relevant_context) < 4000:
                user_message = f"[Project Context]\n{relevant_context}\n\n[User Question]\n{user_input}"
            else:
                # Context too long, truncate
                user_message = f"[Project Context]\n{relevant_context[:3000]}...\n\n[User Question]\n{user_input}"
        else:
            user_message = user_input

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Select relevant tools for this query (saves tokens!)
        selected_tools = select_tools_for_query(user_input, self.all_tools)
        self.tools = get_minimal_tool_definitions(selected_tools)

        # Track tool calls for loop detection within this turn
        turn_tool_calls = []
        last_tool_results = None  # Store for rate limit fallback

        for iteration in range(MAX_ITERATIONS):
            try:
                # Call LLM with full history and tools
                response = call_groq_with_tools(self.conversation_history, self.tools)

                # Check if LLM wants to call tools
                if response.get("tool_calls"):
                    # Pre-check for loops BEFORE executing tools
                    new_calls = []
                    for tc in response["tool_calls"]:
                        call_sig = (tc["name"], json.dumps(tc["arguments"], sort_keys=True))
                        if call_sig not in turn_tool_calls:
                            new_calls.append(tc)
                        else:
                            # Already called this tool with same args
                            pass

                    if not new_calls:
                        # All tools were already called - use previous results
                        if last_tool_results:
                            for tr in last_tool_results.get("results", []):
                                result = tr.get("result", {})
                                if isinstance(result, dict) and result.get("summary"):
                                    return result.get("summary")
                        return "I've already analyzed this. What specific aspect would you like to know more about?"

                    tool_results = self._process_tool_calls(
                        new_calls,  # Only process new calls
                        turn_tool_calls
                    )
                    last_tool_results = tool_results  # Save for fallback

                    if tool_results.get("loop_detected"):
                        # If we have results with _skip_llm, use those
                        for tr in tool_results.get("results", []):
                            result = tr.get("result", {})
                            if isinstance(result, dict) and result.get("_skip_llm"):
                                return result.get("_message", result.get("summary", "Analysis complete."))
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
                        "tool_calls": self._format_tool_calls(new_calls)
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
                        for tc in new_calls
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
                    # Check for off-topic marker - ONLY if no tools were called in this turn
                    # (off-topic should only trigger on direct responses, not after tool usage)
                    if content.startswith("[OFF_TOPIC]") and len(turn_tool_calls) == 0:
                        from utils.output import print_off_topic_skull
                        # Remove the marker and get the actual message
                        actual_content = content.replace("[OFF_TOPIC]", "").strip()
                        print_off_topic_skull("I'm specialized for Spring Boot projects!")
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": actual_content
                        })
                        return actual_content

                    # Remove any accidental [OFF_TOPIC] marker from tool result summaries
                    if content.startswith("[OFF_TOPIC]"):
                        content = content.replace("[OFF_TOPIC]", "").strip()

                    self.conversation_history.append({
                        "role": "assistant",
                        "content": content
                    })
                    return content
                else:
                    # LLM returned empty response - provide helpful guidance
                    finish_reason = response.get("finish_reason", "")
                    if finish_reason == "tool_calls":
                        # Tool call was expected but not provided
                        msg = "I'm not sure how to help with that. Can you provide more details about what you'd like me to analyze?"
                    else:
                        msg = "I couldn't generate a response. Try asking about:\n- Dependencies analysis\n- Code structure\n- Endpoints and APIs\n- Configuration\n- Finding issues"
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
                            # Try to get a meaningful summary from the result
                            summary = result.get("summary")
                            if not summary:
                                # Build a summary from available data
                                if "endpoints" in result:
                                    summary = f"Found {len(result['endpoints'])} endpoints in your project."
                                elif "dependencies" in result:
                                    summary = f"Found {len(result['dependencies'])} dependencies."
                                elif "classes" in result:
                                    summary = f"Found {len(result['classes'])} classes."
                                elif "results" in result:
                                    summary = f"Found {len(result['results'])} matches."
                                elif "tree" in result:
                                    summary = "Project structure loaded. Check the tree above for details."
                                else:
                                    summary = "Analysis data retrieved. Ask me specific questions about it."
                            self.conversation_history.append({
                                "role": "assistant",
                                "content": summary
                            })
                            return summary
                    return "I've gathered some data. What would you like to know about your project?"
                # No tool results - show rate limit message
                from utils.output import warn, print_error_ascii
                print_error_ascii("Rate Limit Exceeded")
                return warn(str(e))
            except ContextTooLargeError as e:
                # Context too large - clear history and retry with just this query
                from utils.output import warn
                self.clear_history()
                self.conversation_history.append({
                    "role": "user",
                    "content": user_input  # Original input without context
                })
                error_msg = warn("Context was too large. Starting fresh conversation. Please try your question again.")
                return error_msg
            except json.JSONDecodeError as e:
                # Handle malformed JSON from LLM
                from utils.output import print_error_ascii
                print_error_ascii("Processing Error")
                error_msg = "I had trouble processing that request. Please try rephrasing your question."
                self.conversation_history.append({
                    "role": "assistant",
                    "content": error_msg
                })
                return error_msg
            except Exception as e:
                from utils.output import print_error_ascii
                error_str = str(e)
                # Provide more helpful error messages for common issues
                if "API error" in error_str:
                    print_error_ascii("API Error")
                    error_msg = f"There was an issue with the AI service: {error_str}"
                elif "timeout" in error_str.lower():
                    print_error_ascii("Timeout Error")
                    error_msg = "The request timed out. Please try again."
                elif "connection" in error_str.lower():
                    print_error_ascii("Connection Error")
                    error_msg = "Network connection issue. Please check your internet connection."
                else:
                    print_error_ascii("Error")
                    error_msg = f"An error occurred: {error_str}"
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
    # Also reset context retriever to reload any updated context
    reset_retriever()


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
