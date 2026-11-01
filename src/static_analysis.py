"""Lightweight advisory checks for teacher-configured C source rules."""

import re
from typing import Any


ENGINE_NAME = "jutge-static-rules-v1"
CALL_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_rules(rules: dict[str, Any]) -> None:
    if not isinstance(rules, dict):
        raise ValueError("static_rules must be an object")
    rule_set = rules.get("static_rules", rules)
    if not isinstance(rule_set, dict):
        raise ValueError("static_rules.static_rules must be an object")

    supported_keys = {
        "required_calls", "forbidden_calls", "forbidden_headers",
        "min_counts", "max_counts", "required_pairs",
    }
    unknown_keys = set(rule_set) - supported_keys
    if unknown_keys:
        raise ValueError(f"Unsupported static rule keys: {', '.join(sorted(unknown_keys))}")

    for key in ("required_calls", "forbidden_calls", "forbidden_headers"):
        values = rule_set.get(key, [])
        if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
            raise ValueError(f"{key} must be a list of non-empty strings")
        if key != "forbidden_headers" and any(not CALL_NAME_PATTERN.fullmatch(value) for value in values):
            raise ValueError(f"{key} entries must be C identifiers")

    for key in ("min_counts", "max_counts"):
        values = rule_set.get(key, {})
        if not isinstance(values, dict):
            raise ValueError(f"{key} must be an object")
        for name, count in values.items():
            if not CALL_NAME_PATTERN.fullmatch(str(name)) or not isinstance(count, int) or count < 0:
                raise ValueError(f"{key} must map C identifiers to non-negative integers")

    pairs = rule_set.get("required_pairs", [])
    if not isinstance(pairs, list) or any(
        not isinstance(pair, list)
        or len(pair) != 2
        or any(not isinstance(name, str) or not CALL_NAME_PATTERN.fullmatch(name) for name in pair)
        for pair in pairs
    ):
        raise ValueError("required_pairs must be a list of two-identifier lists")


def _mask_comments_and_literals(source: str) -> str:
    masked = list(source)
    index = 0
    state = "code"
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""

        if state == "code":
            if char == "/" and following == "/":
                masked[index] = masked[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if char == "/" and following == "*":
                masked[index] = masked[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if char in ('"', "'"):
                state = "string" if char == '"' else "char"
                masked[index] = " "
                index += 1
                continue
        elif state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                masked[index] = " "
        elif state == "block_comment":
            if char == "*" and following == "/":
                masked[index] = masked[index + 1] = " "
                index += 2
                state = "code"
                continue
            if char != "\n":
                masked[index] = " "
        else:
            if char == "\\":
                if char != "\n":
                    masked[index] = " "
                if index + 1 < len(source):
                    if source[index + 1] != "\n":
                        masked[index + 1] = " "
                    index += 2
                    continue
            if (state == "string" and char == '"') or (state == "char" and char == "'"):
                masked[index] = " "
                state = "code"
            elif char != "\n":
                masked[index] = " "
        index += 1
    return "".join(masked)


def analyze_source(source: str, rules: dict[str, Any], filename: str = "submission.c") -> dict[str, Any]:
    rule_set = rules.get("static_rules", rules) if isinstance(rules, dict) else {}
    if not isinstance(rule_set, dict):
        rule_set = {}

    clean = _mask_comments_and_literals(source or "")
    function_names = set(rule_set.get("required_calls", [])) | set(rule_set.get("forbidden_calls", []))
    function_names |= set((rule_set.get("min_counts") or {}).keys())
    function_names |= set((rule_set.get("max_counts") or {}).keys())

    counts: dict[str, int] = {}
    evidence: dict[str, list[int]] = {}
    for function_name in sorted(str(name) for name in function_names):
        matches = list(re.finditer(rf"\b{re.escape(function_name)}\s*\(", clean))
        counts[function_name] = len(matches)
        evidence[function_name] = [clean.count("\n", 0, match.start()) + 1 for match in matches]

    headers = []
    for original_line, clean_line in zip((source or "").splitlines(), clean.splitlines()):
        if re.match(r"^\s*#\s*include\b", clean_line):
            include_match = re.match(r"^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]", original_line)
            if include_match:
                headers.append(include_match.group(1))
    forbidden_headers = set(str(name) for name in rule_set.get("forbidden_headers", []))
    violations: list[str] = []
    missing_required = [str(name) for name in rule_set.get("required_calls", []) if counts.get(str(name), 0) == 0]
    forbidden_calls = [str(name) for name in rule_set.get("forbidden_calls", []) if counts.get(str(name), 0) > 0]
    forbidden_headers_found = sorted(forbidden_headers.intersection(headers))

    for function_name in missing_required:
        violations.append(f"required call missing: {function_name}")
    for function_name in forbidden_calls:
        violations.append(f"forbidden call detected: {function_name}")
    for header in forbidden_headers_found:
        violations.append(f"forbidden header detected: {header}")
    for function_name, minimum in (rule_set.get("min_counts") or {}).items():
        if counts.get(str(function_name), 0) < int(minimum):
            violations.append(f"{function_name} count {counts.get(str(function_name), 0)} < min {minimum}")
    for function_name, maximum in (rule_set.get("max_counts") or {}).items():
        if counts.get(str(function_name), 0) > int(maximum):
            violations.append(f"{function_name} count {counts.get(str(function_name), 0)} > max {maximum}")

    for pair in rule_set.get("required_pairs", []):
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            first, second = map(str, pair)
            if counts.get(first, 0) > 0 and counts.get(second, 0) == 0:
                violations.append(f"required pair violated: {first} requires {second}")

    return {
        "engine": ENGINE_NAME,
        "filename": filename,
        "counts": counts,
        "call_lines": evidence,
        "missing_required_calls": missing_required,
        "forbidden_calls_found": forbidden_calls,
        "forbidden_headers_found": forbidden_headers_found,
        "violations": violations,
        "summary": "Advisory only; this report does not affect the judge verdict.",
    }


def analyze_sources(sources: dict[str, str], rules: dict[str, Any]) -> dict[str, Any] | None:
    if not rules:
        return None
    reports = [analyze_source(source, rules, filename) for filename, source in sorted(sources.items())]
    return {
        "engine": ENGINE_NAME,
        "advisory_only": True,
        "files": reports,
        "violations_count": sum(len(report["violations"]) for report in reports),
    }
