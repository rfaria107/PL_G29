import re


def _parse_line(line):
    line = line.ljust(72)

    is_comment = line[0] in ('C', 'c', '*', '!')
    is_continuation = line[5] not in (' ', '')

    label_str = line[0:5].strip()
    label = int(label_str) if label_str and not is_comment else None

    statement_text = line[6:72].rstrip()

    return label, is_comment, is_continuation, statement_text


def process(source_code):
    statements = []
    errors = []

    lines = source_code.split('\n')
    current_statement = []
    current_label = None
    current_line_no = 0

    for line_no, line in enumerate(lines, start=1):
        label, is_comment, is_continuation, statement_text = _parse_line(line)

        if is_comment:
            continue

        if not is_continuation:
            if current_statement:
                full_stmt = ' '.join(current_statement).strip()
                if full_stmt:
                    statements.append((full_stmt, current_line_no, current_label))

            current_statement = [statement_text] if statement_text else []
            current_label = label
            current_line_no = line_no
        else:
            if not current_statement:
                errors.append(f"Line {line_no}: continuation without initial statement")
            else:
                current_statement.append(statement_text)

    if current_statement:
        full_stmt = ' '.join(current_statement).strip()
        if full_stmt:
            statements.append((full_stmt, current_line_no, current_label))

    return statements, errors


def format_for_lexer(statements):
    return '\n'.join(stmt[0] for stmt in statements)


def simple_preprocess(source_code):
    lines = []
    for line in source_code.split('\n'):
        if line.strip().startswith('!') or line.strip().startswith('C'):
            continue
        lines.append(line)

    return '\n'.join(lines)