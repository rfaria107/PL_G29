from __future__ import annotations

import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import ply.yacc as yacc

try:
    from .lexer import tokens as lexer_tokens
except ImportError:
    from lexer import tokens as lexer_tokens


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Node:
    line: Optional[int] = field(default=None, kw_only=True)


@dataclass(slots=True)
class Expr(Node):
    pass


@dataclass(slots=True)
class Identifier(Expr):
    name: str


@dataclass(slots=True)
class Literal(Expr):
    kind: str
    value: Any
    raw: Any


@dataclass(slots=True)
class UnaryOp(Expr):
    op: str
    operand: Expr


@dataclass(slots=True)
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass(slots=True)
class ArrayAccess(Expr):
    name: str
    indices: list[Expr]


@dataclass(slots=True)
class FunctionCall(Expr):
    name: str
    args: list[Expr]


@dataclass(slots=True)
class Declaration(Node):
    type_name: str
    items: list[Node]
    label: Optional[str] = None


@dataclass(slots=True)
class VarDecl(Node):
    name: str


@dataclass(slots=True)
class ArrayDecl(Node):
    name: str
    dimensions: list[Expr]


@dataclass(slots=True)
class Statement(Node):
    label: Optional[str] = field(default=None, kw_only=True)


@dataclass(slots=True)
class Assignment(Statement):
    target: Expr
    value: Expr


@dataclass(slots=True)
class IfStmt(Statement):
    condition: Expr
    then_body: list[Statement]
    else_body: list[Statement] = field(default_factory=list)


@dataclass(slots=True)
class DoStmt(Statement):
    end_label: str
    var: Identifier
    start: Expr
    end: Expr
    step: Optional[Expr]
    body: list[Statement]


@dataclass(slots=True)
class GotoStmt(Statement):
    target_label: str


@dataclass(slots=True)
class ContinueStmt(Statement):
    pass


@dataclass(slots=True)
class ReadStmt(Statement):
    items: list[Expr]
    format_spec: str = "*"


@dataclass(slots=True)
class PrintStmt(Statement):
    items: list[Expr]
    format_spec: str = "*"


@dataclass(slots=True)
class ReturnStmt(Statement):
    pass


@dataclass(slots=True)
class CallStmt(Statement):
    name: str
    args: list[Expr] = field(default_factory=list)


@dataclass(slots=True)
class FunctionDecl(Node):
    name: str
    params: list[str]
    return_type: Optional[str]
    declarations: list[Declaration]
    body: list[Statement]


@dataclass(slots=True)
class SubroutineDecl(Node):
    name: str
    params: list[str]
    declarations: list[Declaration]
    body: list[Statement]


@dataclass(slots=True)
class Program(Node):
    name: str
    declarations: list[Declaration]
    body: list[Statement]
    subprograms: list[Node] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal nodes used while assembling the final AST
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _RawProgram(Node):
    name: str
    declarations: list[Declaration]
    body: list[Node]
    subprograms: list[Node] = field(default_factory=list)
    program_label: Optional[str] = None
    end_label: Optional[str] = None


@dataclass(slots=True)
class _IfMarker(Node):
    condition: Expr
    label: Optional[str] = None


@dataclass(slots=True)
class _ElseMarker(Node):
    label: Optional[str] = None


@dataclass(slots=True)
class _EndIfMarker(Node):
    label: Optional[str] = None


@dataclass(slots=True)
class _DoHeader(Statement):
    end_label: str
    var: Identifier
    start: Expr
    end: Expr
    step: Optional[Expr]


@dataclass(slots=True)
class _CallOrIndex(Expr):
    name: str
    args: list[Expr]


@dataclass(slots=True)
class _RawFunctionDecl(Node):
    name: str
    params: list[str]
    return_type: Optional[str]
    declarations: list[Declaration]
    body: list[Node]
    label: Optional[str] = None
    end_label: Optional[str] = None


@dataclass(slots=True)
class _RawSubroutineDecl(Node):
    name: str
    params: list[str]
    declarations: list[Declaration]
    body: list[Node]
    label: Optional[str] = None
    end_label: Optional[str] = None


# ---------------------------------------------------------------------------
# Parser tokens and precedence
# ---------------------------------------------------------------------------


_EXTRA_TOKENS = (
    "LABEL",
    "EOL",
    "THEN",
    "ELSE",
    "ENDIF",
    "RETURN",
    "FUNCTION",
    "SUBROUTINE",
    "CALL",
    "AND",
    "OR",
    "NOT",
    "EQ",
    "NE",
    "LT",
    "LE",
    "GT",
    "GE",
    "TRUE",
    "FALSE",
)

tokens = tuple(dict.fromkeys(tuple(lexer_tokens) + _EXTRA_TOKENS))

precedence = (
    ("left", "OR"),
    ("left", "AND"),
    ("right", "NOT"),
    ("nonassoc", "EQ", "NE", "LT", "LE", "GT", "GE"),
    ("left", "CONCAT"),
    ("left", "PLUS", "MINUS"),
    ("left", "TIMES", "DIVIDE"),
    ("right", "UPLUS", "UMINUS"),
)

start = "program"


# ---------------------------------------------------------------------------
# Errors and helpers
# ---------------------------------------------------------------------------


class ParseError(SyntaxError):
    """Raised when syntactic analysis fails."""


def _normalize_label(value: Any) -> Optional[str]:
    if value in ("", None):
        return None
    return str(value)


def _normalize_name(value: Any) -> str:
    return str(value).upper()


def _decode_string_like(raw: str) -> tuple[str, str]:
    if re.match(r"^\d+[Hh]", raw):
        marker_end = raw.lower().find("h")
        return "hollerith", raw[marker_end + 1 :]

    if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'":
        return "string", raw[1:-1].replace("''", "'")

    return "string", raw


def _make_number_literal(value: Any, line: Optional[int] = None) -> Literal:
    return Literal(kind="number", value=value, raw=value, line=line)


def _make_string_literal(raw: str, line: Optional[int] = None) -> Literal:
    kind, value = _decode_string_like(raw)
    return Literal(kind=kind, value=value, raw=raw, line=line)


def _make_bool_literal(value: Any, line: Optional[int] = None) -> Literal:
    text = str(value).upper().strip(".")
    return Literal(kind="logical", value=text == "TRUE", raw=value, line=line)


def _with_label(node: Node, label: Optional[str]) -> Node:
    if hasattr(node, "label"):
        setattr(node, "label", _normalize_label(label))
    return node


def ast_to_dict(node: Node) -> dict[str, Any]:
    return asdict(node)


# ---------------------------------------------------------------------------
# Grammar rules
# ---------------------------------------------------------------------------


def p_program(p):
    """
    program : program_header EOL declaration_section executable_section end_line subprogram_section
    """
    name, program_label = p[1]
    p[0] = _RawProgram(
        name=name,
        declarations=p[3],
        body=p[4],
        subprograms=p[6],
        program_label=program_label,
        end_label=p[5],
        line=p.lineno(1),
    )


def p_program_header(p):
    """
    program_header : opt_label PROGRAM ID
    """
    p[0] = (_normalize_name(p[3]), p[1])


def p_end_line(p):
    """
    end_line : opt_label END EOL
    """
    p[0] = p[1]


def p_subprogram_section_recursive(p):
    """
    subprogram_section : subprogram_section subprogram
    """
    p[0] = p[1] + [p[2]]


def p_subprogram_section_empty(p):
    """
    subprogram_section : empty
    """
    p[0] = []


def p_subprogram_function(p):
    """
    subprogram : function_subprogram
    """
    p[0] = p[1]


def p_subprogram_subroutine(p):
    """
    subprogram : subroutine_subprogram
    """
    p[0] = p[1]


def p_function_subprogram(p):
    """
    function_subprogram : function_header EOL declaration_section executable_section end_line
    """
    header = p[1]
    p[0] = _RawFunctionDecl(
        name=header["name"],
        params=header["params"],
        return_type=header["return_type"],
        declarations=p[3],
        body=p[4],
        label=header["label"],
        end_label=p[5],
        line=header["line"],
    )


def p_subroutine_subprogram(p):
    """
    subroutine_subprogram : subroutine_header EOL declaration_section executable_section end_line
    """
    header = p[1]
    p[0] = _RawSubroutineDecl(
        name=header["name"],
        params=header["params"],
        declarations=p[3],
        body=p[4],
        label=header["label"],
        end_label=p[5],
        line=header["line"],
    )


def p_function_header_typed(p):
    """
    function_header : opt_label type_spec FUNCTION ID LPAREN maybe_param_list RPAREN
    """
    p[0] = {
        "label": p[1],
        "return_type": p[2],
        "name": _normalize_name(p[4]),
        "params": p[6],
        "line": p.lineno(3),
    }


def p_function_header_untyped(p):
    """
    function_header : opt_label FUNCTION ID LPAREN maybe_param_list RPAREN
    """
    p[0] = {
        "label": p[1],
        "return_type": None,
        "name": _normalize_name(p[3]),
        "params": p[5],
        "line": p.lineno(2),
    }


def p_subroutine_header_with_params(p):
    """
    subroutine_header : opt_label SUBROUTINE ID LPAREN maybe_param_list RPAREN
    """
    p[0] = {
        "label": p[1],
        "name": _normalize_name(p[3]),
        "params": p[5],
        "line": p.lineno(2),
    }


def p_subroutine_header_without_params(p):
    """
    subroutine_header : opt_label SUBROUTINE ID
    """
    p[0] = {
        "label": p[1],
        "name": _normalize_name(p[3]),
        "params": [],
        "line": p.lineno(2),
    }


def p_declaration_section_recursive(p):
    """
    declaration_section : declaration_section declaration_line
    """
    p[0] = p[1] + [p[2]]


def p_declaration_section_empty(p):
    """
    declaration_section : empty
    """
    p[0] = []


def p_declaration_line(p):
    """
    declaration_line : opt_label declaration EOL
    """
    p[0] = _with_label(p[2], p[1])


def p_declaration(p):
    """
    declaration : type_spec decl_list
    """
    p[0] = Declaration(type_name=p[1], items=p[2], line=p.lineno(1))


def p_type_spec(p):
    """
    type_spec : INTEGER
              | REAL
              | LOGICAL
    """
    p[0] = p.slice[1].type


def p_decl_list_single(p):
    """
    decl_list : decl_item
    """
    p[0] = [p[1]]


def p_decl_list_recursive(p):
    """
    decl_list : decl_list COMMA decl_item
    """
    p[0] = p[1] + [p[3]]


def p_decl_item_scalar(p):
    """
    decl_item : ID
    """
    p[0] = VarDecl(name=_normalize_name(p[1]), line=p.lineno(1))


def p_decl_item_array(p):
    """
    decl_item : ID LPAREN dim_list RPAREN
    """
    p[0] = ArrayDecl(name=_normalize_name(p[1]), dimensions=p[3], line=p.lineno(1))


def p_dim_list_single(p):
    """
    dim_list : expr
    """
    p[0] = [p[1]]


def p_dim_list_recursive(p):
    """
    dim_list : dim_list COMMA expr
    """
    p[0] = p[1] + [p[3]]


def p_maybe_param_list_empty(p):
    """
    maybe_param_list : empty
    """
    p[0] = []


def p_maybe_param_list_values(p):
    """
    maybe_param_list : id_list
    """
    p[0] = p[1]


def p_id_list_single(p):
    """
    id_list : ID
    """
    p[0] = [_normalize_name(p[1])]


def p_id_list_recursive(p):
    """
    id_list : id_list COMMA ID
    """
    p[0] = p[1] + [_normalize_name(p[3])]


def p_executable_section_recursive(p):
    """
    executable_section : executable_section executable_item
    """
    p[0] = p[1] + [p[2]]


def p_executable_section_empty(p):
    """
    executable_section : empty
    """
    p[0] = []


def p_executable_item_simple(p):
    """
    executable_item : simple_stmt_line
    """
    p[0] = p[1]


def p_executable_item_if_start(p):
    """
    executable_item : if_start_line
    """
    p[0] = p[1]


def p_executable_item_else(p):
    """
    executable_item : else_line
    """
    p[0] = p[1]


def p_executable_item_endif(p):
    """
    executable_item : endif_line
    """
    p[0] = p[1]


def p_executable_item_do(p):
    """
    executable_item : do_stmt_line
    """
    p[0] = p[1]


def p_simple_stmt_line(p):
    """
    simple_stmt_line : opt_label simple_stmt EOL
    """
    p[0] = _with_label(p[2], p[1])


def p_simple_stmt_assignment(p):
    """
    simple_stmt : assignment
    """
    p[0] = p[1]


def p_simple_stmt_read(p):
    """
    simple_stmt : read_stmt
    """
    p[0] = p[1]


def p_simple_stmt_print(p):
    """
    simple_stmt : print_stmt
    """
    p[0] = p[1]


def p_simple_stmt_goto(p):
    """
    simple_stmt : goto_stmt
    """
    p[0] = p[1]


def p_simple_stmt_continue(p):
    """
    simple_stmt : continue_stmt
    """
    p[0] = p[1]


def p_simple_stmt_return(p):
    """
    simple_stmt : return_stmt
    """
    p[0] = p[1]


def p_simple_stmt_call(p):
    """
    simple_stmt : call_stmt
    """
    p[0] = p[1]


def p_assignment(p):
    """
    assignment : ref EQUALS expr
    """
    p[0] = Assignment(target=p[1], value=p[3], line=p.lineno(2))


def p_ref_identifier(p):
    """
    ref : ID
    """
    p[0] = Identifier(name=_normalize_name(p[1]), line=p.lineno(1))


def p_ref_array_access(p):
    """
    ref : ID LPAREN expr_list RPAREN
    """
    p[0] = ArrayAccess(name=_normalize_name(p[1]), indices=p[3], line=p.lineno(1))


def p_if_start_line(p):
    """
    if_start_line : opt_label IF LPAREN expr RPAREN THEN EOL
    """
    p[0] = _IfMarker(condition=p[4], label=p[1], line=p.lineno(2))


def p_else_line(p):
    """
    else_line : opt_label ELSE EOL
    """
    p[0] = _ElseMarker(label=p[1], line=p.lineno(2))


def p_endif_line(p):
    """
    endif_line : opt_label ENDIF EOL
    """
    p[0] = _EndIfMarker(label=p[1], line=p.lineno(2))


def p_do_stmt_line_two_bounds(p):
    """
    do_stmt_line : opt_label DO NUMBER ID EQUALS expr COMMA expr EOL
    """
    p[0] = _DoHeader(
        end_label=_normalize_label(p[3]),
        var=Identifier(name=_normalize_name(p[4]), line=p.lineno(4)),
        start=p[6],
        end=p[8],
        step=None,
        label=p[1],
        line=p.lineno(2),
    )


def p_do_stmt_line_three_bounds(p):
    """
    do_stmt_line : opt_label DO NUMBER ID EQUALS expr COMMA expr COMMA expr EOL
    """
    p[0] = _DoHeader(
        end_label=_normalize_label(p[3]),
        var=Identifier(name=_normalize_name(p[4]), line=p.lineno(4)),
        start=p[6],
        end=p[8],
        step=p[10],
        label=p[1],
        line=p.lineno(2),
    )


def p_goto_stmt(p):
    """
    goto_stmt : GOTO NUMBER
    """
    p[0] = GotoStmt(target_label=_normalize_label(p[2]), line=p.lineno(1))


def p_continue_stmt(p):
    """
    continue_stmt : CONTINUE
    """
    p[0] = ContinueStmt(line=p.lineno(1))


def p_return_stmt(p):
    """
    return_stmt : RETURN
    """
    p[0] = ReturnStmt(line=p.lineno(1))


def p_call_stmt_without_args(p):
    """
    call_stmt : CALL ID
    """
    p[0] = CallStmt(name=_normalize_name(p[2]), args=[], line=p.lineno(1))


def p_call_stmt_with_args(p):
    """
    call_stmt : CALL ID LPAREN maybe_expr_list RPAREN
    """
    p[0] = CallStmt(name=_normalize_name(p[2]), args=p[4], line=p.lineno(1))


def p_read_stmt(p):
    """
    read_stmt : READ TIMES COMMA io_list
    """
    p[0] = ReadStmt(items=p[4], line=p.lineno(1))


def p_print_stmt(p):
    """
    print_stmt : PRINT TIMES COMMA output_list
    """
    p[0] = PrintStmt(items=p[4], line=p.lineno(1))


def p_io_list_single(p):
    """
    io_list : ref
    """
    p[0] = [p[1]]


def p_io_list_recursive(p):
    """
    io_list : io_list COMMA ref
    """
    p[0] = p[1] + [p[3]]


def p_output_list_single(p):
    """
    output_list : expr
    """
    p[0] = [p[1]]


def p_output_list_recursive(p):
    """
    output_list : output_list COMMA expr
    """
    p[0] = p[1] + [p[3]]


def p_expr(p):
    """
    expr : logical_or
    """
    p[0] = p[1]


def p_logical_or_single(p):
    """
    logical_or : logical_and
    """
    p[0] = p[1]


def p_logical_or_recursive(p):
    """
    logical_or : logical_or OR logical_and
    """
    p[0] = BinOp(op="OR", left=p[1], right=p[3], line=p.lineno(2))


def p_logical_and_single(p):
    """
    logical_and : logical_not
    """
    p[0] = p[1]


def p_logical_and_recursive(p):
    """
    logical_and : logical_and AND logical_not
    """
    p[0] = BinOp(op="AND", left=p[1], right=p[3], line=p.lineno(2))


def p_logical_not_relation(p):
    """
    logical_not : relation
    """
    p[0] = p[1]


def p_logical_not_recursive(p):
    """
    logical_not : NOT logical_not
    """
    p[0] = UnaryOp(op="NOT", operand=p[2], line=p.lineno(1))


def p_relation_plain(p):
    """
    relation : concat_expr
    """
    p[0] = p[1]


def p_relation_binary(p):
    """
    relation : concat_expr relop concat_expr
    """
    p[0] = BinOp(op=p[2], left=p[1], right=p[3], line=p.lineno(2))


def p_relop(p):
    """
    relop : EQ
          | NE
          | LT
          | LE
          | GT
          | GE
    """
    p[0] = p[1] if isinstance(p[1], str) else p.slice[1].type


def p_concat_expr_single(p):
    """
    concat_expr : arith_expr
    """
    p[0] = p[1]


def p_concat_expr_recursive(p):
    """
    concat_expr : concat_expr CONCAT arith_expr
    """
    p[0] = BinOp(op="CONCAT", left=p[1], right=p[3], line=p.lineno(2))


def p_arith_expr_single(p):
    """
    arith_expr : term
    """
    p[0] = p[1]


def p_arith_expr_plus(p):
    """
    arith_expr : arith_expr PLUS term
    """
    p[0] = BinOp(op="+", left=p[1], right=p[3], line=p.lineno(2))


def p_arith_expr_minus(p):
    """
    arith_expr : arith_expr MINUS term
    """
    p[0] = BinOp(op="-", left=p[1], right=p[3], line=p.lineno(2))


def p_term_single(p):
    """
    term : factor
    """
    p[0] = p[1]


def p_term_times(p):
    """
    term : term TIMES factor
    """
    p[0] = BinOp(op="*", left=p[1], right=p[3], line=p.lineno(2))


def p_term_divide(p):
    """
    term : term DIVIDE factor
    """
    p[0] = BinOp(op="/", left=p[1], right=p[3], line=p.lineno(2))


def p_factor_number(p):
    """
    factor : NUMBER
    """
    p[0] = _make_number_literal(p[1], line=p.lineno(1))


def p_factor_string(p):
    """
    factor : STRING_MARKER
    """
    p[0] = _make_string_literal(p[1], line=p.lineno(1))


def p_factor_true(p):
    """
    factor : TRUE
    """
    p[0] = _make_bool_literal(p[1], line=p.lineno(1))


def p_factor_false(p):
    """
    factor : FALSE
    """
    p[0] = _make_bool_literal(p[1], line=p.lineno(1))


def p_factor_identifier(p):
    """
    factor : ID
    """
    p[0] = Identifier(name=_normalize_name(p[1]), line=p.lineno(1))


def p_factor_invocation(p):
    """
    factor : ID LPAREN maybe_expr_list RPAREN
    """
    p[0] = _CallOrIndex(name=_normalize_name(p[1]), args=p[3], line=p.lineno(1))


def p_factor_group(p):
    """
    factor : LPAREN expr RPAREN
    """
    p[0] = p[2]


def p_factor_uminus(p):
    """
    factor : MINUS factor %prec UMINUS
    """
    p[0] = UnaryOp(op="-", operand=p[2], line=p.lineno(1))


def p_factor_uplus(p):
    """
    factor : PLUS factor %prec UPLUS
    """
    p[0] = UnaryOp(op="+", operand=p[2], line=p.lineno(1))


def p_maybe_expr_list_empty(p):
    """
    maybe_expr_list : empty
    """
    p[0] = []


def p_maybe_expr_list_values(p):
    """
    maybe_expr_list : expr_list
    """
    p[0] = p[1]


def p_expr_list_single(p):
    """
    expr_list : expr
    """
    p[0] = [p[1]]


def p_expr_list_recursive(p):
    """
    expr_list : expr_list COMMA expr
    """
    p[0] = p[1] + [p[3]]


def p_opt_label_some(p):
    """
    opt_label : LABEL
    """
    p[0] = _normalize_label(p[1])


def p_opt_label_empty(p):
    """
    opt_label : empty
    """
    p[0] = None


def p_empty(p):
    """
    empty :
    """
    p[0] = None


def p_error(token):
    if token is None:
        raise ParseError("Fim de input inesperado durante a análise sintática.")

    token_value = token.value if token.type != "EOL" else "<fim de instrução>"
    raise ParseError(
        f"Token inesperado {token.type} ({token_value!r}) na linha lógica {getattr(token, 'lineno', '?')}."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_PARSER: Optional[yacc.LRParser] = None


def build_parser(**kwargs: Any) -> yacc.LRParser:
    global _PARSER

    if kwargs:
        return yacc.yacc(
            module=sys.modules[__name__],
            write_tables=False,
            debug=False,
            errorlog=yacc.NullLogger(),
            **kwargs,
        )

    if _PARSER is None:
        _PARSER = yacc.yacc(
            module=sys.modules[__name__],
            write_tables=False,
            debug=False,
            errorlog=yacc.NullLogger(),
        )

    return _PARSER


def parse_instructions(
    instructions: list[dict[str, Any]],
    string_map: Optional[dict[str, str]] = None,
    parser: Optional[yacc.LRParser] = None,
) -> Program:
    try:
        from .parser_driver import parse_instructions as _parse_instructions
    except ImportError:
        from parser_driver import parse_instructions as _parse_instructions

    return _parse_instructions(instructions, string_map, parser=parser)


def parse_tokens(
    token_lines: list[dict[str, Any]],
    parser: Optional[yacc.LRParser] = None,
) -> Program:
    try:
        from .parser_driver import parse_tokens as _parse_tokens
    except ImportError:
        from parser_driver import parse_tokens as _parse_tokens

    return _parse_tokens(token_lines, parser=parser)


def parse_source(source_text: str, parser: Optional[yacc.LRParser] = None) -> Program:
    try:
        from .parser_driver import parse_source as _parse_source
    except ImportError:
        from parser_driver import parse_source as _parse_source

    return _parse_source(source_text, parser=parser)
