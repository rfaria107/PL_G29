import sys
from fortran77.preprocessor import process
from fortran77.statement_classifier import classify_statement
from fortran77.lexer import Lexer


def run_lexer_test(source_code):
    statements, errors = process(source_code)

    if errors:
        for err in errors:
            print(f"ERRO DE PRÉ-PROCESSAMENTO: {err}", file=sys.stderr)
        return

    print("--- Tokens ---")

    for text, line_no, label in statements:
        stmt_type = classify_statement(text)
        lexer = Lexer()
        lexer.set_statement_type(stmt_type)

        # Sincroniza o estado interno do PLY com a linha real do código-fonte
        lexer.lexer.lineno = line_no

        # Restaura o delimitador de instrução destruído pelo pré-processador
        text_with_newline = text + '\n'

        tokens = list(lexer.tokenize(text_with_newline))
        for tok in tokens:
            print(f"Tipo: {tok.type:12} | Valor: {repr(tok.value):15} | Linha: {tok.lineno}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            snippet = f.read()
    else:
        snippet = """C     Exemplo 5: Conversao de base
              PROGRAM CONVERSOR
              INTEGER NUM, BASE, RESULT, CONVRT
              PRINT *, 'INTRODUZA UM NUMERO DECIMAL INTEIRO:'
              READ *, NUM
              DO 10 BASE = 2, 9
                 RESULT = CONVRT(NUM, BASE)
                 PRINT *, 'BASE ', BASE, ': ', RESULT
           10 CONTINUE
              END
              INTEGER FUNCTION CONVRT(N, B)
              INTEGER N, B, QUOT, REM, POT, VAL
              VAL = 0
              POT = 1
              QUOT = N
           20 IF (QUOT .GT. 0) THEN
                 REM = MOD(QUOT, B)
                 VAL = VAL + (REM * POT)
                 QUOT = QUOT / B
                 POT = POT * 10
                 GOTO 20
              ENDIF
              CONVRT = VAL
              RETURN
              END
        """
    run_lexer_test(snippet)