import re
import ply.lex as lex

class Lexer:
    KEYWORDS = {
        'PROGRAM', 'SUBROUTINE', 'FUNCTION', 'END',
        'INTEGER', 'REAL', 'DOUBLE', 'PRECISION', 'COMPLEX', 'LOGICAL', 'CHARACTER',
        'DIMENSION', 'PARAMETER', 'COMMON', 'IMPLICIT', 'NONE',
        'DO', 'CONTINUE', 'IF', 'THEN', 'ELSE', 'ELSEIF', 'ENDIF',
        'GO', 'GOTO', 'CALL', 'RETURN', 'STOP', 'PAUSE',
        'WHILE', 'EXIT', 'CYCLE',
        'READ', 'WRITE', 'PRINT', 'FORMAT',
        'OPEN', 'CLOSE', 'REWIND', 'BACKSPACE', 'ENDFILE',
        'ALLOCATE', 'DEALLOCATE',
        'INTENT', 'IN', 'OUT', 'INOUT', 'OPTIONAL', 'VALUE',
    }

    tokens = (
        'ICON', 'RCON', 'SCON', 'HCON', 'LCON', 'IDENT',
        'PLUS', 'MINUS', 'MULT', 'DIV', 'POW', 'DPSLASH',
        'EQ', 'EQEQ', 'NE', 'LT', 'LE', 'GT', 'GE',
        'LAND', 'LOR', 'LNOT', 'LEQ', 'LNE', 'LLT', 'LLE', 'LGT', 'LGE',
        'LPAREN', 'RPAREN', 'LBRACKET', 'RBRACKET', 'COMMA', 'SEMICOLON',
        'COLON', 'PERCENT', 'AMPERSAND', 'NEWLINE', 'ENDMARKER'
    )

    for keyword in KEYWORDS:
        tokens = tokens + (keyword,)

    def __init__(self, statement_classifier=None):
        self.classifier = statement_classifier
        self.lexer = lex.lex(module=self)
        self.format_depth = 0
        self.in_format = False
        self.current_statement = None
        self.statement_type = None
        self.token_list = []

    def t_LCON(self, t):
        r'\.TRUE\.|\.FALSE\.'
        t.type = 'LCON'
        return t

    def t_HCON(self, t):
        r'\d+H[^\n]*'
        t.type = 'HCON'
        return t

    def t_RCON(self, t):
        r'(\d+\.\d*|\d*\.\d+)([eE][+-]?\d+)?|\d+[eE][+-]?\d+'
        t.type = 'RCON'
        return t

    def t_ICON(self, t):
        r'\d+'
        t.type = 'ICON'
        return t

    def t_SCON(self, t):
        r"'([^'\\\\]|\\\\.)*'|\"([^\"\\\\]|\\\\.)*\""
        t.type = 'SCON'
        return t

    def t_IDENT(self, t):
        r'[a-zA-Z_][a-zA-Z0-9_]*'
        t.type = t.value.upper() if t.value.upper() in self.KEYWORDS else 'IDENT'
        return t

    def t_DPSLASH(self, t):
        r'//'
        t.type = 'DPSLASH'
        return t

    def t_EQEQ(self, t):
        r'=='
        t.type = 'EQEQ'
        return t

    def t_NE(self, t):
        r'/='
        t.type = 'NE'
        return t

    def t_LE(self, t):
        r'<='
        t.type = 'LE'
        return t

    def t_GE(self, t):
        r'>='
        t.type = 'GE'
        return t

    def t_POW(self, t):
        r'\*\*'
        t.type = 'POW'
        return t

    def t_LAND(self, t):
        r'\.AND\.'
        t.type = 'LAND'
        return t

    def t_LOR(self, t):
        r'\.OR\.'
        t.type = 'LOR'
        return t

    def t_LNOT(self, t):
        r'\.NOT\.'
        t.type = 'LNOT'
        return t

    def t_LEQ(self, t):
        r'\.EQ\.'
        t.type = 'LEQ'
        return t

    def t_LNE(self, t):
        r'\.NE\.'
        t.type = 'LNE'
        return t

    def t_LLT(self, t):
        r'\.LT\.'
        t.type = 'LLT'
        return t

    def t_LLE(self, t):
        r'\.LE\.'
        t.type = 'LLE'
        return t

    def t_LGT(self, t):
        r'\.GT\.'
        t.type = 'LGT'
        return t

    def t_LGE(self, t):
        r'\.GE\.'
        t.type = 'LGE'
        return t

    def t_PLUS(self, t):
        r'\+'
        return t

    def t_MINUS(self, t):
        r'-'
        return t

    def t_MULT(self, t):
        r'\*'
        return t

    def t_DIV(self, t):
        r'/'
        return t

    def t_EQ(self, t):
        r'='
        return t

    def t_LT(self, t):
        r'<'
        return t

    def t_GT(self, t):
        r'>'
        return t

    def t_LPAREN(self, t):
        r'\('
        if self.in_format:
            self.format_depth += 1
        return t

    def t_RPAREN(self, t):
        r'\)'
        if self.in_format and self.format_depth > 0:
            self.format_depth -= 1
            if self.format_depth == 0:
                self.in_format = False
        return t

    def t_LBRACKET(self, t):
        r'\['
        return t

    def t_RBRACKET(self, t):
        r'\]'
        return t

    def t_COMMA(self, t):
        r','
        return t

    def t_SEMICOLON(self, t):
        r';'
        return t

    def t_COLON(self, t):
        r':'
        return t

    def t_PERCENT(self, t):
        r'%'
        return t

    def t_AMPERSAND(self, t):
        r'&'
        return t

    def t_NEWLINE(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)
        return t

    t_ignore = ' \t'

    def t_error(self, t):
        print(f"Illegal character '{t.value[0]}' at line {t.lineno}")
        t.lexer.skip(1)

    def tokenize(self, data):
        self.lexer.input(data)
        self.token_list = []

        for tok in self.lexer:
            self.token_list.append(tok)
            yield tok

    def set_statement_type(self, stmt_type):
        self.statement_type = stmt_type

        if stmt_type == 'FORMAT':
            self.in_format = True
            self.format_depth = 0

    def get_tokens(self):
        return self.token_list

    def get_format_depth(self):
        return self.format_depth

    def is_in_format(self):
        return self.in_format