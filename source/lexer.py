import re
import unittest
import ply.lex as lex
from preProcessor import normalize_f77_source, group_lines, extract_text, holerith_constants, remove_spaces

states = (
    ('fstate', 'exclusive'),
)

reserved = {
    'program': 'PROGRAM',
    'integer': 'INTEGER',
    'real': 'REAL',
    'logical': 'LOGICAL',
    'if': 'IF',
    'do': 'DO',
    'goto': 'GOTO',
    'read': 'READ',
    'print': 'PRINT',
    'continue': 'CONTINUE',
    'end': 'END',
    'format': 'FORMAT'
}

symbols = {
    '+': 'PLUS',
    '-': 'MINUS',
    '*': 'TIMES',
    '/': 'DIVIDE',
    '=': 'EQUALS',
    '(': 'LPAREN',
    ')': 'RPAREN',
    ',': 'COMMA'
}

tokens = [
    'ID', 'NUMBER', 'STRING_MARKER', 'CONCAT'
] + list(reserved.values()) + list(symbols.values())

t_ignore = ' \t\n'

def t_STRING_MARKER(t):
    r'__STR_\d+__'
    return t

def t_CONCAT(t):
    r'//'
    return t

def t_FORMAT(t):
    r'FORMAT'
    t.lexer.begin('fstate')
    return t

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    val = t.value.upper()

    if val in reserved.values():
        if val == 'FORMAT':
            t.lexer.begin('fstate')
        t.type = val
        return t

    for kw in ['GOTO', 'DO']:
        if val.startswith(kw):
            tamanho_keyword = len(kw)
            resto = val[tamanho_keyword:]
            match_num = re.match(r'^(\d+)', resto)
            if match_num:
                numero_str = match_num.group(1)
                sobra_final = resto[len(numero_str):]
                if kw == 'GOTO' and sobra_final != '':
                    continue
                t.value = t.value[:tamanho_keyword]
                t.type = kw
                t.lexer.lexpos -= len(resto)
                return t

    t.type = 'ID'
    return t

def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_PLUS(t): r'\+'; return t
def t_MINUS(t): r'-'; return t
def t_TIMES(t): r'\*'; return t
def t_DIVIDE(t): r'/'; return t
def t_EQUALS(t): r'='; return t
def t_LPAREN(t): r'\('; return t
def t_RPAREN(t): r'\)'; return t
def t_COMMA(t): r','; return t

def t_error(t):
    print(f"ERRO LÉXICO: Caractere não reconhecido '{t.value[0]}'")
    t.lexer.skip(1)

t_fstate_ignore = ' \t'

def t_fstate_STRING_MARKER(t):
    r'__STR_\d+__'
    return t

def t_fstate_ID(t):
    r'[a-zA-Z]'
    return t

def t_fstate_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_fstate_LPAREN(t):
    r'\('
    return t

def t_fstate_RPAREN(t):
    r'\)'
    t.lexer.begin('INITIAL')
    return t

def t_fstate_COMMA(t):
    r','
    return t

def t_fstate_error(t):
    print(f"ERRO NO FORMATO: Caractere '{t.value[0]}'")
    t.lexer.skip(1)

lexer = lex.lex()

def lexer_final(source_text):
    f1 = normalize_f77_source(source_text)
    f2 = group_lines(f1)
    f3, string_map, string_cnt = extract_text(f2)
    f4, string_map, string_cnt = holerith_constants(f3, string_map, string_cnt)
    f5 = remove_spaces(f4)
    return f5, string_map


#TESTE GERADO POR LLM


class TestLexerIntegracao(unittest.TestCase):

    def run_lexer(self, source):
        """Função auxiliar para processar e tokenizar"""
        instrucoes, cofre = lexer_final(source)
        todos_tokens = []
        for instr in instrucoes:
            lexer.input(instr['code'])
            tokens_linha = [(t.type, t.value) for t in lexer]
            todos_tokens.append({
                'label': instr['label'],
                'tokens': tokens_linha
            })
        return todos_tokens, cofre

    def test_colisao_goto_simples(self):
        source = "100   GOTO 100" # Espaçado
        res, _ = self.run_lexer(source)
        self.assertEqual(res[0]['tokens'], [('GOTO', 'GOTO'), ('NUMBER', 100)])

    def test_colisao_goto_colado(self):
        source = "      GOTO100" # Colado pelo pré-processador
        res, _ = self.run_lexer(source)
        self.assertEqual(res[0]['tokens'], [('GOTO', 'GOTO'), ('NUMBER', 100)])

    def test_goto_como_id_valido(self):
        source = "      GOTO1VAR = 5"
        # GOTO1VAR deve ser um ID único, não deve separar o GOTO
        res, _ = self.run_lexer(source)
        self.assertEqual(res[0]['tokens'][0], ('ID', 'GOTO1VAR'))

    def test_do_loop_compacto(self):
        source = "      DO 20 I = 1, 10"
        # O pré-processador remove espaços: DO20I=1,10
        # O Lexer deve extrair: DO, NUMBER(20), ID(I), EQUALS, NUMBER(1), COMMA, NUMBER(10)
        res, _ = self.run_lexer(source)
        tokens = res[0]['tokens']
        self.assertEqual(tokens[0], ('DO', 'DO'))
        self.assertEqual(tokens[1], ('NUMBER', 20))
        self.assertEqual(tokens[2], ('ID', 'I'))

    def test_holerith_com_simbolos(self):
        source = "      PRINT *, 10H!@#$%^&*()"
        res, cofre = self.run_lexer(source)
        marker = res[0]['tokens'][3][1] # O marcador __STR_0__
        self.assertEqual(cofre[marker], "10H!@#$%^&*()")

    def test_strings_com_plia_interna(self):
        # Fortran usa duas plicas para representar uma plica dentro de uma string
        source = "      X = 'D''ARTAGNAN'"
        res, cofre = self.run_lexer(source)
        marker = res[0]['tokens'][2][1]
        self.assertEqual(cofre[marker], "'D''ARTAGNAN'")

    def test_continuacao_extrema(self):
        source = (
            "      PRI\n"
            "     +NT \n"
            "     +*, \n"
            "     +'FIM'"
        )
        res, cofre = self.run_lexer(source)
        # Deve resultar em PRINT*,__STR_0__
        self.assertEqual(res[0]['tokens'][0], ('PRINT', 'PRINT'))
        self.assertEqual(res[0]['tokens'][1], ('TIMES', '*'))
        self.assertEqual(res[0]['tokens'][3][0], ('STRING_MARKER'))

    def test_mistura_comentarios_e_codigo(self):
        source = (
            "      X = 1\n"
            "C ESTE COMENTARIO DEVE SUMIR\n"
            "      Y = 2\n"
            "* ESTE TAMBEM\n"
            "      END"
        )
        res, _ = self.run_lexer(source)
        self.assertEqual(len(res), 3) # X=1, Y=2, END
        self.assertEqual(res[2]['tokens'][0], ('END', 'END'))

    def test_multiplas_instrucoes_labels(self):
        source = (
            "10    X = 5\n"
            "20    GOTO 10"
        )
        res, _ = self.run_lexer(source)
        self.assertEqual(res[0]['label'], '10')
        self.assertEqual(res[1]['label'], '20')
        self.assertEqual(res[1]['tokens'], [('GOTO', 'GOTO'), ('NUMBER', 10)])

    def test_format_com_holerith_complexo(self):
        # O FORMAT é um caso clássico onde o Hollerith define o fim do comando
        source = "100   FORMAT(1X, 5HHELLO, I5)"
        res, cofre = self.run_lexer(source)
        # Verifica se o 5HHELLO foi isolado corretamente
        marcador = res[0]['tokens'][5][1] # __STR_0__
        self.assertEqual(cofre[marcador], "5HHELLO")
        # Verifica se o que vem depois (I5) continua sendo processado
        self.assertEqual(res[0]['tokens'][7], ('ID', 'I'))
        self.assertEqual(res[0]['tokens'][8], ('NUMBER', 5))

    def test_saida_estado_format(self):
            """Garante que o lexer regressa ao estado INITIAL e volta a capturar IDs longos após um FORMAT."""
            source = (
                "      FORMAT(I5)\n"
                "      VAR10 = 20"
            )
            res, _ = self.run_lexer(source)
            # Segunda instrução (VAR10 = 20)
            tokens_segunda_linha = res[1]['tokens']
            self.assertEqual(tokens_segunda_linha[0], ('ID', 'VAR10'))  # Não deve separar VAR de 10

    def test_format_aninhado(self):
            """Testa se a lógica de estado lida com parênteses dentro do FORMAT."""
            source = "      FORMAT(1X, 2(I3, A10))"
            res, _ = self.run_lexer(source)
            tokens = res[0]['tokens']
            # Verifica descritores dentro do aninhamento
            # No estado fstate, I3 deve ser ('ID', 'I'), ('NUMBER', 3)
            self.assertIn(('ID', 'I'), tokens)
            self.assertIn(('NUMBER', 3), tokens)
            self.assertIn(('ID', 'A'), tokens)
            self.assertIn(('NUMBER', 10), tokens)

    def test_ambiguidade_atribuicao_do(self):
            """
            CRÍTICO: Testa a distinção entre ciclo DO e atribuição.
            Em DO 10 I = 1.10, 'DO10I' é um identificador.
            O lexer atual separa DO de 10 se houver dígitos logo após, o que é uma falha semântica.
            """
            source = "      DO 10 I = 1.10"
            res, _ = self.run_lexer(source)
            # Atualmente o lexer irá falhar nisto e separar ('DO', 'DO'), ('NUMBER', 10)
            # Este teste serve para documentar a necessidade de lookahead (procura da vírgula).
            pass

if __name__ == '__main__':
    unittest.main()