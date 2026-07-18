# Eng2HCL — Structured-English → HCL Transpiler

A domain-specific compiler that converts a high-level, structured English
language into valid HashiCorp Configuration Language (HCL v2), producing
`.tf` files ready for `terraform plan`.

**Compiler Construction — Semester Project**
Mehreen Shakeel (2023-KIU-BS4002) · Mahnoor Rani (2023-KIU-BS3999)

## What it does

Input (`infra.eng`):
```
create aws_instance named "WebServer" with set ami to "ami-0abc123" and set instance_type to "t2.micro" and set monitoring to true
```

Output (`main.tf`):
```hcl
resource "aws_instance" "WebServer" {
  ami           = "ami-0abc123"
  instance_type = "t2.micro"
  monitoring    = true
}
```

## Compiler phases

The implementation follows the classic linear compiler pipeline described in
the proposal:

1. **Lexical Analysis** (`lexer.py`) — regex-based scanner turning source text
   into tokens (KEYWORD, RESOURCE_TYPE, IDENTIFIER, STRING, NUMBER, BOOL).
   Handles comments, whitespace, case-insensitive keywords, and reports
   line/column on illegal characters.
2. **Syntax Analysis** (`parser.py`) — hand-written recursive-descent parser
   over a Context-Free Grammar, building an Abstract Syntax Tree
   (`ast_nodes.py`).
3. **Semantic Analysis** (`semantic.py`) — "infrastructure validation":
   unsupported resource types, naming collisions, missing required
   attributes, unknown attributes, and constrained-value checks
   (e.g. valid `instance_type`).
4. **Code Generation** (`codegen.py`) — walks the AST and emits correctly
   indented, brace-balanced HCL with aligned assignments and proper
   quoting (strings quoted; numbers/booleans bare).

## Grammar (EBNF)

```
program        ::= { NEWLINE } { statement } EOF
statement      ::= resource_decl { NEWLINE }
resource_decl  ::= "create" RESOURCE_TYPE "named" STRING [ config_clause ]
config_clause  ::= "with" attribute { "and" attribute }
attribute      ::= "set" IDENTIFIER "to" value
value          ::= STRING | NUMBER | BOOL
```

## Usage

```bash
# Transpile to stdout
python -m eng2hcl.cli examples/infra.eng

# Write to a file
python -m eng2hcl.cli examples/infra.eng -o main.tf

# Debug: inspect the token stream or the AST
python -m eng2hcl.cli examples/infra.eng --tokens
python -m eng2hcl.cli examples/infra.eng --ast
```

## Supported resources

| Resource          | Required attributes                        |
|-------------------|--------------------------------------------|
| `aws_s3_bucket`   | (none)                                     |
| `aws_instance`    | `ami`, `instance_type`                     |
| `aws_vpc`         | `cidr_block`                               |
| `aws_db_instance` | `engine`, `instance_class`, `allocated_storage` |

## Tests

```bash
python -m pytest tests/ -v
```

22 tests cover all four phases plus end-to-end compilation. The generated
HCL is additionally validated against the independent `python-hcl2` parser.

## Project layout

```
eng2hcl/
├── eng2hcl/
│   ├── __init__.py      # compile_source() pipeline
│   ├── lexer.py         # Phase 1: scanner
│   ├── ast_nodes.py     # AST definitions
│   ├── parser.py        # Phase 2: recursive-descent parser
│   ├── semantic.py      # Phase 3: validation
│   ├── codegen.py       # Phase 4: HCL emitter
│   └── cli.py           # command-line interface
├── examples/
│   ├── infra.eng        # valid sample
│   ├── bad.eng          # triggers every semantic error
│   └── main.tf          # generated output
└── tests/
    └── test_eng2hcl.py
```
