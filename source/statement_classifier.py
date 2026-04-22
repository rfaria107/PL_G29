import re

DO_LOOP_PATTERN = re.compile(
    r'^\s*DO\s+(\d+)?\s*(\w+)\s*=',
    re.IGNORECASE
)

FORMAT_PATTERN = re.compile(
    r'^\s*(\d+)?\s*FORMAT\s*\(',
    re.IGNORECASE
)

ASSIGNMENT_PATTERN = re.compile(
    r'^\s*(\w+)(\s*\([^)]*\))?\s*=\s*',
    re.IGNORECASE
)

STATEMENT_KEYWORDS = {
    'PROGRAM', 'SUBROUTINE', 'FUNCTION', 'END',
    'INTEGER', 'REAL', 'DOUBLE', 'PRECISION', 'COMPLEX', 'LOGICAL', 'CHARACTER',
    'DIMENSION', 'PARAMETER', 'COMMON', 'IMPLICIT',
    'IF', 'THEN', 'ELSE', 'ELSEIF', 'ENDIF',
    'GO', 'GOTO', 'CALL', 'RETURN', 'STOP', 'PAUSE',
    'WHILE', 'EXIT', 'CYCLE',
    'READ', 'WRITE', 'PRINT', 'FORMAT',
    'OPEN', 'CLOSE', 'REWIND', 'BACKSPACE', 'ENDFILE',
    'ALLOCATE', 'DEALLOCATE',
}


def classify_statement(text):
    text = text.strip()

    if DO_LOOP_PATTERN.match(text):
        return 'DO_LOOP'

    if FORMAT_PATTERN.match(text):
        return 'FORMAT'

    if ASSIGNMENT_PATTERN.match(text):
        first_word = text.split()[0].upper()
        if first_word not in STATEMENT_KEYWORDS:
            return 'ASSIGNMENT'

    return 'OTHER'


def classify(statements):
    classifications = {}

    for idx, (text, line_no, label) in enumerate(statements):
        stmt_type = classify_statement(text)
        classifications[idx] = {
            'type': stmt_type,
            'text': text,
            'line': line_no,
            'label': label,
        }

    return classifications