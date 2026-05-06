"""Minimalist Salesforce formula parser used to build decision trees.

The goal is not to implement the full Salesforce formula language but to
extract the top-level logical structure (AND / OR / NOT / IF and leaf
comparisons) so we can render a Mermaid decision diagram that is actually
readable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FormulaNode:
    kind: str  # "AND", "OR", "NOT", "IF", "LEAF"
    text: str = ""
    children: list["FormulaNode"] = field(default_factory=list)


_WHITESPACE_RE = re.compile(r"\s+")


def parse_formula(text: str) -> FormulaNode:
    """Parse a Salesforce formula string into a lightweight AST."""
    if not text:
        return FormulaNode(kind="LEAF", text="")
    normalized = _normalize(text)
    try:
        return _parse(normalized)
    except Exception:
        return FormulaNode(kind="LEAF", text=normalized)


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _parse(text: str) -> FormulaNode:
    text = _strip_outer_parens(text.strip())
    if not text:
        return FormulaNode(kind="LEAF", text="")

    or_parts = _split_toplevel(text, "||")
    if len(or_parts) > 1:
        return FormulaNode(
            kind="OR", text=text, children=[_parse(part) for part in or_parts]
        )

    and_parts = _split_toplevel(text, "&&")
    if len(and_parts) > 1:
        return FormulaNode(
            kind="AND", text=text, children=[_parse(part) for part in and_parts]
        )

    call = _match_function_call(text)
    if call is not None:
        name, args_text = call
        upper = name.upper()
        if upper == "AND":
            args = _split_args(args_text)
            if args:
                return FormulaNode(
                    kind="AND", text=text, children=[_parse(arg) for arg in args]
                )
        if upper == "OR":
            args = _split_args(args_text)
            if args:
                return FormulaNode(
                    kind="OR", text=text, children=[_parse(arg) for arg in args]
                )
        if upper == "NOT":
            args = _split_args(args_text)
            if len(args) == 1:
                return FormulaNode(
                    kind="NOT", text=text, children=[_parse(args[0])]
                )
        if upper == "IF":
            args = _split_args(args_text)
            if len(args) == 3:
                return FormulaNode(
                    kind="IF",
                    text=text,
                    children=[_parse(arg) for arg in args],
                )

    return FormulaNode(kind="LEAF", text=text)


def _strip_outer_parens(text: str) -> str:
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        balanced_pair = True
        for i, ch in enumerate(text):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i < len(text) - 1:
                    balanced_pair = False
                    break
        if not balanced_pair:
            return text
        text = text[1:-1].strip()
    return text


def _match_function_call(text: str) -> tuple[str, str] | None:
    if not text.endswith(")"):
        return None
    match = re.match(r"^([A-Za-z_][A-Za-z_0-9]*)\s*\(", text)
    if not match:
        return None
    start = match.end() - 1
    depth = 0
    in_string = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                if i != len(text) - 1:
                    return None
                return match.group(1), text[start + 1 : i]
    return None


def _split_toplevel(text: str, op: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    in_string = False
    start = 0
    i = 0
    op_len = len(op)
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth -= 1
            i += 1
            continue
        if depth == 0 and text[i : i + op_len] == op:
            parts.append(text[start:i].strip())
            i += op_len
            start = i
            continue
        i += 1
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def _split_args(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    in_string = False
    start = 0
    for i, ch in enumerate(text):
        if in_string:
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def describe_kind(kind: str, lang: str = "fr") -> str:
    mapping_fr = {
        "AND": "Toutes ces conditions sont vraies",
        "OR": "Au moins une de ces conditions est vraie",
        "NOT": "La condition suivante est fausse",
        "IF": "Selon la condition",
        "LEAF": "Condition",
    }
    mapping_en = {
        "AND": "All these conditions are true",
        "OR": "At least one of these conditions is true",
        "NOT": "The following condition is false",
        "IF": "Depending on the condition",
        "LEAF": "Condition",
    }
    return (mapping_en if lang.startswith("en") else mapping_fr).get(kind, kind)
