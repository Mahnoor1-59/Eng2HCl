"""Eng2HCL: a structured-English to HCL transpiler."""

from .lexer import tokenize, LexerError
from .parser import parse, ParseError
from .semantic import analyze, SemanticError
from .codegen import generate

__all__ = [
    "tokenize", "parse", "analyze", "generate", "compile_source",
    "LexerError", "ParseError", "SemanticError", "CompileError",
]


class CompileError(Exception):
    """Aggregated compilation failure carrying one or more messages."""
    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("\n".join(messages))


def compile_source(source: str) -> str:
    """Run all phases. Returns HCL text or raises CompileError."""
    # Lexing + parsing raise immediately on the first error.
    program = parse(source)

    # Semantic phase collects all errors before failing.
    errors = analyze(program)
    if errors:
        raise CompileError([str(e) for e in errors])

    return generate(program)
