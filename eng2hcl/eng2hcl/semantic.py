"""
Semantic Analysis for Eng2HCL ("Infrastructure Validation").

Checks performed:
  * Resource type is supported (known AWS resource).
  * No duplicate logical resource names within the same resource type
    (naming collision detection).
  * Required attributes are present for each resource type.
  * Unknown attributes are flagged.
  * Constrained values (e.g. instance_type) are validated against an allow-list.

Returns a list of SemanticError objects. An empty list means the program is
semantically valid.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ast_nodes import Program, ResourceDecl


@dataclass
class SemanticError:
    message: str
    line: int

    def __str__(self) -> str:
        return f"Semantic error (line {self.line}): {self.message}"


# Schema of supported resources: required attrs, optional attrs, and any
# value constraints. This is intentionally small but realistic.
RESOURCE_SCHEMA = {
    "aws_s3_bucket": {
        "required": [],
        "optional": ["acl", "versioning", "region", "tags"],
        "constraints": {
            "acl": {"private", "public-read", "public-read-write",
                    "authenticated-read"},
        },
    },
    "aws_instance": {
        "required": ["ami", "instance_type"],
        "optional": ["region", "key_name", "monitoring", "tags"],
        "constraints": {
            "instance_type": {
                "t2.micro", "t2.small", "t2.medium",
                "t3.micro", "t3.small", "t3.medium",
                "m5.large", "m5.xlarge",
            },
        },
    },
    "aws_db_instance": {
        "required": ["engine", "instance_class", "allocated_storage"],
        "optional": ["region", "username", "multi_az", "tags"],
        "constraints": {
            "engine": {"mysql", "postgres", "mariadb", "oracle-se2"},
        },
    },
    "aws_vpc": {
        "required": ["cidr_block"],
        "optional": ["region", "tags", "enable_dns_support"],
        "constraints": {},
    },
}


def analyze(program: Program) -> list[SemanticError]:
    errors: list[SemanticError] = []
    seen: dict[tuple[str, str], int] = {}  # (rtype, name) -> first line

    for res in program.resources:
        _check_resource(res, seen, errors)

    return errors


def _check_resource(res: ResourceDecl, seen: dict, errors: list) -> None:
    schema = RESOURCE_SCHEMA.get(res.resource_type)

    # 1. Unsupported resource type.
    if schema is None:
        supported = ", ".join(sorted(RESOURCE_SCHEMA))
        errors.append(SemanticError(
            f"unsupported resource type '{res.resource_type}'. "
            f"Supported types: {supported}",
            res.line,
        ))
        return

    # 2. Empty resource name.
    if res.name.strip() == "":
        errors.append(SemanticError(
            f"empty name for {res.resource_type} (a non-empty quoted name is required)",
            res.line,
        ))

    # 3. Naming collision.
    key = (res.resource_type, res.name)
    if key in seen:
        errors.append(SemanticError(
            f"duplicate name '{res.name}' for {res.resource_type} "
            f"(first declared on line {seen[key]})",
            res.line,
        ))
    else:
        seen[key] = res.line

    known = set(schema["required"]) | set(schema["optional"])
    provided = {a.key for a in res.attributes}

    # 4. Duplicate attribute keys within the same resource (invalid HCL).
    attr_lines: dict[str, int] = {}
    for attr in res.attributes:
        if attr.key in attr_lines:
            errors.append(SemanticError(
                f"duplicate attribute '{attr.key}' for {res.resource_type} "
                f"'{res.name}' (first set on line {attr_lines[attr.key]})",
                attr.line,
            ))
        else:
            attr_lines[attr.key] = attr.line

    # 5. Unknown attributes + constrained values.
    for attr in res.attributes:
        if attr.key not in known:
            errors.append(SemanticError(
                f"unknown attribute '{attr.key}' for {res.resource_type}",
                attr.line,
            ))
            continue
        allowed = schema["constraints"].get(attr.key)
        if allowed is not None and attr.value not in allowed:
            errors.append(SemanticError(
                f"invalid value '{attr.value}' for '{attr.key}'. "
                f"Allowed: {', '.join(sorted(allowed))}",
                attr.line,
            ))

    # 6. Missing required attributes.
    for req in schema["required"]:
        if req not in provided:
            errors.append(SemanticError(
                f"missing required attribute '{req}' for {res.resource_type} "
                f"'{res.name}'",
                res.line,
            ))
