"""
Syntax Analysis (Parser) for Eng2HCL.

Implements a hand-written recursive-descent parser over the token stream.

Grammar (EBNF):
    program        ::= { NEWLINE } { statement } EOF
    statement      ::= resource_decl { NEWLINE }
    resource_decl  ::= "create" RESOURCE_TYPE "named" STRING [ config_clause ]
    config_clause  ::= "with" attribute { "and" attribute }
    attribute      ::= "set" IDENTIFIER "to" value
    value          ::= STRING | NUMBER | BOOL

Produces a Program AST. Raises ParseError with line/col on any violation.
"""

from __future__ import annotations

from .lexer import Token, TokenType, tokenize
from .ast_nodes import Program, ResourceDecl, Attribute


class ParseError(Exception):
    def __init__(self, message: str, token: Token):
        super().__init__(
            f"Syntax error (line {token.line}, col {token.col}): {message} "
            f"(got {token.type.name} {token.value!r})"
        )
        self.token = token


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # ---- token stream helpers -------------------------------------------
    @property
    def current(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def check(self, ttype: TokenType, value: str | None = None) -> bool:
        if self.current.type != ttype:
            return False
        if value is not None and self.current.value != value:
            return False
        return True

    def expect(self, ttype: TokenType, value: str | None = None,
               what: str | None = None) -> Token:
        if self.check(ttype, value):
            return self.advance()
        expected = what or (f"{value!r}" if value else ttype.name)
        raise ParseError(f"expected {expected}", self.current)

    def skip_newlines(self) -> None:
        while self.check(TokenType.NEWLINE):
            self.advance()

    # ---- grammar rules ---------------------------------------------------
    def parse_program(self) -> Program:
        program = Program()
        self.skip_newlines()
        while not self.check(TokenType.EOF):
            program.resources.append(self.parse_resource_decl())
            self.skip_newlines()
        return program

    def parse_resource_decl(self) -> ResourceDecl:
        kw = self.expect(TokenType.KEYWORD, "create", what="'create' keyword")
        rtype = self.expect(TokenType.RESOURCE_TYPE,
                            what="a resource type (e.g. aws_s3_bucket)")
        self.expect(TokenType.KEYWORD, "named", what="'named' keyword")
        name_tok = self.expect(TokenType.STRING, what="a quoted resource name")

        decl = ResourceDecl(
            resource_type=rtype.value,
            name=_unquote(name_tok.value),
            line=kw.line,
        )

        # Optional configuration clause.
        if self.check(TokenType.KEYWORD, "with"):
            self.advance()
            decl.attributes.append(self.parse_attribute())
            while self.check(TokenType.KEYWORD, "and"):
                self.advance()
                decl.attributes.append(self.parse_attribute())

        return decl

    def parse_attribute(self) -> Attribute:
        self.expect(TokenType.KEYWORD, "set", what="'set' keyword")
        key_tok = self.expect(TokenType.IDENTIFIER, what="an attribute name")
        self.expect(TokenType.KEYWORD, "to", what="'to' keyword")
        value, is_string = self.parse_value()
        return Attribute(
            key=key_tok.value,
            value=value,
            value_is_string=is_string,
            line=key_tok.line,
        )

    def parse_value(self):
        tok = self.current
        if tok.type == TokenType.STRING:
            self.advance()
            return _unquote(tok.value), True
        if tok.type == TokenType.NUMBER:
            self.advance()
            num = float(tok.value) if "." in tok.value else int(tok.value)
            return num, False
        if tok.type == TokenType.BOOL:
            self.advance()
            return (tok.value == "true"), False
        raise ParseError("expected a value (string, number, or boolean)", tok)


_ESCAPES = {
    '"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r",
}


def _unquote(s: str) -> str:
    """Strip surrounding double quotes and process a safe, fixed set of
    escape sequences (\\" \\\\ \\n \\t \\r). Unknown escapes are kept
    literally (backslash preserved) rather than crashing. This avoids the
    pitfalls of str.decode('unicode_escape'), which mangles paths like
    C:\\new and raises on \\x sequences."""
    inner = s[1:-1]
    out = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            nxt = inner[i + 1]
            out.append(_ESCAPES.get(nxt, "\\" + nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def parse(source: str) -> Program:
    return Parser(tokenize(source)).parse_program()
