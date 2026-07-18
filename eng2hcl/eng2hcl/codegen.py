"""
Code Generation for Eng2HCL.

Walks the validated AST and emits well-formed, correctly indented
HashiCorp Configuration Language (HCL v2) suitable for `terraform plan`.
"""

from __future__ import annotations

from .ast_nodes import Program, ResourceDecl, Attribute

INDENT = "  "


def generate(program: Program) -> str:
    blocks = [_gen_resource(res) for res in program.resources]
    return "\n\n".join(blocks) + "\n" if blocks else ""


def _gen_resource(res: ResourceDecl) -> str:
    lines = [f'resource "{res.resource_type}" "{_sanitize(res.name)}" {{']

    # Compute alignment width so the `=` signs line up neatly.
    width = max((len(a.key) for a in res.attributes), default=0)
    for attr in res.attributes:
        lines.append(f"{INDENT}{attr.key.ljust(width)} = {_render_value(attr)}")

    lines.append("}")
    return "\n".join(lines)


def _render_value(attr: Attribute) -> str:
    if attr.value_is_string:
        return f'"{_escape_string(attr.value)}"'
    if isinstance(attr.value, bool):
        return "true" if attr.value else "false"
    return str(attr.value)


def _escape_string(s: str) -> str:
    """Escape a Python string into a safe HCL double-quoted literal.
    Backslash must be escaped first to avoid double-processing."""
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\t", "\\t")
    s = s.replace("\r", "\\r")
    return s


def _sanitize(name: str) -> str:
    """Terraform labels must be valid identifiers; map spaces/dashes to _."""
    out = []
    for ch in name:
        out.append(ch if (ch.isalnum() or ch == "_") else "_")
    label = "".join(out)
    if label and label[0].isdigit():
        label = "_" + label
    return label or "resource"
