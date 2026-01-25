"""Code summarizer for generating semantic descriptions of methods."""

import os
from typing import Dict, List, Any, Optional

from llm.client import get_api_key, GROQ_API_URL, AGENT_MODEL, FALLBACK_MODEL


# Batch size for summarization (methods per LLM call)
BATCH_SIZE = 5


def summarize_methods(methods: List[Dict[str, Any]],
                      show_progress: bool = True) -> List[Dict[str, Any]]:
    """Generate summaries for a list of methods using Groq LLM.

    Args:
        methods: List of method dicts from the parser with keys:
            - name: Method name
            - class_name: Class containing the method
            - file_path: Path to source file
            - start_line: Starting line number
            - end_line: Ending line number
            - annotations: List of annotations
            - parameters: List of parameter dicts
            - return_type: Return type
            - calls: Methods called internally
        show_progress: Whether to print progress updates

    Returns:
        List of method dicts with added 'summary' field
    """
    if not methods:
        return []

    # Read method bodies from files
    methods_with_code = _extract_method_bodies(methods)

    # Batch summarize
    summarized = []
    total_batches = (len(methods_with_code) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(methods_with_code), BATCH_SIZE):
        batch = methods_with_code[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        if show_progress:
            print(f"  Summarizing methods... ({batch_num}/{total_batches})")

        # Get summaries for batch
        summaries = _summarize_batch(batch)

        # Merge summaries into method dicts
        for j, method in enumerate(batch):
            method_with_summary = method.copy()
            method_with_summary['summary'] = summaries[j] if j < len(summaries) else _generate_fallback_summary(method)
            summarized.append(method_with_summary)

    return summarized


def _extract_method_bodies(methods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract actual code bodies for methods.

    Args:
        methods: List of method dicts

    Returns:
        Methods with 'code' field added containing the method body
    """
    # Group methods by file for efficient reading
    by_file: Dict[str, List[Dict]] = {}
    for method in methods:
        file_path = method.get('file_path', '')
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(method)

    # Read each file and extract method bodies
    result = []
    for file_path, file_methods in by_file.items():
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for method in file_methods:
                start = method.get('start_line', 1) - 1  # Convert to 0-indexed
                end = method.get('end_line', start + 1)

                # Extract method body (limit to ~50 lines to avoid huge methods)
                max_lines = 50
                if end - start > max_lines:
                    end = start + max_lines

                code = ''.join(lines[start:end])

                method_with_code = method.copy()
                method_with_code['code'] = code
                result.append(method_with_code)
        except Exception:
            # If file can't be read, use method without code
            for method in file_methods:
                method_with_code = method.copy()
                method_with_code['code'] = ''
                result.append(method_with_code)

    return result


def _summarize_batch(methods: List[Dict[str, Any]]) -> List[str]:
    """Summarize a batch of methods with a single LLM call.

    Args:
        methods: Batch of methods to summarize

    Returns:
        List of summary strings in same order as input
    """
    import requests
    import json

    api_key = get_api_key()
    if not api_key:
        return [_generate_fallback_summary(m) for m in methods]

    # Build prompt with all methods
    prompt = _build_batch_prompt(methods)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": AGENT_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 1024
    }

    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=60)

        # Handle rate limiting - try fallback model
        if response.status_code == 429:
            payload["model"] = FALLBACK_MODEL
            response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=60)

        if response.status_code >= 400:
            return [_generate_fallback_summary(m) for m in methods]

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Parse summaries from response
        return _parse_batch_response(content, len(methods))

    except Exception:
        return [_generate_fallback_summary(m) for m in methods]


def _build_batch_prompt(methods: List[Dict[str, Any]]) -> str:
    """Build a prompt to summarize multiple methods.

    Args:
        methods: List of methods to summarize

    Returns:
        Prompt string for LLM
    """
    prompt_parts = [
        "Summarize each Java method below in ONE sentence. Focus on WHAT it does (business logic), not HOW.",
        "Format: Return ONLY a numbered list matching the method numbers. No extra text.",
        "Example output:",
        "1. Calculates the total order price including tax and discounts.",
        "2. Validates user credentials and returns authentication token.",
        "",
        "Methods to summarize:",
        ""
    ]

    for i, method in enumerate(methods, 1):
        class_name = method.get('class_name', 'Unknown')
        method_name = method.get('name', 'unknown')
        annotations = ', '.join(method.get('annotations', [])) or 'none'
        code = method.get('code', 'No code available')

        # Truncate code if too long
        if len(code) > 1500:
            code = code[:1500] + "\n... (truncated)"

        prompt_parts.append(f"--- Method {i}: {class_name}.{method_name} ---")
        prompt_parts.append(f"Annotations: {annotations}")
        prompt_parts.append(f"Code:\n{code}")
        prompt_parts.append("")

    return '\n'.join(prompt_parts)


def _parse_batch_response(response: str, expected_count: int) -> List[str]:
    """Parse numbered summaries from LLM response.

    Args:
        response: LLM response text
        expected_count: Number of summaries expected

    Returns:
        List of summary strings
    """
    import re

    summaries = [''] * expected_count

    # Match patterns like "1. Summary text" or "1: Summary text"
    pattern = r'(\d+)[.:\)]\s*(.+?)(?=\n\d+[.:\)]|\n*$)'
    matches = re.findall(pattern, response, re.DOTALL)

    for num_str, summary in matches:
        try:
            num = int(num_str)
            if 1 <= num <= expected_count:
                # Clean up the summary
                summary = summary.strip()
                summary = re.sub(r'\s+', ' ', summary)  # Normalize whitespace
                summaries[num - 1] = summary
        except ValueError:
            continue

    # Fill in any missing with fallback
    for i in range(expected_count):
        if not summaries[i]:
            summaries[i] = "Method functionality could not be determined."

    return summaries


def _generate_fallback_summary(method: Dict[str, Any]) -> str:
    """Generate a basic summary from method metadata when LLM fails.

    Args:
        method: Method dict

    Returns:
        Basic summary string
    """
    class_name = method.get('class_name', 'Unknown')
    method_name = method.get('name', 'unknown')
    annotations = method.get('annotations', [])
    return_type = method.get('return_type', 'void')
    params = method.get('parameters', [])

    # Build description from metadata
    parts = []

    # Infer from annotations
    if '@GetMapping' in annotations or '@RequestMapping' in annotations:
        parts.append("HTTP endpoint that")
    elif '@PostMapping' in annotations:
        parts.append("HTTP POST endpoint that")
    elif '@Transactional' in annotations:
        parts.append("Transactional operation that")
    elif '@Scheduled' in annotations:
        parts.append("Scheduled task that")
    elif '@EventListener' in annotations:
        parts.append("Event handler that")

    # Infer from method name
    name_lower = method_name.lower()
    if name_lower.startswith('get') or name_lower.startswith('find') or name_lower.startswith('fetch'):
        parts.append(f"retrieves {_camel_to_words(method_name[3:] if name_lower.startswith('get') else method_name[4:])}")
    elif name_lower.startswith('set') or name_lower.startswith('update'):
        parts.append(f"updates {_camel_to_words(method_name[3:] if name_lower.startswith('set') else method_name[6:])}")
    elif name_lower.startswith('create') or name_lower.startswith('add'):
        parts.append(f"creates {_camel_to_words(method_name[6:] if name_lower.startswith('create') else method_name[3:])}")
    elif name_lower.startswith('delete') or name_lower.startswith('remove'):
        parts.append(f"removes {_camel_to_words(method_name[6:] if name_lower.startswith('delete') else method_name[6:])}")
    elif name_lower.startswith('is') or name_lower.startswith('has') or name_lower.startswith('can'):
        parts.append(f"checks if {_camel_to_words(method_name[2:] if name_lower.startswith('is') else method_name[3:])}")
    elif name_lower.startswith('calculate') or name_lower.startswith('compute'):
        parts.append(f"calculates {_camel_to_words(method_name[9:] if name_lower.startswith('calculate') else method_name[7:])}")
    elif name_lower.startswith('validate') or name_lower.startswith('verify'):
        parts.append(f"validates {_camel_to_words(method_name[8:] if name_lower.startswith('validate') else method_name[6:])}")
    elif name_lower.startswith('process'):
        parts.append(f"processes {_camel_to_words(method_name[7:])}")
    elif name_lower.startswith('handle'):
        parts.append(f"handles {_camel_to_words(method_name[6:])}")
    elif name_lower.startswith('send') or name_lower.startswith('notify'):
        parts.append(f"sends {_camel_to_words(method_name[4:] if name_lower.startswith('send') else method_name[6:])}")
    else:
        parts.append(f"{_camel_to_words(method_name)}")

    # Add return type info
    if return_type and return_type not in ('void', 'None'):
        if 'List' in return_type or 'Collection' in return_type:
            parts.append(f"and returns a list")
        elif 'Optional' in return_type:
            parts.append(f"and returns optional result")
        elif return_type == 'boolean':
            parts.append(f"and returns boolean result")

    summary = ' '.join(parts)
    if not summary.endswith('.'):
        summary += '.'

    return summary.capitalize() if summary else f"Method {method_name} in {class_name}."


def _camel_to_words(camel_str: str) -> str:
    """Convert CamelCase to space-separated words.

    Args:
        camel_str: CamelCase string

    Returns:
        Space-separated lowercase string
    """
    import re
    if not camel_str:
        return ""
    # Insert space before capitals and split
    words = re.sub(r'([A-Z])', r' \1', camel_str).strip().lower()
    return words
