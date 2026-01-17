import os
import json
import requests
from llm import prompts

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"  # Fast model for simple tasks
AGENT_MODEL = "llama-3.1-8b-instant"  # Primary model (500k tokens available)
FALLBACK_MODEL = "llama-3.3-70b-versatile"  # Fallback model


CREDENTIALS_FILE = os.path.expanduser("~/.nix/credentials")


def get_api_key():
    """Get Groq API key from environment or credentials file"""
    # First check environment variable
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        return api_key

    # Then check credentials file
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, 'r') as f:
                return f.read().strip()
        except:
            pass

    return None


def save_api_key(api_key):
    """Save API key to credentials file"""
    os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
    with open(CREDENTIALS_FILE, 'w') as f:
        f.write(api_key)
    os.chmod(CREDENTIALS_FILE, 0o600)  # Only owner can read/write


def call_groq(prompt):
    """
    Make API call to Groq
    Returns: Response text from LLM
    """
    api_key = get_api_key()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 500
    }

    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        raise Exception("Request timed out. Please check your internet connection.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")
    except KeyError:
        raise Exception("Unexpected API response format.")


def check_springboot(build_file_content, build_type):
    """
    Ask LLM if project is Spring Boot
    Returns: (is_springboot: bool, version: str or None)
    """
    prompt = prompts.get_springboot_detection_prompt(build_file_content, build_type)

    try:
        response = call_groq(prompt)
        return parse_springboot_response(response)
    except Exception as e:
        raise Exception(f"Failed to check Spring Boot: {str(e)}")


def parse_springboot_response(response):
    """
    Parse LLM response for Spring Boot detection
    Returns: (is_springboot: bool, version: str or None)
    """
    response_lower = response.lower()

    # Check if it's Spring Boot
    is_springboot = "yes" in response_lower and "spring boot" in response_lower

    if not is_springboot:
        return False, None

    # Try to extract version
    # Look for patterns like "3.2.0", "2.7.5", etc.
    import re
    version_pattern = r'\b\d+\.\d+\.\d+\b'
    matches = re.findall(version_pattern, response)

    version = matches[0] if matches else "Unknown"

    return True, version


class RateLimitExhaustedError(Exception):
    """Raised when Groq API daily quota is exhausted for all models"""
    pass


def call_groq_with_tools(messages, tools=None, retry_count=0, use_fallback=False):
    """
    Make API call to Groq with function calling support.

    Args:
        messages: List of message dicts with role and content
        tools: List of tool definitions (OpenAI function calling format)
        retry_count: Internal retry counter
        use_fallback: Whether to use fallback model

    Returns:
        dict with:
            - content: Text response (if no tool call)
            - tool_calls: List of tool calls (if LLM wants to use tools)
            - finish_reason: Why the response ended
    """
    import time

    api_key = get_api_key()
    current_model = FALLBACK_MODEL if use_fallback else AGENT_MODEL

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": current_model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024
    }

    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=60)

        # Handle rate limiting (silently retry, then fail gracefully)
        if response.status_code == 429:
            # Try quick retry first (2 retries max, shorter wait)
            if retry_count < 2:
                wait_time = 0.5 * (retry_count + 1)  # 0.5s, 1s
                time.sleep(wait_time)
                return call_groq_with_tools(messages, tools, retry_count + 1, use_fallback)

            # If primary model exhausted, try fallback model
            if not use_fallback:
                return call_groq_with_tools(messages, tools, retry_count=0, use_fallback=True)

            # Both models exhausted
            raise RateLimitExhaustedError(
                "Groq API usage limit reached. Your daily token quota is exhausted.\n"
                "Wait for your quota to reset or check usage at https://console.groq.com"
            )

        # Check for other errors and show details
        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except:
                error_msg = response.text
            raise Exception(f"API error ({response.status_code}): {error_msg}")

        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]

        result = {
            "content": message.get("content"),
            "tool_calls": None,
            "finish_reason": choice.get("finish_reason")
        }

        if message.get("tool_calls"):
            result["tool_calls"] = []
            for tc in message["tool_calls"]:
                tool_call = {
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": json.loads(tc["function"]["arguments"])
                }
                result["tool_calls"].append(tool_call)

        return result

    except RateLimitExhaustedError:
        raise  # Re-raise our custom error
    except requests.exceptions.Timeout:
        raise Exception("Request timed out. Please check your internet connection.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse tool arguments: {str(e)}")
    except KeyError as e:
        raise Exception(f"Unexpected API response format: {str(e)}")