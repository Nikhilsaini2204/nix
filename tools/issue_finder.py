"""Issue finder composite tool that combines all analysis checks."""

import os
from typing import Dict, List, Any, Optional

from core.tools_registry import register_tool, create_tool_definition
from utils.output import (
    print_tool_start, print_tool_result, is_quiet,
    print_issues_summary, format_issue_with_snippet, print_code_snippet,
    bold, error, warn, success, muted, highlight, Colors
)


def find_issues(include_build: bool = True, include_tests: bool = False,
                limit: int = 30) -> Dict[str, Any]:
    """
    Find all issues in the project by running multiple analysis checks.

    Combines:
    - Build errors (run by default - most critical!)
    - Null safety analysis
    - Bean wiring analysis
    - Annotation analysis
    - Optional: Test failures

    Results are prioritized by severity.

    Args:
        include_build: If True (default), run build and include compile errors
        include_tests: If True, run tests and include test failures
        limit: Maximum number of issues to return per category

    Returns:
        dict with categorized issues, summary, and recommendations
    """
    if not is_quiet():
        print_tool_start("find_issues")

    all_issues = []
    category_counts = {}
    errors = []

    # Run build FIRST - compile errors are the most critical!
    build_errors = []
    if include_build:
        try:
            from tools.build_runner import build_project
            from utils.output import set_quiet_mode

            # Run build in quiet mode to avoid duplicate output
            set_quiet_mode(True)
            build_result = build_project()
            set_quiet_mode(False)

            if not build_result.get('success') and build_result.get('errors'):
                for err in build_result['errors']:
                    err['category'] = 'compile_error'
                    if not err.get('severity'):
                        err['severity'] = 'critical'
                build_errors = build_result['errors']
                all_issues.extend(build_errors)
                category_counts['compile_errors'] = len(build_errors)

                # Print build status
                if not is_quiet():
                    print_tool_result(error(f"Build failed with {len(build_errors)} compile errors"))
            elif build_result.get('success'):
                if not is_quiet():
                    print_tool_result(success("Build successful - no compile errors"))
        except Exception as e:
            errors.append(f"Build check failed: {str(e)}")

    # Run other checks in quiet mode to consolidate output
    from utils.output import set_quiet_mode
    set_quiet_mode(True)

    # Run null safety check
    try:
        from tools.null_safety_checker import check_null_safety
        null_result = check_null_safety(limit=limit)
        if null_result.get('issues'):
            for issue in null_result['issues']:
                issue['category'] = 'null_safety'
            all_issues.extend(null_result['issues'])
            category_counts['null_safety'] = len(null_result['issues'])
    except Exception as e:
        errors.append(f"Null safety check failed: {str(e)}")

    # Run bean wiring check
    try:
        from tools.bean_wiring_checker import check_bean_wiring
        bean_result = check_bean_wiring()
        if bean_result.get('issues'):
            for issue in bean_result['issues']:
                issue['category'] = 'bean_wiring'
            all_issues.extend(bean_result['issues'])
            category_counts['bean_wiring'] = len(bean_result['issues'])
    except Exception as e:
        errors.append(f"Bean wiring check failed: {str(e)}")

    # Run annotation check
    try:
        from tools.annotation_checker import check_annotations
        annotation_result = check_annotations()
        if annotation_result.get('issues'):
            for issue in annotation_result['issues']:
                issue['category'] = 'annotations'
            all_issues.extend(annotation_result['issues'])
            category_counts['annotations'] = len(annotation_result['issues'])
    except Exception as e:
        errors.append(f"Annotation check failed: {str(e)}")

    # Run security check
    try:
        from tools.security_checker import check_security
        security_result = check_security(limit=limit)
        if security_result.get('issues'):
            for issue in security_result['issues']:
                if 'category' not in issue:
                    issue['category'] = 'security'
            all_issues.extend(security_result['issues'])
            category_counts['security'] = len(security_result['issues'])
    except Exception as e:
        errors.append(f"Security check failed: {str(e)}")

    set_quiet_mode(False)

    # Optional: Run tests
    test_failures = []
    if include_tests:
        try:
            from tools.test_runner import run_tests
            test_result = run_tests()
            if test_result.get('failures'):
                for failure in test_result['failures']:
                    failure['category'] = 'test_failure'
                    failure['severity'] = 'high'
                    failure['issue'] = f"Test {failure.get('class', '')}.{failure.get('method', '')} failed"
                test_failures = test_result['failures']
                all_issues.extend(test_failures)
                category_counts['test_failures'] = len(test_failures)
        except Exception as e:
            errors.append(f"Test check failed: {str(e)}")

    # Build index if not already built
    try:
        from indexer import IndexBuilder
        builder = IndexBuilder()
        index_result = builder.build_index()
        if index_result.get('rebuilt'):
            if not is_quiet():
                print_tool_result(f"Index built: {index_result.get('stats', {})}")
    except Exception as e:
        errors.append(f"Index build failed: {str(e)}")

    # Prioritize and sort issues
    all_issues = prioritize_issues(all_issues)

    # Limit total issues
    if len(all_issues) > limit:
        all_issues = all_issues[:limit]

    # Generate recommendations
    recommendations = generate_recommendations(all_issues, category_counts)

    # Build result
    result = {
        "total_issues": len(all_issues),
        "by_category": category_counts,
        "issues": all_issues,
        "recommendations": recommendations,
        "errors": errors if errors else None
    }

    # Generate summary
    high_count = sum(1 for i in all_issues if i.get('severity') == 'high' or i.get('severity') == 'critical')
    medium_count = sum(1 for i in all_issues if i.get('severity') == 'medium')
    low_count = sum(1 for i in all_issues if i.get('severity') == 'low')

    result["summary"] = f"Found {len(all_issues)} issues: {high_count} high, {medium_count} medium, {low_count} low priority"

    if not is_quiet():
        print_tool_result(result["summary"])
        # Print colored issues with snippets
        if all_issues:
            print_issues_summary(all_issues[:10], "Top Issues")  # Show top 10 with snippets

    return result


def prioritize_issues(issues: List[Dict]) -> List[Dict]:
    """Sort issues by severity and category.

    Args:
        issues: List of issue dictionaries

    Returns:
        Sorted list with most critical first
    """
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    category_order = {
        "compile_error": 0,
        "security": 1,  # Security issues are high priority
        "test_failure": 2,
        "bean_wiring": 3,
        "null_safety": 4,
        "annotations": 5
    }

    return sorted(issues, key=lambda x: (
        severity_order.get(x.get("severity", "low"), 4),
        category_order.get(x.get("category", "other"), 5),
        x.get("file", "") or "",
        x.get("line", 0) or 0
    ))


def generate_recommendations(issues: List[Dict], category_counts: Dict) -> List[str]:
    """Generate actionable recommendations based on found issues.

    Args:
        issues: List of all issues
        category_counts: Count of issues by category

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Compile errors are most critical
    if category_counts.get('compile_errors', 0) > 0:
        recommendations.append("Fix compile errors first - the project won't run until these are resolved")

    # Test failures next
    if category_counts.get('test_failures', 0) > 0:
        count = category_counts['test_failures']
        recommendations.append(f"Address {count} failing test(s) to ensure code correctness")

    # Bean wiring issues can cause runtime failures
    if category_counts.get('bean_wiring', 0) > 0:
        count = category_counts['bean_wiring']
        recommendations.append(f"Review {count} bean wiring issue(s) - these can cause startup failures")

    # Null safety issues
    if category_counts.get('null_safety', 0) > 0:
        count = category_counts['null_safety']
        high_count = sum(1 for i in issues if i.get('category') == 'null_safety' and i.get('severity') == 'high')
        if high_count > 0:
            recommendations.append(f"Fix {high_count} high-risk null safety issues to prevent NPEs")
        else:
            recommendations.append(f"Consider addressing {count} potential null safety concerns")

    # Annotation issues
    if category_counts.get('annotations', 0) > 0:
        count = category_counts['annotations']
        recommendations.append(f"Review {count} annotation issue(s) for best practices")

    # Security issues
    if category_counts.get('security', 0) > 0:
        count = category_counts['security']
        critical_count = sum(1 for i in issues if i.get('category') == 'security' and i.get('severity') == 'critical')
        if critical_count > 0:
            recommendations.append(f"URGENT: Fix {critical_count} critical security vulnerabilities")
        else:
            recommendations.append(f"Address {count} security issue(s) to improve application security")

    if not recommendations:
        recommendations.append("No critical issues found. Consider running full build and tests for verification.")

    return recommendations


def get_top_issues(issues: List[Dict], n: int = 5) -> List[Dict]:
    """Get the top N most critical issues.

    Args:
        issues: List of issues
        n: Number of issues to return

    Returns:
        Top N issues
    """
    return issues[:n]


def format_issue_summary(issue: Dict) -> str:
    """Format an issue for display.

    Args:
        issue: Issue dictionary

    Returns:
        Formatted string
    """
    severity = issue.get('severity', 'unknown').upper()
    category = issue.get('category', 'unknown')
    file_path = issue.get('file', 'unknown')
    line = issue.get('line', '?')
    message = issue.get('issue', issue.get('message', 'No description'))

    if file_path and file_path != 'unknown':
        file_name = os.path.basename(file_path)
        location = f"{file_name}:{line}"
    else:
        location = "project"

    return f"[{severity}] [{category}] {location}: {message}"


# Tool definition
TOOL_DEFINITION = create_tool_definition(
    name="find_issues",
    description="Find all issues in the project. Runs BUILD first (compile errors are critical!), then null safety, bean wiring, and annotation checks. Optionally runs tests. Returns prioritized issues with recommendations.",
    parameters={
        "include_build": {
            "type": "boolean",
            "description": "If true (DEFAULT), run build and include compile errors"
        },
        "include_tests": {
            "type": "boolean",
            "description": "If true, run tests and include test failures (default false)"
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of issues per category (default 30)"
        }
    }
)


def register():
    """Register this tool with the registry."""
    register_tool("find_issues", find_issues, TOOL_DEFINITION)
