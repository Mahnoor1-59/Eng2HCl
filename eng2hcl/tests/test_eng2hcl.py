"""Test suite for Eng2HCL. Run with: python -m pytest tests/ -v"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from eng2hcl import compile_source, CompileError
from eng2hcl.lexer import tokenize, TokenType, LexerError
from eng2hcl.parser import parse, ParseError
from eng2hcl.semantic import analyze


# ---------------------------------------------------------------- Lexer ----
def test_lexer_basic_tokens():
    toks = tokenize('create aws_s3_bucket named "my_data"')
    types = [t.type for t in toks if t.type != TokenType.EOF]
    assert types == [
        TokenType.KEYWORD, TokenType.RESOURCE_TYPE,
        TokenType.KEYWORD, TokenType.STRING,
    ]


def test_lexer_keyword_case_insensitive():
    toks = tokenize("CREATE aws_vpc NAMED \"v\"")
    assert toks[0].type == TokenType.KEYWORD and toks[0].value == "create"


def test_lexer_numbers_and_bools():
    toks = tokenize("set x to 20 set y to true")
    vals = {t.type for t in toks}
    assert TokenType.NUMBER in vals and TokenType.BOOL in vals


def test_lexer_comment_and_skip():
    toks = tokenize("# just a comment\ncreate aws_vpc named \"v\"")
    # comment produces no token; newline + statement remain
    assert any(t.type == TokenType.RESOURCE_TYPE for t in toks)


def test_lexer_rejects_bad_char():
    with pytest.raises(LexerError):
        tokenize("create aws_vpc named @bad")


# --------------------------------------------------------------- Parser ----
def test_parser_single_resource_no_config():
    prog = parse('create aws_vpc named "main" with set cidr_block to "10.0.0.0/16"')
    assert len(prog.resources) == 1
    r = prog.resources[0]
    assert r.resource_type == "aws_vpc"
    assert r.name == "main"
    assert r.attributes[0].key == "cidr_block"


def test_parser_multiple_attributes():
    prog = parse('create aws_instance named "w" with '
                 'set ami to "a" and set instance_type to "t2.micro"')
    assert len(prog.resources[0].attributes) == 2


def test_parser_missing_named_keyword():
    with pytest.raises(ParseError):
        parse('create aws_vpc "main"')


def test_parser_missing_value():
    with pytest.raises(ParseError):
        parse('create aws_vpc named "v" with set cidr_block to')


def test_parser_value_types():
    prog = parse('create aws_instance named "w" with '
                 'set ami to "a" and set instance_type to "t2.micro" '
                 'and set monitoring to true')
    attrs = {a.key: a.value for a in prog.resources[0].attributes}
    assert attrs["monitoring"] is True


# ------------------------------------------------------------- Semantic ----
def test_semantic_valid_program_has_no_errors():
    prog = parse('create aws_vpc named "v" with set cidr_block to "10.0.0.0/16"')
    assert analyze(prog) == []


def test_semantic_naming_collision():
    prog = parse('create aws_vpc named "v" with set cidr_block to "10.0.0.0/8"\n'
                 'create aws_vpc named "v" with set cidr_block to "10.0.0.0/8"')
    errs = analyze(prog)
    assert any("duplicate name" in str(e) for e in errs)


def test_semantic_unsupported_resource():
    prog = parse('create aws_lambda named "fn"')
    errs = analyze(prog)
    assert any("unsupported resource type" in str(e) for e in errs)


def test_semantic_missing_required():
    prog = parse('create aws_instance named "w" with set ami to "a"')
    errs = analyze(prog)
    assert any("missing required attribute 'instance_type'" in str(e) for e in errs)


def test_semantic_invalid_constrained_value():
    prog = parse('create aws_instance named "w" with '
                 'set ami to "a" and set instance_type to "nope.big"')
    errs = analyze(prog)
    assert any("invalid value" in str(e) for e in errs)


def test_semantic_unknown_attribute():
    prog = parse('create aws_vpc named "v" with set cidr_block to "10.0.0.0/16" '
                 'and set bogus to "x"')
    errs = analyze(prog)
    assert any("unknown attribute 'bogus'" in str(e) for e in errs)


# --------------------------------------------------------------- Codegen ---
def test_codegen_produces_valid_block():
    hcl = compile_source('create aws_vpc named "main" with set cidr_block to "10.0.0.0/16"')
    assert 'resource "aws_vpc" "main"' in hcl
    assert "cidr_block = \"10.0.0.0/16\"" in hcl
    assert hcl.count("{") == hcl.count("}")


def test_codegen_bool_unquoted():
    hcl = compile_source('create aws_instance named "w" with '
                         'set ami to "a" and set instance_type to "t2.micro" '
                         'and set monitoring to true')
    import re
    assert re.search(r"monitoring\s+= true", hcl)
    assert '"true"' not in hcl


def test_codegen_number_unquoted():
    hcl = compile_source('create aws_db_instance named "db" with '
                         'set engine to "mysql" and set instance_class to "db.t3.micro" '
                         'and set allocated_storage to 20')
    assert "allocated_storage = 20" in hcl


def test_codegen_sanitizes_label():
    hcl = compile_source('create aws_vpc named "main-vpc" with set cidr_block to "10.0.0.0/16"')
    assert 'resource "aws_vpc" "main_vpc"' in hcl


# --------------------------------------------------------- End-to-end ----
def test_compile_raises_on_semantic_error():
    with pytest.raises(CompileError):
        compile_source('create aws_lambda named "fn"')


def test_braces_balanced_multi_resource():
    src = ('create aws_vpc named "v" with set cidr_block to "10.0.0.0/16"\n'
           'create aws_s3_bucket named "b" with set acl to "private"')
    hcl = compile_source(src)
    assert hcl.count("{") == hcl.count("}") == 2


# ----------------------------------------------- Regression (review bugs) --
def test_unquote_backslash_n_roundtrips_safely():
    # \n is interpreted as a newline on input, then re-escaped on output,
    # so the generated HCL never contains a raw newline mid-value.
    hcl = compile_source(r'create aws_s3_bucket named "b" with set region to "a\nb"')
    assert '"a\\nb"' in hcl          # escaped in output
    assert '"a\nb"' not in hcl        # not a raw newline


def test_unquote_handles_x_escape_without_crashing():
    # Previously raised UnicodeDecodeError.
    prog = parse(r'create aws_vpc named "p\xZZq" with set cidr_block to "10.0.0.0/16"')
    assert "xZZq" in prog.resources[0].name


def test_unquote_supported_escapes():
    prog = parse(r'create aws_s3_bucket named "tab\there" with set acl to "private"')
    assert "\t" in prog.resources[0].name


def test_codegen_escapes_quotes_in_value():
    # A quote in a value must be escaped so the HCL stays valid.
    hcl = compile_source('create aws_s3_bucket named "b" with set region to "us\\"east"')
    assert r'region = "us\"east"' in hcl


def test_codegen_escapes_newline_in_value():
    prog_src = 'create aws_s3_bucket named "b" with set region to "a\\nb"'
    hcl = compile_source(prog_src)
    # The literal backslash-n stays escaped; no raw newline injected mid-value.
    assert '"a\\nb"' in hcl


def test_semantic_duplicate_attribute_detected():
    src = ('create aws_vpc named "v" with '
           'set cidr_block to "10.0.0.0/16" and set cidr_block to "10.0.0.0/8"')
    with pytest.raises(CompileError) as ei:
        compile_source(src)
    assert any("duplicate attribute 'cidr_block'" in m for m in ei.value.messages)


def test_semantic_empty_name_detected():
    with pytest.raises(CompileError) as ei:
        compile_source('create aws_vpc named "" with set cidr_block to "10.0.0.0/16"')
    assert any("empty name" in m for m in ei.value.messages)


def test_generated_hcl_parses_with_real_parser():
    # End-to-end: output must parse under an independent HCL parser.
    hcl2 = pytest.importorskip("hcl2")
    import io
    src = ('create aws_vpc named "main-vpc" with set cidr_block to "10.0.0.0/16"\n'
           'create aws_s3_bucket named "b" with set region to "us\\"east"')
    out = compile_source(src)
    data = hcl2.load(io.StringIO(out))
    assert len(data["resource"]) == 2
