from __future__ import annotations

from collections import deque
from typing import Any, Iterable, Optional

import ply.yacc as yacc
from ply.lex import LexToken

try:
    from .lexer import lexer as base_lexer
    from .lexer import lexer_final
    from .parser import (
        ArrayAccess,
        ArrayDecl,
        Assignment,
        BinOp,
        CallStmt,
        Declaration,
        DoStmt,
        Expr,
        FunctionDecl,
        FunctionCall,
        IfStmt,
        Node,
        ParseError,
        PrintStmt,
        Program,
        ReadStmt,
        Statement,
        SubroutineDecl,
        UnaryOp,
        _CallOrIndex,
        _DoHeader,
        _ElseMarker,
        _EndIfMarker,
        _IfMarker,
        _RawFunctionDecl,
        _RawProgram,
        _RawSubroutineDecl,
        _normalize_label,
        build_parser,
    )
except ImportError:
    from lexer import lexer as base_lexer
    from lexer import lexer_final
    from parser import (
        ArrayAccess,
        ArrayDecl,
        Assignment,
        BinOp,
        CallStmt,
        Declaration,
        DoStmt,
        Expr,
        FunctionDecl,
        FunctionCall,
        IfStmt,
        Node,
        ParseError,
        PrintStmt,
        Program,
        ReadStmt,
        Statement,
        SubroutineDecl,
        UnaryOp,
        _CallOrIndex,
        _DoHeader,
        _ElseMarker,
        _EndIfMarker,
        _IfMarker,
        _RawFunctionDecl,
        _RawProgram,
        _RawSubroutineDecl,
        _normalize_label,
        build_parser,
    )


def _make_token(token_type: str, value: Any, lineno: int, lexpos: int = 0) -> LexToken:
    token = LexToken()
    token.type = token_type
    token.value = value
    token.lineno = lineno
    token.lexpos = lexpos
    return token


class InstructionStreamLexer:
    """
    Adapts the preprocessed instruction list to a parser-friendly token stream.

    The lexer itself is untouched. This adapter only reattaches line labels and
    injects EOL markers so the grammar can stay line-oriented.
    """

    def __init__(self, instructions: list[dict[str, Any]], string_map: Optional[dict[str, str]] = None):
        self.instructions = instructions
        self.string_map = string_map or {}
        self.pending: deque[LexToken] = deque()
        self.index = 0
        self.lineno = 1
        self.lexpos = 0

    def token(self) -> Optional[LexToken]:
        while True:
            if self.pending:
                token = self.pending.popleft()
                self.lineno = token.lineno
                self.lexpos = token.lexpos
                return token

            if self.index >= len(self.instructions):
                return None

            instruction = self.instructions[self.index]
            self.index += 1

            line_no = self.index
            label = _normalize_label(instruction.get("label"))
            code = instruction.get("code", "")

            if label is not None:
                self.pending.append(_make_token("LABEL", label, line_no))

            base_lexer.input(code)
            while True:
                token = base_lexer.token()
                if token is None:
                    break
                token.lineno = line_no
                if token.type == "STRING_MARKER":
                    token.value = self.string_map.get(token.value, token.value)
                self.pending.append(token)

            self.pending.append(_make_token("EOL", None, line_no, len(code)))


class TokenLineStream:
    """
    Accepts logical lines already tokenized by an external driver/lexer.

    Expected shape:
        {
            "label": "10" | None,
            "tokens": [("PRINT", "PRINT"), ("TIMES", "*"), ...]
        }
    """

    def __init__(self, token_lines: list[dict[str, Any]]):
        self.pending: deque[LexToken] = deque()
        self.index = 0
        self.token_lines = token_lines
        self.lineno = 1
        self.lexpos = 0

    def token(self) -> Optional[LexToken]:
        while True:
            if self.pending:
                token = self.pending.popleft()
                self.lineno = token.lineno
                self.lexpos = token.lexpos
                return token

            if self.index >= len(self.token_lines):
                return None

            line = self.token_lines[self.index]
            self.index += 1
            line_no = self.index

            label = _normalize_label(line.get("label"))
            if label is not None:
                self.pending.append(_make_token("LABEL", label, line_no))

            for lexpos, token_info in enumerate(line.get("tokens", []), start=1):
                token_type, token_value = token_info
                self.pending.append(_make_token(token_type, token_value, line_no, lexpos))

            self.pending.append(_make_token("EOL", None, line_no))


def _consume_statement(items: list[Node], index: int) -> tuple[Statement, int]:
    if index >= len(items):
        raise ParseError("Fim de input inesperado ao montar a AST final.")

    item = items[index]

    if isinstance(item, Statement) and not isinstance(item, _DoHeader):
        return item, index + 1

    if isinstance(item, _IfMarker):
        then_body, index, stop_item = _consume_block(items, index + 1, stop_types=(_ElseMarker, _EndIfMarker))

        if stop_item is None:
            raise ParseError(f"IF iniciado na linha lógica {item.line} sem ENDIF correspondente.")

        if isinstance(stop_item, _ElseMarker):
            else_body, index, end_item = _consume_block(items, index + 1, stop_types=(_EndIfMarker,))
            if end_item is None:
                raise ParseError(f"ELSE na linha lógica {stop_item.line} sem ENDIF correspondente.")
            return (
                IfStmt(
                    condition=item.condition,
                    then_body=then_body,
                    else_body=else_body,
                    label=item.label,
                    line=item.line,
                ),
                index + 1,
            )

        return (
            IfStmt(
                condition=item.condition,
                then_body=then_body,
                else_body=[],
                label=item.label,
                line=item.line,
            ),
            index + 1,
        )

    if isinstance(item, _DoHeader):
        body: list[Statement] = []
        cursor = index + 1

        while cursor < len(items):
            statement, cursor = _consume_statement(items, cursor)
            body.append(statement)

            if _normalize_label(statement.label) == item.end_label:
                return (
                    DoStmt(
                        end_label=item.end_label,
                        var=item.var,
                        start=item.start,
                        end=item.end,
                        step=item.step,
                        body=body,
                        label=item.label,
                        line=item.line,
                    ),
                    cursor,
                )

        raise ParseError(
            f"DO com label de fecho {item.end_label} iniciado na linha lógica {item.line} "
            "sem instrução terminal correspondente."
        )

    if isinstance(item, _ElseMarker):
        raise ParseError(f"ELSE inesperado na linha lógica {item.line} sem IF correspondente.")

    if isinstance(item, _EndIfMarker):
        raise ParseError(f"ENDIF inesperado na linha lógica {item.line} sem IF correspondente.")

    raise ParseError(f"Nó intermédio inesperado ao montar a AST: {type(item).__name__}")


def _consume_block(
    items: list[Node],
    index: int,
    stop_types: tuple[type[Node], ...] = (),
) -> tuple[list[Statement], int, Optional[Node]]:
    statements: list[Statement] = []
    cursor = index

    while cursor < len(items):
        item = items[cursor]
        if stop_types and isinstance(item, stop_types):
            return statements, cursor, item

        statement, cursor = _consume_statement(items, cursor)
        statements.append(statement)

    return statements, cursor, None


def _collect_array_names(declarations: Iterable[Declaration]) -> set[str]:
    array_names: set[str] = set()
    for declaration in declarations:
        for item in declaration.items:
            if isinstance(item, ArrayDecl):
                array_names.add(item.name)
    return array_names


def _rewrite_expr(expr: Expr, array_names: set[str]) -> Expr:
    if isinstance(expr, _CallOrIndex):
        args = [_rewrite_expr(arg, array_names) for arg in expr.args]
        if expr.name in array_names:
            return ArrayAccess(name=expr.name, indices=args, line=expr.line)
        return FunctionCall(name=expr.name, args=args, line=expr.line)

    if isinstance(expr, ArrayAccess):
        expr.indices = [_rewrite_expr(index, array_names) for index in expr.indices]
        return expr

    if isinstance(expr, FunctionCall):
        expr.args = [_rewrite_expr(arg, array_names) for arg in expr.args]
        return expr

    if isinstance(expr, BinOp):
        expr.left = _rewrite_expr(expr.left, array_names)
        expr.right = _rewrite_expr(expr.right, array_names)
        return expr

    if isinstance(expr, UnaryOp):
        expr.operand = _rewrite_expr(expr.operand, array_names)
        return expr

    return expr


def _rewrite_statement(stmt: Statement, array_names: set[str]) -> Statement:
    if isinstance(stmt, Assignment):
        stmt.target = _rewrite_expr(stmt.target, array_names)
        stmt.value = _rewrite_expr(stmt.value, array_names)
        return stmt

    if isinstance(stmt, CallStmt):
        stmt.args = [_rewrite_expr(arg, array_names) for arg in stmt.args]
        return stmt

    if isinstance(stmt, ReadStmt):
        stmt.items = [_rewrite_expr(item, array_names) for item in stmt.items]
        return stmt

    if isinstance(stmt, PrintStmt):
        stmt.items = [_rewrite_expr(item, array_names) for item in stmt.items]
        return stmt

    if isinstance(stmt, IfStmt):
        stmt.condition = _rewrite_expr(stmt.condition, array_names)
        stmt.then_body = [_rewrite_statement(item, array_names) for item in stmt.then_body]
        stmt.else_body = [_rewrite_statement(item, array_names) for item in stmt.else_body]
        return stmt

    if isinstance(stmt, DoStmt):
        stmt.start = _rewrite_expr(stmt.start, array_names)
        stmt.end = _rewrite_expr(stmt.end, array_names)
        if stmt.step is not None:
            stmt.step = _rewrite_expr(stmt.step, array_names)
        stmt.body = [_rewrite_statement(item, array_names) for item in stmt.body]
        return stmt

    return stmt


def _finalize_statement_block(
    items: list[Node],
    declarations: list[Declaration],
) -> list[Statement]:
    body, cursor, stop_item = _consume_block(items, 0)

    if stop_item is not None:
        raise ParseError(f"Marcador estrutural inesperado na linha lógica {stop_item.line}.")

    if cursor != len(items):
        raise ParseError("Nem todas as instruções foram consumidas ao montar a AST.")

    array_names = _collect_array_names(declarations)
    return [_rewrite_statement(statement, array_names) for statement in body]


def _finalize_subprogram(raw_subprogram: Node) -> Node:
    if isinstance(raw_subprogram, _RawFunctionDecl):
        declarations = list(raw_subprogram.declarations)
        body = _finalize_statement_block(raw_subprogram.body, declarations)
        return FunctionDecl(
            name=raw_subprogram.name,
            params=list(raw_subprogram.params),
            return_type=raw_subprogram.return_type,
            declarations=declarations,
            body=body,
            line=raw_subprogram.line,
        )

    if isinstance(raw_subprogram, _RawSubroutineDecl):
        declarations = list(raw_subprogram.declarations)
        body = _finalize_statement_block(raw_subprogram.body, declarations)
        return SubroutineDecl(
            name=raw_subprogram.name,
            params=list(raw_subprogram.params),
            declarations=declarations,
            body=body,
            line=raw_subprogram.line,
        )

    raise ParseError(f"Subprograma intermédio inesperado: {type(raw_subprogram).__name__}")


def _finalize_program(raw_program: _RawProgram) -> Program:
    declarations = list(raw_program.declarations)
    rewritten_body = _finalize_statement_block(raw_program.body, declarations)
    subprograms = [_finalize_subprogram(subprogram) for subprogram in raw_program.subprograms]

    return Program(
        name=raw_program.name,
        declarations=declarations,
        body=rewritten_body,
        subprograms=subprograms,
        line=raw_program.line,
    )


def parse_instructions(
    instructions: list[dict[str, Any]],
    string_map: Optional[dict[str, str]] = None,
    parser: Optional[yacc.LRParser] = None,
) -> Program:
    parser_instance = parser or build_parser()
    stream = InstructionStreamLexer(instructions, string_map)
    raw_program = parser_instance.parse(lexer=stream, tracking=True)
    return _finalize_program(raw_program)


def parse_tokens(
    token_lines: list[dict[str, Any]],
    parser: Optional[yacc.LRParser] = None,
) -> Program:
    parser_instance = parser or build_parser()
    stream = TokenLineStream(token_lines)
    raw_program = parser_instance.parse(lexer=stream, tracking=True)
    return _finalize_program(raw_program)


def parse_source(source_text: str, parser: Optional[yacc.LRParser] = None) -> Program:
    instructions, string_map = lexer_final(source_text)
    return parse_instructions(instructions, string_map, parser=parser)
