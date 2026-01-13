import os
import requests
from llm import prompts

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"  # Fast and free Groq model


CREDENTIALS_FILE = os.path.expanduser("~/.niks/credentials")


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