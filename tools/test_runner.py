"""Test runner tool for Spring Boot projects."""

import os
import re
import subprocess
from typing import Dict, List, Any, Optional, Tuple

from core.tools_registry import register_tool, create_tool_definition
from utils.output import (
    print_tool_start, print_tool_result, is_quiet,
    bold, error, warn, success, muted, highlight
)


def run_tests(test_class: str = None, test_method: str = None) -> Dict[str, Any]:
    """
    Run tests using Maven or Gradle.

    Args:
        test_class: Optional specific test class to run
        test_method: Optional specific test method to run

    Returns:
        dict with test results, failures, and stack traces
    """
    if not is_quiet():
        print_tool_start("run_tests")

    build_file, build_type = find_build_tool()

    if not build_file:
        if not is_quiet():
            print_tool_result("No build file found")
        return {
            "success": False,
            "error": "No build file found. This doesn't appear to be a Maven or Gradle project.",
            "suggestion": "Make sure you're in a Maven or Gradle project directory"
        }

    try:
        if build_type == "maven":
            result = run_maven_tests(test_class, test_method)
        else:
            result = run_gradle_tests(test_class, test_method)

        if not is_quiet():
            if result['success']:
                print_tool_result(success(f"All {result.get('total', 0)} tests passed"))
            else:
                failed = result.get('failed', 0)
                total = result.get('total', 0)
                print_tool_result(error(f"{failed}/{total} tests failed"))

                # Print colored test failures
                failures = result.get('failures', [])
                for i, failure in enumerate(failures[:5], 1):
                    test_class_name = failure.get('class', 'Unknown')
                    test_method_name = failure.get('method', 'unknown')
                    failure_type = failure.get('type', 'failure')

                    print(f"\n{error(f'[{failure_type.upper()}]')} {bold(test_class_name)}.{warn(test_method_name)}")

                    # Print stack trace snippet if available
                    stack_trace = failure.get('stack_trace')
                    if stack_trace:
                        trace_lines = stack_trace.split('\n')[:8]  # First 8 lines
                        for line in trace_lines:
                            if 'at ' in line and '.java:' in line:
                                # Highlight file:line references
                                print(f"  {muted(line.strip())}")
                            elif 'Exception' in line or 'Error' in line or 'assert' in line.lower():
                                print(f"  {error(line.strip())}")
                            else:
                                print(f"  {muted(line.strip())}")

                if len(failures) > 5:
                    print(f"\n{muted(f'... and {len(failures) - 5} more failures')}")

        return result

    except Exception as e:
        if not is_quiet():
            print_tool_result(f"Error: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to run tests: {str(e)}",
            "build_tool": build_type
        }


def find_build_tool() -> Tuple[Optional[str], Optional[str]]:
    """Find build file in current directory."""
    project_root = os.getcwd()

    candidates = [
        ("pom.xml", "maven"),
        ("build.gradle", "gradle"),
        ("build.gradle.kts", "gradle"),
    ]

    for filename, build_type in candidates:
        path = os.path.join(project_root, filename)
        if os.path.exists(path):
            return path, build_type

    return None, None


def run_maven_tests(test_class: str = None, test_method: str = None) -> Dict[str, Any]:
    """Run Maven tests.

    Args:
        test_class: Optional specific test class to run
        test_method: Optional specific test method to run

    Returns:
        dict with test results
    """
    mvnw = "./mvnw" if os.path.exists("mvnw") else "mvn"

    command = [mvnw, "test"]

    if test_class:
        if test_method:
            command.extend(["-Dtest=" + test_class + "#" + test_method])
        else:
            command.extend(["-Dtest=" + test_class])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout for tests
        )

        output = result.stdout + result.stderr
        success = result.returncode == 0

        # Parse test results
        test_results = parse_maven_test_results(output)

        return {
            "success": success,
            "build_tool": "maven",
            "command": " ".join(command),
            **test_results,
            "output_summary": summarize_test_output(output, success)
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "build_tool": "maven",
            "error": "Tests timed out after 10 minutes",
            "failures": []
        }
    except FileNotFoundError:
        return {
            "success": False,
            "build_tool": "maven",
            "error": "Maven not found. Make sure mvn or mvnw is available.",
            "failures": []
        }


def run_gradle_tests(test_class: str = None, test_method: str = None) -> Dict[str, Any]:
    """Run Gradle tests.

    Args:
        test_class: Optional specific test class to run
        test_method: Optional specific test method to run

    Returns:
        dict with test results
    """
    gradlew = "./gradlew" if os.path.exists("gradlew") else "gradle"

    command = [gradlew, "test"]

    if test_class:
        if test_method:
            command.append(f"--tests={test_class}.{test_method}")
        else:
            command.append(f"--tests={test_class}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=600
        )

        output = result.stdout + result.stderr
        success = result.returncode == 0

        # Parse test results
        test_results = parse_gradle_test_results(output)

        return {
            "success": success,
            "build_tool": "gradle",
            "command": " ".join(command),
            **test_results,
            "output_summary": summarize_test_output(output, success)
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "build_tool": "gradle",
            "error": "Tests timed out after 10 minutes",
            "failures": []
        }
    except FileNotFoundError:
        return {
            "success": False,
            "build_tool": "gradle",
            "error": "Gradle not found. Make sure gradle or gradlew is available.",
            "failures": []
        }


def parse_maven_test_results(output: str) -> Dict[str, Any]:
    """Parse Maven Surefire test output.

    Args:
        output: Maven test output

    Returns:
        dict with total, passed, failed, skipped, and failure details
    """
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "failures": []
    }

    # Parse summary line: Tests run: X, Failures: Y, Errors: Z, Skipped: W
    summary_pattern = r'Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)'
    summary_match = re.search(summary_pattern, output)

    if summary_match:
        total = int(summary_match.group(1))
        failures = int(summary_match.group(2))
        errors = int(summary_match.group(3))
        skipped = int(summary_match.group(4))

        results["total"] = total
        results["failed"] = failures + errors
        results["skipped"] = skipped
        results["passed"] = total - failures - errors - skipped

    # Parse individual test failures
    # Pattern: TestClass.testMethod  Time elapsed: Xs  <<< FAILURE!
    failure_pattern = r'(\w+)\.(\w+)\s+Time elapsed:.*<<<\s*(FAILURE|ERROR)!'
    for match in re.finditer(failure_pattern, output):
        test_class = match.group(1)
        test_method = match.group(2)
        failure_type = match.group(3).lower()

        # Try to get the stack trace
        stack_trace = extract_stack_trace(output, test_class, test_method)

        results["failures"].append({
            "class": test_class,
            "method": test_method,
            "type": failure_type,
            "stack_trace": stack_trace
        })

    return results


def parse_gradle_test_results(output: str) -> Dict[str, Any]:
    """Parse Gradle test output.

    Args:
        output: Gradle test output

    Returns:
        dict with total, passed, failed, skipped, and failure details
    """
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "failures": []
    }

    # Parse summary: X tests completed, Y failed
    summary_pattern = r'(\d+)\s+tests?\s+completed,\s+(\d+)\s+failed'
    summary_match = re.search(summary_pattern, output)

    if summary_match:
        results["total"] = int(summary_match.group(1))
        results["failed"] = int(summary_match.group(2))
        results["passed"] = results["total"] - results["failed"]

    # Another common format: TEST_COUNT tests, FAILURE_COUNT failures
    if results["total"] == 0:
        alt_pattern = r'(\d+)\s+tests?,\s+(\d+)\s+failures?'
        alt_match = re.search(alt_pattern, output)
        if alt_match:
            results["total"] = int(alt_match.group(1))
            results["failed"] = int(alt_match.group(2))
            results["passed"] = results["total"] - results["failed"]

    # Parse test failures
    # Pattern: TestClass > testMethod FAILED
    failure_pattern = r'(\w+)\s*>\s*(\w+)\s*(?:\([^)]*\))?\s*FAILED'
    for match in re.finditer(failure_pattern, output):
        test_class = match.group(1)
        test_method = match.group(2)

        stack_trace = extract_stack_trace(output, test_class, test_method)

        results["failures"].append({
            "class": test_class,
            "method": test_method,
            "type": "failure",
            "stack_trace": stack_trace
        })

    return results


def extract_stack_trace(output: str, test_class: str, test_method: str) -> Optional[str]:
    """Extract stack trace for a specific test failure.

    Args:
        output: Full test output
        test_class: Test class name
        test_method: Test method name

    Returns:
        Stack trace string or None if not found
    """
    # Look for the test failure section
    lines = output.split('\n')
    in_trace = False
    trace_lines = []

    for i, line in enumerate(lines):
        # Start capturing after finding the test name
        if test_method in line and ('FAILURE' in line or 'FAILED' in line or 'ERROR' in line):
            in_trace = True
            continue

        if in_trace:
            # Stop at next test or empty section
            if line.strip() == '' and trace_lines:
                break
            if re.match(r'\w+\.\w+\s+Time elapsed:', line):
                break
            if re.match(r'\w+\s*>\s*\w+', line) and 'PASSED' not in line:
                break

            trace_lines.append(line)

            # Limit trace length
            if len(trace_lines) > 30:
                trace_lines.append("... (truncated)")
                break

    if trace_lines:
        return '\n'.join(trace_lines).strip()

    return None


def summarize_test_output(output: str, success: bool) -> str:
    """Create a brief summary of the test output.

    Args:
        output: Full test output
        success: Whether tests passed

    Returns:
        Summary string
    """
    if success:
        # Look for summary line
        summary_match = re.search(r'Tests run:\s*\d+.*', output)
        if summary_match:
            return summary_match.group(0)

        if "BUILD SUCCESS" in output:
            return "All tests passed"
        elif "BUILD SUCCESSFUL" in output:
            return "All tests passed"
        else:
            return "Tests completed successfully"

    # For failures
    summary_match = re.search(r'Tests run:\s*\d+.*', output)
    if summary_match:
        return summary_match.group(0)

    summary_match = re.search(r'\d+\s+tests?\s+completed,\s+\d+\s+failed', output)
    if summary_match:
        return summary_match.group(0)

    return "Tests failed. Check failures for details."


def get_test_file_location(test_class: str) -> Optional[str]:
    """Find the file location for a test class.

    Args:
        test_class: Test class name

    Returns:
        File path or None if not found
    """
    test_dirs = [
        "src/test/java",
        "src/test/kotlin",
        "test",
        "tests"
    ]

    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            for root, _, files in os.walk(test_dir):
                for file in files:
                    if file == test_class + ".java" or file == test_class + ".kt":
                        return os.path.join(root, file)

    return None


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="run_tests",
    description="Run project tests using Maven or Gradle. Returns test results including failures and stack traces. Use when user says: run tests, test my code, check tests, test failures.",
    parameters={
        "test_class": {
            "type": "string",
            "description": "Optional: specific test class to run"
        },
        "test_method": {
            "type": "string",
            "description": "Optional: specific test method to run (requires test_class)"
        }
    }
)


def register():
    """Register this tool with the registry."""
    register_tool("run_tests", run_tests, TOOL_DEFINITION)
