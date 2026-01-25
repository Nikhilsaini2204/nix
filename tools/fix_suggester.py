"""Fix suggester tool for providing detailed fix suggestions for compile errors."""

import os
import re
from typing import Dict, List, Any, Optional, Tuple

from core.tools_registry import register_tool, create_tool_definition
from utils.output import (
    print_tool_start, print_tool_result, is_quiet,
    bold, error, warn, success, muted, highlight, Colors
)


# Error patterns with detection regex, quick fix hint, and detailed fix generator
ERROR_PATTERNS = {
    "missing_return": {
        "patterns": [
            r"missing return statement",
            r"method must return a value",
            r"not all code paths return a value"
        ],
        "quick_fix": "Add a return statement matching the method's return type",
        "fix_generator": "generate_return_fix"
    },
    "cannot_find_symbol": {
        "patterns": [
            r"cannot find symbol",
            r"symbol:\s*(class|variable|method)\s+(\w+)"
        ],
        "quick_fix": "Check import statements or verify the class/method exists",
        "fix_generator": "generate_symbol_fix"
    },
    "incompatible_types": {
        "patterns": [
            r"incompatible types",
            r"required:\s*(\w+)",
            r"found:\s*(\w+)"
        ],
        "quick_fix": "Cast the value or change the variable type",
        "fix_generator": "generate_type_fix"
    },
    "semicolon_expected": {
        "patterns": [
            r"['\"]?;['\"]?\s*expected",
            r"expected\s*['\"]?;['\"]?",
            r"missing semicolon",
            r"';' expected"
        ],
        "quick_fix": "Add missing semicolon at the end of the statement",
        "fix_generator": "generate_semicolon_fix"
    },
    "class_not_found": {
        "patterns": [
            r"cannot find symbol.*class\s+(\w+)",
            r"class\s+(\w+)\s+not found"
        ],
        "quick_fix": "Add import or verify the class exists in dependencies",
        "fix_generator": "generate_import_fix"
    },
    "unclosed_string": {
        "patterns": [
            r"unclosed string literal",
            r"illegal line end in string literal"
        ],
        "quick_fix": "Close the string with a matching quote",
        "fix_generator": "generate_string_fix"
    },
    "unchecked_exception": {
        "patterns": [
            r"unreported exception",
            r"unreported exception\s+(\w+)",
            r"must be caught or declared to be thrown",
            r"unhandled exception"
        ],
        "quick_fix": "Add try-catch block or add 'throws' to method signature",
        "fix_generator": "generate_exception_fix"
    },
    "duplicate_class": {
        "patterns": [
            r"duplicate class",
            r"class (\w+) is already defined"
        ],
        "quick_fix": "Remove duplicate class definition or rename one",
        "fix_generator": "generate_duplicate_fix"
    },
    "method_not_found": {
        "patterns": [
            r"cannot find symbol.*method\s+(\w+)",
            r"method\s+(\w+)\s+not found"
        ],
        "quick_fix": "Check method name spelling and parameter types",
        "fix_generator": "generate_method_fix"
    },
    "variable_not_initialized": {
        "patterns": [
            r"variable\s+(\w+)\s+might not have been initialized",
            r"(\w+)\s+may not have been initialized"
        ],
        "quick_fix": "Initialize the variable before use",
        "fix_generator": "generate_init_fix"
    },
    "bracket_expected": {
        "patterns": [
            r"'\{' expected",
            r"'\}' expected",
            r"'\(' expected",
            r"'\)' expected",
            r"'\[' expected",
            r"'\]' expected"
        ],
        "quick_fix": "Add the missing bracket/parenthesis",
        "fix_generator": "generate_bracket_fix"
    },
    "illegal_start": {
        "patterns": [
            r"illegal start of (expression|type|statement)",
        ],
        "quick_fix": "Check for syntax errors like missing operators or keywords",
        "fix_generator": "generate_syntax_fix"
    },
    "modifier_not_allowed": {
        "patterns": [
            r"modifier\s+(\w+)\s+not allowed",
            r"illegal modifier"
        ],
        "quick_fix": "Remove the invalid modifier from the declaration",
        "fix_generator": "generate_modifier_fix"
    },
    "void_not_allowed": {
        "patterns": [
            r"'void' type not allowed here",
            r"void cannot be dereferenced"
        ],
        "quick_fix": "Void methods don't return values - change return type or remove return",
        "fix_generator": "generate_void_fix"
    }
}


def suggest_fix(file_path: str = None, line: int = None,
                error_type: str = None, error_message: str = None) -> Dict[str, Any]:
    """
    Provide detailed fix suggestions for a compile error.

    Args:
        file_path: Path to the file with the error
        line: Line number of the error (1-indexed)
        error_type: Type of error (e.g., "missing return statement")
        error_message: Full error message from compiler

    Returns:
        dict with:
        - code_context: The problematic code with context
        - problem_explanation: What's wrong and why
        - fix_suggestion: How to fix it
        - code_example: Example of the fixed code
    """
    if not is_quiet():
        print_tool_start("suggest_fix")

    # Need at least file/line or error message or error type
    if not file_path and not error_message and not error_type:
        return {
            "error": "Please provide a file path/line, error type, or error message",
            "suggestion": "Try: 'suggest fix for UserService.java line 14' or describe the error",
            "summary": "Need more information to provide a fix suggestion"
        }

    # Try to extract file:line from error_message if not provided directly
    if not file_path and error_message:
        file_line_match = re.search(r'([\w/\\]+\.java)[:\s]+(?:line\s+)?(\d+)', error_message, re.IGNORECASE)
        if file_line_match:
            file_path = file_line_match.group(1)
            if not line:
                line = int(file_line_match.group(2))

    result = {
        "file": file_path,
        "line": line,
        "error_type": None,
        "problem_explanation": None,
        "code_context": None,
        "fix_suggestion": None,
        "code_example": None
    }

    # Detect error type from message or explicit type
    detected_type, pattern_info = detect_error_type(error_type or error_message or "")
    result["error_type"] = detected_type

    # Read the source file for context
    if file_path:
        full_path = find_java_file(file_path) if not os.path.isabs(file_path) else file_path

        if full_path and os.path.exists(full_path):
            result["file"] = full_path
            code_lines = read_file_lines(full_path)

            if line and code_lines:
                # Get code context around the error
                result["code_context"] = get_code_context(code_lines, line, context=5)

                # Generate specific fix based on error type
                if detected_type and pattern_info:
                    fix_result = generate_specific_fix(
                        detected_type,
                        pattern_info,
                        code_lines,
                        line,
                        error_message or error_type
                    )
                    result.update(fix_result)
                else:
                    # Generic fix suggestion
                    result["problem_explanation"] = "Unable to determine specific error type"
                    result["fix_suggestion"] = "Review the code at this location and check for syntax or type errors"
        else:
            result["error"] = f"File not found: {file_path}"

    # If only error message or error_type provided (no file), give general guidance
    if not file_path and (error_message or error_type):
        if detected_type and pattern_info:
            result["problem_explanation"] = get_problem_explanation(detected_type)
            result["fix_suggestion"] = pattern_info.get("quick_fix", "Review and fix the error")

    # Add summary for LLM consumption
    if result.get("fix_suggestion"):
        error_desc = detected_type.replace("_", " ") if detected_type else "error"
        result["summary"] = f"Fix suggestion for {error_desc}: {result['fix_suggestion']}"
    elif result.get("error"):
        result["summary"] = result["error"]
    else:
        result["summary"] = "Unable to provide specific fix suggestion. Please provide more details about the error."

    # Print output
    if not is_quiet():
        print_fix_result(result)

    return result


def detect_error_type(error_text: str) -> Tuple[Optional[str], Optional[Dict]]:
    """Detect error type from error message or type string.

    Args:
        error_text: Error message or type hint

    Returns:
        (error_type_key, pattern_info) or (None, None)
    """
    error_lower = error_text.lower()

    for error_key, pattern_info in ERROR_PATTERNS.items():
        for pattern in pattern_info["patterns"]:
            if re.search(pattern, error_lower, re.IGNORECASE):
                return error_key, pattern_info

    return None, None


def get_problem_explanation(error_type: str) -> str:
    """Get a human-readable explanation of the error type.

    Args:
        error_type: Error type key

    Returns:
        Explanation string
    """
    explanations = {
        "missing_return": "This method is declared to return a value, but doesn't have a return statement (or not all code paths return a value).",
        "cannot_find_symbol": "The compiler can't find a class, variable, or method. This usually means it's not imported, misspelled, or doesn't exist.",
        "incompatible_types": "You're trying to assign or use a value of the wrong type. Java is strongly typed and requires type compatibility.",
        "semicolon_expected": "Java statements must end with a semicolon. There's a missing semicolon before this line.",
        "class_not_found": "The compiler can't find this class. Either the import is missing or the class doesn't exist.",
        "unclosed_string": "A string literal is not properly closed with a matching quote.",
        "unchecked_exception": "This code throws a checked exception that must be caught or declared in the method signature.",
        "duplicate_class": "A class with this name is already defined in this scope or package.",
        "method_not_found": "The method you're trying to call doesn't exist on this object or has different parameters.",
        "variable_not_initialized": "A variable is being used before it has been assigned a value.",
        "bracket_expected": "There's a missing or mismatched bracket, parenthesis, or brace.",
        "illegal_start": "The compiler encountered something unexpected that can't begin an expression or statement.",
        "modifier_not_allowed": "The modifier (like public, static, final) is not valid in this context.",
        "void_not_allowed": "Void methods don't return values, so you can't use the result of a void method call."
    }
    return explanations.get(error_type, "An error occurred in the code.")


def generate_specific_fix(error_type: str, pattern_info: Dict,
                         code_lines: List[str], line: int,
                         error_message: str) -> Dict[str, Any]:
    """Generate specific fix based on error type and code context.

    Args:
        error_type: Detected error type
        pattern_info: Pattern info dict
        code_lines: List of code lines
        line: Error line number
        error_message: Full error message

    Returns:
        Dict with problem_explanation, fix_suggestion, code_example
    """
    result = {
        "problem_explanation": get_problem_explanation(error_type),
        "fix_suggestion": pattern_info.get("quick_fix"),
        "code_example": None
    }

    # Call specific fix generator if available
    generator_name = pattern_info.get("fix_generator")
    if generator_name:
        generator_func = globals().get(generator_name)
        if generator_func:
            try:
                specific_result = generator_func(code_lines, line, error_message)
                result.update(specific_result)
            except Exception:
                pass

    return result


def generate_return_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for missing return statement.

    Args:
        code_lines: Source file lines
        line: Error line
        error_message: Error message

    Returns:
        Fix suggestion dict
    """
    result = {}

    # Find the method containing this line
    method_info = find_enclosing_method(code_lines, line)

    if method_info:
        return_type = method_info.get("return_type", "Object")
        method_name = method_info.get("name", "method")

        # Generate example based on return type
        default_values = {
            "int": "0",
            "long": "0L",
            "double": "0.0",
            "float": "0.0f",
            "boolean": "false",
            "char": "'\\0'",
            "byte": "(byte) 0",
            "short": "(short) 0",
            "String": "\"\"",
            "List": "Collections.emptyList()",
            "Map": "Collections.emptyMap()",
            "Set": "Collections.emptySet()",
            "Optional": "Optional.empty()"
        }

        # Check for common types
        default_value = "null"
        for type_name, value in default_values.items():
            if type_name.lower() in return_type.lower():
                default_value = value
                break

        result["fix_suggestion"] = (
            f"Add a return statement at the end of the '{method_name}' method.\n"
            f"The method must return a value of type '{return_type}'."
        )

        # Generate code example
        error_line_content = code_lines[line - 1].rstrip() if line <= len(code_lines) else ""
        indent = get_indent(error_line_content) or "        "

        result["code_example"] = {
            "before": f"    // Method ends without return:\n    {error_line_content}",
            "after": f"    // Add return statement before closing brace:\n{indent}return {default_value};\n    }}"
        }

    return result


def generate_symbol_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for 'cannot find symbol' error.

    Args:
        code_lines: Source file lines
        line: Error line
        error_message: Error message

    Returns:
        Fix suggestion dict
    """
    result = {}

    # Extract symbol name from error message
    symbol_match = re.search(r'symbol:\s*(class|variable|method)\s+(\w+)', error_message, re.IGNORECASE)
    if not symbol_match:
        symbol_match = re.search(r'cannot find symbol.*?(\w+)', error_message, re.IGNORECASE)

    if symbol_match:
        symbol_type = symbol_match.group(1) if symbol_match.lastindex >= 2 else "symbol"
        symbol_name = symbol_match.group(2) if symbol_match.lastindex >= 2 else symbol_match.group(1)

        if symbol_type == "class":
            result["fix_suggestion"] = (
                f"The class '{symbol_name}' is not imported or doesn't exist.\n\n"
                f"Possible fixes:\n"
                f"1. Add import: import com.example.{symbol_name};\n"
                f"2. Check if the class exists in your project\n"
                f"3. Add required dependency to pom.xml/build.gradle"
            )

            # Suggest common imports
            common_imports = suggest_common_import(symbol_name)
            if common_imports:
                result["fix_suggestion"] += f"\n\nCommon imports for '{symbol_name}':\n"
                for imp in common_imports:
                    result["fix_suggestion"] += f"  import {imp};\n"

        elif symbol_type == "variable":
            result["fix_suggestion"] = (
                f"The variable '{symbol_name}' is not declared.\n\n"
                f"Possible fixes:\n"
                f"1. Declare the variable before use: Type {symbol_name} = value;\n"
                f"2. Check for typos in the variable name\n"
                f"3. Check if it's defined in the correct scope"
            )

        elif symbol_type == "method":
            result["fix_suggestion"] = (
                f"The method '{symbol_name}' was not found.\n\n"
                f"Possible fixes:\n"
                f"1. Check the method name spelling\n"
                f"2. Verify the object has this method (check its class)\n"
                f"3. Check if you need to import a class for static methods"
            )

    return result


def generate_type_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for incompatible types error.

    Args:
        code_lines: Source file lines
        line: Error line
        error_message: Error message

    Returns:
        Fix suggestion dict
    """
    result = {}

    # Extract types from error
    required_match = re.search(r'required:\s*(\S+)', error_message)
    found_match = re.search(r'found:\s*(\S+)', error_message)

    required_type = required_match.group(1) if required_match else "expected type"
    found_type = found_match.group(1) if found_match else "actual type"

    error_line = code_lines[line - 1] if line <= len(code_lines) else ""

    result["fix_suggestion"] = (
        f"Type mismatch: expected '{required_type}' but found '{found_type}'.\n\n"
        f"Possible fixes:\n"
        f"1. Cast the value: ({required_type}) value\n"
        f"2. Change the variable type to '{found_type}'\n"
        f"3. Convert the value using a method (e.g., toString(), parseInt(), etc.)"
    )

    # Suggest specific conversions
    conversions = get_type_conversion(found_type, required_type)
    if conversions:
        result["fix_suggestion"] += f"\n\nConversion example:\n{conversions}"

    return result


def generate_semicolon_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for missing semicolon error."""
    result = {}

    # Check the previous line for missing semicolon
    if line > 1:
        prev_line = code_lines[line - 2].rstrip()
        if prev_line and not prev_line.endswith((';', '{', '}', ':')):
            result["fix_suggestion"] = (
                f"Add a semicolon at the end of the previous line.\n\n"
                f"Before: {prev_line}\n"
                f"After:  {prev_line};"
            )
            result["code_example"] = {
                "before": prev_line,
                "after": prev_line + ";"
            }

    return result


def generate_import_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for missing import/class not found."""
    result = {}

    # Extract class name
    class_match = re.search(r'class\s+(\w+)', error_message, re.IGNORECASE)
    if not class_match:
        class_match = re.search(r'symbol.*?(\w+)', error_message)

    if class_match:
        class_name = class_match.group(1)

        imports = suggest_common_import(class_name)

        if imports:
            result["fix_suggestion"] = f"Add one of these imports for '{class_name}':\n"
            for imp in imports:
                result["fix_suggestion"] += f"\nimport {imp};"
        else:
            result["fix_suggestion"] = (
                f"Add the import for '{class_name}':\n\n"
                f"import your.package.{class_name};\n\n"
                f"Or check if the class exists in your dependencies."
            )

    return result


def generate_exception_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for unchecked exception error."""
    result = {}

    # Extract exception name
    exc_match = re.search(r'exception\s+(\w+)', error_message, re.IGNORECASE)
    exception_name = exc_match.group(1) if exc_match else "Exception"

    error_line = code_lines[line - 1] if line <= len(code_lines) else ""
    indent = get_indent(error_line)

    result["fix_suggestion"] = (
        f"Handle the {exception_name} with one of these options:\n\n"
        f"Option 1 - Add try-catch:\n"
        f"  try {{\n"
        f"      {error_line.strip()}\n"
        f"  }} catch ({exception_name} e) {{\n"
        f"      // handle exception\n"
        f"  }}\n\n"
        f"Option 2 - Add throws to method signature:\n"
        f"  public void methodName() throws {exception_name} {{"
    )

    return result


def generate_string_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for unclosed string literal."""
    result = {}

    error_line = code_lines[line - 1] if line <= len(code_lines) else ""

    result["fix_suggestion"] = (
        "Close the string literal with a matching quote.\n\n"
        "If your string spans multiple lines, use:\n"
        "1. String concatenation: \"line1\" + \"line2\"\n"
        "2. Text blocks (Java 15+): \"\"\"\n   multi-line string\n   \"\"\""
    )

    return result


def generate_duplicate_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for duplicate class definition."""
    return {
        "fix_suggestion": (
            "A class with this name already exists.\n\n"
            "Options:\n"
            "1. Rename one of the classes\n"
            "2. Move one class to a different package\n"
            "3. Delete the duplicate class definition"
        )
    }


def generate_method_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for method not found error."""
    result = {}

    method_match = re.search(r'method\s+(\w+)', error_message, re.IGNORECASE)
    method_name = method_match.group(1) if method_match else "method"

    result["fix_suggestion"] = (
        f"The method '{method_name}' was not found.\n\n"
        f"Possible fixes:\n"
        f"1. Check the method name spelling\n"
        f"2. Check the object type - does it have this method?\n"
        f"3. Check method parameter types match\n"
        f"4. Verify the method visibility (public/private)\n"
        f"5. Check if an import is needed"
    )

    return result


def generate_init_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for variable not initialized error."""
    result = {}

    var_match = re.search(r'variable\s+(\w+)', error_message, re.IGNORECASE)
    if not var_match:
        var_match = re.search(r'(\w+)\s+may not', error_message)

    var_name = var_match.group(1) if var_match else "variable"

    result["fix_suggestion"] = (
        f"Initialize '{var_name}' before using it.\n\n"
        f"Example:\n"
        f"  String {var_name} = null;  // or an actual value\n"
        f"  // ... later ...\n"
        f"  if ({var_name} != null) {{ use it }}"
    )

    return result


def generate_bracket_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for missing bracket error."""
    result = {}

    bracket_match = re.search(r"'(.)'", error_message)
    bracket = bracket_match.group(1) if bracket_match else "bracket"

    result["fix_suggestion"] = (
        f"Add the missing '{bracket}'.\n\n"
        f"Tips:\n"
        f"1. Check that all brackets/braces are balanced\n"
        f"2. Use IDE bracket matching to find mismatches\n"
        f"3. Check the lines before this error"
    )

    return result


def generate_syntax_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for illegal start of expression/type."""
    return {
        "fix_suggestion": (
            "The compiler found something unexpected.\n\n"
            "Common causes:\n"
            "1. Missing semicolon on the previous line\n"
            "2. Missing operator (=, +, ., etc.)\n"
            "3. Typo in keyword (pubilc instead of public)\n"
            "4. Missing closing brace/bracket above\n"
            "5. Code outside a method body"
        )
    }


def generate_modifier_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for invalid modifier error."""
    result = {}

    mod_match = re.search(r'modifier\s+(\w+)', error_message, re.IGNORECASE)
    modifier = mod_match.group(1) if mod_match else "modifier"

    result["fix_suggestion"] = (
        f"The modifier '{modifier}' is not allowed here.\n\n"
        f"Rules:\n"
        f"1. Local variables can't be public/private/protected\n"
        f"2. Interface methods are implicitly public abstract\n"
        f"3. static is not allowed on local classes\n"
        f"4. Remove the modifier or move the code to appropriate scope"
    )

    return result


def generate_void_fix(code_lines: List[str], line: int, error_message: str) -> Dict[str, Any]:
    """Generate fix for void type not allowed error."""
    return {
        "fix_suggestion": (
            "Void methods don't return a value, so you can't use the result.\n\n"
            "Possible fixes:\n"
            "1. Remove the assignment: just call the method without storing result\n"
            "2. Change the method to return a value instead of void\n"
            "3. Use a different method that returns the value you need"
        )
    }


# Helper functions

def find_java_file(file_name: str) -> Optional[str]:
    """Find a Java file in the project by name."""
    project_root = os.getcwd()

    # If already looks like a path
    if os.path.sep in file_name or file_name.startswith("."):
        if os.path.exists(file_name):
            return file_name
        full_path = os.path.join(project_root, file_name)
        if os.path.exists(full_path):
            return full_path

    # Search in src directories
    src_dirs = ["src/main/java", "src/test/java", "src"]

    for src_dir in src_dirs:
        src_path = os.path.join(project_root, src_dir)
        if os.path.exists(src_path):
            for root, _, files in os.walk(src_path):
                if file_name in files:
                    return os.path.join(root, file_name)

    return None


def read_file_lines(file_path: str) -> List[str]:
    """Read file and return list of lines."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.readlines()
    except Exception:
        return []


def get_code_context(lines: List[str], line: int, context: int = 5) -> str:
    """Get code context around a line."""
    start = max(0, line - context - 1)
    end = min(len(lines), line + context)

    result_lines = []
    for i in range(start, end):
        line_num = i + 1
        prefix = ">>> " if line_num == line else "    "
        content = lines[i].rstrip()
        result_lines.append(f"{prefix}{line_num:4d}: {content}")

    return '\n'.join(result_lines)


def find_enclosing_method(lines: List[str], target_line: int) -> Optional[Dict]:
    """Find the method that contains the target line."""
    # Simple regex for method declarations
    method_pattern = r'(public|private|protected)?\s*(static)?\s*(\w+(?:<[^>]+>)?)\s+(\w+)\s*\('

    current_method = None
    brace_count = 0

    for i, line in enumerate(lines):
        line_num = i + 1

        # Check for method declaration
        match = re.search(method_pattern, line)
        if match:
            return_type = match.group(3)
            method_name = match.group(4)

            # Skip constructors (return type same as class name in class context)
            if return_type not in ['if', 'while', 'for', 'switch', 'catch']:
                current_method = {
                    "return_type": return_type,
                    "name": method_name,
                    "start_line": line_num
                }
                brace_count = line.count('{') - line.count('}')
        else:
            brace_count += line.count('{') - line.count('}')

        # If we're past the target line and have a method, return it
        if line_num == target_line and current_method:
            return current_method

        # Reset if we've closed the method
        if brace_count <= 0 and current_method:
            if line_num > target_line:
                return current_method
            current_method = None

    return current_method


def get_indent(line: str) -> str:
    """Get the indentation of a line."""
    match = re.match(r'^(\s*)', line)
    return match.group(1) if match else ""


def suggest_common_import(class_name: str) -> List[str]:
    """Suggest common imports for a class name."""
    common_imports = {
        "List": ["java.util.List"],
        "ArrayList": ["java.util.ArrayList"],
        "Map": ["java.util.Map"],
        "HashMap": ["java.util.HashMap"],
        "Set": ["java.util.Set"],
        "HashSet": ["java.util.HashSet"],
        "Optional": ["java.util.Optional"],
        "Stream": ["java.util.stream.Stream"],
        "Collectors": ["java.util.stream.Collectors"],
        "Arrays": ["java.util.Arrays"],
        "Collections": ["java.util.Collections"],
        "Date": ["java.util.Date", "java.sql.Date"],
        "LocalDate": ["java.time.LocalDate"],
        "LocalDateTime": ["java.time.LocalDateTime"],
        "Instant": ["java.time.Instant"],
        "Duration": ["java.time.Duration"],
        "IOException": ["java.io.IOException"],
        "File": ["java.io.File"],
        "Path": ["java.nio.file.Path"],
        "Paths": ["java.nio.file.Paths"],
        "Files": ["java.nio.file.Files"],
        "Pattern": ["java.util.regex.Pattern"],
        "Matcher": ["java.util.regex.Matcher"],
        "BigDecimal": ["java.math.BigDecimal"],
        "BigInteger": ["java.math.BigInteger"],
        # Spring
        "Autowired": ["org.springframework.beans.factory.annotation.Autowired"],
        "Service": ["org.springframework.stereotype.Service"],
        "Repository": ["org.springframework.stereotype.Repository"],
        "Component": ["org.springframework.stereotype.Component"],
        "Controller": ["org.springframework.stereotype.Controller"],
        "RestController": ["org.springframework.web.bind.annotation.RestController"],
        "RequestMapping": ["org.springframework.web.bind.annotation.RequestMapping"],
        "GetMapping": ["org.springframework.web.bind.annotation.GetMapping"],
        "PostMapping": ["org.springframework.web.bind.annotation.PostMapping"],
        "RequestBody": ["org.springframework.web.bind.annotation.RequestBody"],
        "ResponseBody": ["org.springframework.web.bind.annotation.ResponseBody"],
        "PathVariable": ["org.springframework.web.bind.annotation.PathVariable"],
        "RequestParam": ["org.springframework.web.bind.annotation.RequestParam"],
        # JPA
        "Entity": ["jakarta.persistence.Entity", "javax.persistence.Entity"],
        "Table": ["jakarta.persistence.Table", "javax.persistence.Table"],
        "Id": ["jakarta.persistence.Id", "javax.persistence.Id"],
        "Column": ["jakarta.persistence.Column", "javax.persistence.Column"],
        "GeneratedValue": ["jakarta.persistence.GeneratedValue", "javax.persistence.GeneratedValue"],
        # Testing
        "Test": ["org.junit.jupiter.api.Test", "org.junit.Test"],
        "BeforeEach": ["org.junit.jupiter.api.BeforeEach"],
        "AfterEach": ["org.junit.jupiter.api.AfterEach"],
        "Assertions": ["org.junit.jupiter.api.Assertions"],
        "Mock": ["org.mockito.Mock"],
        "InjectMocks": ["org.mockito.InjectMocks"],
        "Mockito": ["org.mockito.Mockito"],
        # Lombok
        "Data": ["lombok.Data"],
        "Getter": ["lombok.Getter"],
        "Setter": ["lombok.Setter"],
        "Builder": ["lombok.Builder"],
        "NoArgsConstructor": ["lombok.NoArgsConstructor"],
        "AllArgsConstructor": ["lombok.AllArgsConstructor"],
    }

    return common_imports.get(class_name, [])


def get_type_conversion(from_type: str, to_type: str) -> Optional[str]:
    """Get conversion example between types."""
    conversions = {
        ("int", "String"): "String.valueOf(intValue)  // or Integer.toString(intValue)",
        ("String", "int"): "Integer.parseInt(stringValue)",
        ("String", "Integer"): "Integer.valueOf(stringValue)",
        ("double", "String"): "String.valueOf(doubleValue)",
        ("String", "double"): "Double.parseDouble(stringValue)",
        ("long", "String"): "String.valueOf(longValue)",
        ("String", "long"): "Long.parseLong(stringValue)",
        ("boolean", "String"): "String.valueOf(boolValue)",
        ("String", "boolean"): "Boolean.parseBoolean(stringValue)",
        ("Object", "String"): "object.toString()  // or String.valueOf(object)",
        ("int", "long"): "(long) intValue  // automatic widening",
        ("long", "int"): "(int) longValue  // may lose precision",
        ("int", "double"): "(double) intValue  // automatic widening",
        ("double", "int"): "(int) doubleValue  // truncates decimal",
    }

    # Normalize types
    from_lower = from_type.lower().replace("integer", "int")
    to_lower = to_type.lower().replace("integer", "int")

    return conversions.get((from_lower, to_lower))


def print_fix_result(result: Dict[str, Any]):
    """Print formatted fix suggestion result."""
    if result.get("error"):
        print_tool_result(error(result["error"]))
        return

    print_tool_result(f"Analyzing error at {highlight(result.get('file', 'unknown'))}")

    error_type = result.get("error_type")
    if error_type:
        print(f"\n{error('Problem:')} {bold(error_type.replace('_', ' ').title())}")

    explanation = result.get("problem_explanation")
    if explanation:
        print(f"\n{muted(explanation)}")

    # Show code context
    code_context = result.get("code_context")
    if code_context:
        print(f"\n{bold('Your code:')}")
        for line in code_context.split('\n'):
            if line.startswith('>>> '):
                # Error line
                print(f"  {error(line)}")
            else:
                print(f"  {muted(line)}")

    # Show fix suggestion
    fix = result.get("fix_suggestion")
    if fix:
        print(f"\n{success('How to fix:')}")
        for line in fix.split('\n'):
            print(f"  {line}")

    # Show code example if available
    code_example = result.get("code_example")
    if code_example:
        print(f"\n{bold('Example fix:')}")
        if isinstance(code_example, dict):
            if code_example.get("before"):
                print(f"  {muted('Before:')} {error(code_example['before'])}")
            if code_example.get("after"):
                print(f"  {success('After:')}  {success(code_example['after'])}")
        else:
            print(f"  {code_example}")

    print()


def get_quick_suggestion(error_message: str) -> Optional[str]:
    """Get a quick one-liner suggestion for an error message.

    This is used by build_runner.py to show inline suggestions.

    Args:
        error_message: Compiler error message

    Returns:
        Quick suggestion string or None
    """
    error_type, pattern_info = detect_error_type(error_message)
    if pattern_info:
        return pattern_info.get("quick_fix")
    return None


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="suggest_fix",
    description=(
        "Provide detailed fix suggestions for compile errors. "
        "Use when user asks 'how do I fix this?', 'help me fix', 'what's wrong with my code'. "
        "Analyzes the error type and code context to give specific fix guidance with examples."
    ),
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the file with the error (e.g., 'UserService.java')"
        },
        "line": {
            "type": "integer",
            "description": "Line number of the error (1-indexed)"
        },
        "error_type": {
            "type": "string",
            "description": "Type of error (e.g., 'missing return statement', 'cannot find symbol')"
        },
        "error_message": {
            "type": "string",
            "description": "Full error message from the compiler"
        }
    }
)


def register():
    """Register this tool with the registry."""
    register_tool("suggest_fix", suggest_fix, TOOL_DEFINITION)
