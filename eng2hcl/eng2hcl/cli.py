#!/usr/bin/env python3
"""
Eng2HCL command-line interface.

Usage:
    python -m eng2hcl.cli input.eng [-o main.tf]
    python -m eng2hcl.cli input.eng --tokens   # debug: show token stream
    python -m eng2hcl.cli input.eng --ast      # debug: show parsed AST
"""

from __future__ import annotations

import argparse
import sys

from . import compile_source, CompileError
from .lexer import tokenize, LexerError
from .parser import parse, ParseError


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eng2hcl",
                                 description="English-to-HCL transpiler")
    ap.add_argument("input", help="input .eng file")
    ap.add_argument("-o", "--output", help="output .tf file (default: stdout)")
    ap.add_argument("--tokens", action="store_true", help="print tokens and exit")
    ap.add_argument("--ast", action="store_true", help="print AST and exit")
    args = ap.parse_args(argv)

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"error: cannot read {args.input}: {e}", file=sys.stderr)
        return 2

    try:
        if args.tokens:
            for t in tokenize(source):
                print(t)
            return 0

        if args.ast:
            import pprint
            pprint.pprint(parse(source))
            return 0

        hcl = compile_source(source)
    except (LexerError, ParseError) as e:
        print(str(e), file=sys.stderr)
        return 1
    except CompileError as e:
        print("Compilation failed:", file=sys.stderr)
        for msg in e.messages:
            print(f"  - {msg}", file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(hcl)
        print(f"Wrote {args.output}")
    else:
        sys.stdout.write(hcl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
