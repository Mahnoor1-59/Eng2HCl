"""
Abstract Syntax Tree node definitions for Eng2HCL.

A program is a list of ResourceDecl nodes, each carrying a list of Attribute
nodes. Every node tracks its source line for good error messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Attribute:
    """A single key = value pair inside a resource block."""
    key: str
    value: object          # str | int | float | bool
    value_is_string: bool  # how to render: quoted vs bare
    line: int


@dataclass
class ResourceDecl:
    """A single resource declaration, e.g. an aws_s3_bucket named "data"."""
    resource_type: str
    name: str
    attributes: list[Attribute] = field(default_factory=list)
    line: int = 0


@dataclass
class Program:
    resources: list[ResourceDecl] = field(default_factory=list)
