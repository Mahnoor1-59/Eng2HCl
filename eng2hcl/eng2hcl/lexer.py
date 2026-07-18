"""
Lexical Analysis (Scanner) for Eng2HCL.

Converts a structured-English input script into a stream of tokens.
Example:
    create aws_s3_bucket "my_data"
  ->
    [KEYWORD:create] [RESOURCE_TYPE:aws_s3_bucket] [STRING:"my_data"]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    KEYWORD = auto()         # create, named, with, and, set, to
    RESOURCE_TYPE = auto()   # aws_s3_bucket, aws_instance, ...
    IDENTIFIER = auto()      # attribute names: type, region, ...
    STRING = auto()          # "quoted text"
    NUMBER = auto()          # 42, 3
    BOOL = auto()            # true, false
    NEWLINE = auto()
    EOF = auto()


# Reserved English keywords of the source language.
KEYWORDS = {"create", "named", "with", "and", "set", "to"}

# Boolean literals.
BOOLEANS = {"true", "false"}

# Known AWS resource types the language understands. Any token of the form
# aws_* that is not in this set is still lexed as RESOURCE_TYPE, but the
# semantic analyzer decides whether it is supported.
RESOURCE_TYPE_RE = re.compile(r"^aws_[a-z0-9_]+$")


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Token({self.type.name}, {self.value!r}, line={self.line}, col={self.col})"


class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"Lexical error (line {line}, col {col}): {message}")
        self.line = line
        self.col = col


# Master token-matching specification. Order matters.
_TOKEN_SPEC = [
    ("STRING",  r'"(?:\\.|[^"\\])*"'),   # double-quoted string with escapes
    ("NUMBER",  r"\d+(?:\.\d+)?"),
    ("WORD",    r"[A-Za-z_][A-Za-z0-9_\-]*"),
    ("NEWLINE", r"\n"),
    ("SKIP",    r"[ \t\r]+"),
    ("COMMENT", r"\#[^\n]*"),
    ("MISMATCH", r"."),
]
_MASTER_RE = re.compile("|".join(f"(?P<{name}>{pat})" for name, pat in _TOKEN_SPEC))


def tokenize(source: str) -> list[Token]:
    """Turn raw source text into a list of Tokens (ending with EOF)."""
    tokens: list[Token] = []
    line = 1
    line_start = 0

    for m in _MASTER_RE.finditer(source):
        kind = m.lastgroup
        value = m.group()
        col = m.start() - line_start + 1

        if kind == "NEWLINE":
            tokens.append(Token(TokenType.NEWLINE, "\\n", line, col))
            line += 1
            line_start = m.end()
        elif kind == "SKIP" or kind == "COMMENT":
            continue
        elif kind == "STRING":
            tokens.append(Token(TokenType.STRING, value, line, col))
        elif kind == "NUMBER":
            tokens.append(Token(TokenType.NUMBER, value, line, col))
        elif kind == "WORD":
            low = value.lower()
            if low in KEYWORDS:
                tokens.append(Token(TokenType.KEYWORD, low, line, col))
            elif low in BOOLEANS:
                tokens.append(Token(TokenType.BOOL, low, line, col))
            elif RESOURCE_TYPE_RE.match(low):
                tokens.append(Token(TokenType.RESOURCE_TYPE, low, line, col))
            else:
                tokens.append(Token(TokenType.IDENTIFIER, value, line, col))
        elif kind == "MISMATCH":
            raise LexerError(f"unexpected character {value!r}", line, col)

    tokens.append(Token(TokenType.EOF, "", line, 1))
    return tokens
