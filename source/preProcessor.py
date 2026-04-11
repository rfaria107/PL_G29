import re
import unittest

def normalize_f77_source(source_code):
    processed_lines = []
    lines = source_code.splitlines()

    for line in lines:
        if not line.strip():
            continue

        if line[0] in ('C', 'c', '*'):
            continue

        padded_line = line.ljust(72, ' ')
        truncated_line = padded_line[:72]

        processed_lines.append(truncated_line)

    return processed_lines


def group_lines(source):
    processed_lines = []
    current_block = None

    for i, line in enumerate(source):
        column_6 = line[5]
        if column_6 in (' ', '0'):
            if current_block is not None:
                processed_lines.append(current_block)

            label = line[0:5].replace(' ', '')
            code = line[6:72]

            current_block = {
                'label': label,
                'code': code
            }

        else:
            if current_block is None:
                raise SyntaxError(f"Erro de Sintaxe (linha {i}): Continuação sem instrução prévia.")

            extra_code = line[6:72]
            current_block['code'] += extra_code

    if current_block is not None:
        processed_lines.append(current_block)

    return processed_lines

def extract_text (processed_lines):
    lietrals = r"'(?:''|[^'])*'"
    string_map = {}
    string_cnt = 0

    def substitute(match):
        nonlocal string_map, string_cnt
        text = match.group(0)
        marker = f"__STR_{string_cnt}__"
        string_map[marker] = text
        string_cnt += 1

        return marker

    for processed_line in processed_lines:
        code = processed_line['code']
        code = re.sub(lietrals, substitute, code)
        processed_line['code']= code

    return processed_lines, string_map, string_cnt

def holerith_constants (processed_lines, string_map, string_cnt):
    holerith = r"(?<![A-Za-z_])(\d+)[Hh]"

    for line in processed_lines:
        code = line['code']
        while True:
            match = re.search(holerith, code)
            if match is None:
                break
            marker = f"__STR_{string_cnt}__"
            holeriuth_size = int(match.group(1) )
            text_start = match.start()
            text_end = match.end() + holeriuth_size
            text = code[text_start:text_end]
            string_map[marker] = text
            string_cnt += 1
            code = code[:text_start] + marker + code[text_end:]

        line['code'] =code

    return processed_lines, string_map, string_cnt


def remove_spaces(processed_lines):
    for line in processed_lines:
        line['code'] = line['code'].replace(' ', '')

    return processed_lines

def finalize(processed_lines, string_map):
    marker_r = r"__STR_(\d+)__"

    for line in processed_lines:
        code = line['code']
        while True:
            match = re.search(marker_r, code)
            if match is None:
                break
            marker = match.group(0)
            string = string_map[marker]
            code = code[:match.start()] + string + code[match.end():]

        line['code'] = code

    return processed_lines


def preprocess_fortran77(source_text):
    f1 = normalize_f77_source(source_text)
    f2 = group_lines(f1)
    f3, string_map, string_cnt = extract_text(f2)
    f4, string_map, string_cnt = holerith_constants(f3, string_map, string_cnt)
    f5 = remove_spaces(f4)
    f6 = finalize(f5, string_map)

    return f6



# TESTE GERADOS POR LLM!!

class Test(unittest.TestCase):

    def pad_72(self, lines):
        """Simula o output da Fase 1 para testes isolados subsequentes."""
        return [line.ljust(72, ' ')[:72] for line in lines]

    # TESTES FASE 1
    def test_normalize_f77_source(self):
        raw_code = "C Comentario\n      A = 1\n* Outro comentario\n      B = 2"
        resultado = normalize_f77_source(raw_code)
        self.assertEqual(len(resultado), 2)
        self.assertEqual(len(resultado[0]), 72)
        self.assertEqual(resultado[0].strip(), "A = 1")
        self.assertEqual(resultado[1].strip(), "B = 2")

    # TESTES FASE 2
    def test_instrucao_unica_sem_rotulo(self):
        source = self.pad_72(["      PRINT *, 'HELLO'"])
        resultado = group_lines(source)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]['label'], '')
        self.assertEqual(resultado[0]['code'].strip(), "PRINT *, 'HELLO'")

    def test_instrucao_com_rotulo_e_espacos(self):
        source = self.pad_72(["1 0 0 CONTINUE"])
        resultado = group_lines(source)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]['label'], '100')
        self.assertEqual(resultado[0]['code'].strip(), "CONTINUE")

    def test_multiplas_continuacoes(self):
        source = self.pad_72([
            "      A = 1 +",
            "     +2 +",
            "     *3"
        ])
        resultado = group_lines(source)
        self.assertEqual(len(resultado), 1)
        codigo_limpo = resultado[0]['code'].replace(' ', '')
        self.assertEqual(codigo_limpo, "A=1+2+3")

    def test_fluxo_misto(self):
        source = self.pad_72([
            "10    X = 1",
            "      Y = 2 +",
            "     13",
            "20    Z = 4"
        ])
        resultado = group_lines(source)
        self.assertEqual(len(resultado), 3)
        self.assertEqual(resultado[0]['label'], '10')
        self.assertEqual(resultado[1]['label'], '')
        self.assertEqual(resultado[1]['code'].replace(' ', ''), "Y=2+3")
        self.assertEqual(resultado[2]['label'], '20')

    def test_falha_continuacao_orfao(self):
        source = self.pad_72(["     +A = 1"])
        with self.assertRaises(SyntaxError):
            group_lines(source)

    # TESTES FASE 3
        # TESTES FASE 3
    def test_instrucao_sem_strings(self):
            input_data = [{'label': '100', 'code': 'X = Y + Z'}]
            output_lines, string_map, string_cnt = extract_text(input_data)
            self.assertEqual(output_lines[0]['code'], 'X = Y + Z')
            self.assertEqual(len(string_map), 0)

    def test_string_unica(self):
            input_data = [{'label': '', 'code': "PRINT *, 'ERRO FATAL'"}]
            output_lines, string_map, string_cnt = extract_text(input_data)
            self.assertEqual(output_lines[0]['code'], 'PRINT *, __STR_0__')
            self.assertEqual(string_map['__STR_0__'], "'ERRO FATAL'")

    def test_multiplas_strings_mesma_linha(self):
            input_data = [{'label': '', 'code': "A = 'UM' // 'DOIS' // 'TRES'"}]
            output_lines, string_map, string_cnt = extract_text(input_data)
            self.assertEqual(output_lines[0]['code'], 'A = __STR_0__ // __STR_1__ // __STR_2__')
            self.assertEqual(string_map['__STR_0__'], "'UM'")
            self.assertEqual(string_map['__STR_1__'], "'DOIS'")
            self.assertEqual(string_map['__STR_2__'], "'TRES'")

    def test_estado_global_multiplas_linhas(self):
            input_data = [
                {'label': '10', 'code': "PRINT *, 'PRIMEIRA'"},
                {'label': '20', 'code': "PRINT *, 'SEGUNDA'"}
            ]
            output_lines, string_map, string_cnt = extract_text(input_data)
            self.assertEqual(output_lines[0]['code'], 'PRINT *, __STR_0__')
            self.assertEqual(output_lines[1]['code'], 'PRINT *, __STR_1__')
            self.assertEqual(string_map['__STR_0__'], "'PRIMEIRA'")
            self.assertEqual(string_map['__STR_1__'], "'SEGUNDA'")

    def test_strings_com_espacos_e_simbolos(self):
            input_data = [{'label': '', 'code': "MSG = '  .EQ.  3.14  '"}]
            output_lines, string_map, string_cnt = extract_text(input_data)
            self.assertEqual(output_lines[0]['code'], 'MSG = __STR_0__')
            self.assertEqual(string_map['__STR_0__'], "'  .EQ.  3.14  '")

    # TESTES FASE 4
    def test_holerith_constants(self):
        dados_teste = [
            {'label': '10', 'code': '      FORMAT(14HMENSAGEM CURTA)'},
            {'label': '20', 'code': '      MSG = 5HTESTE // 4H ERRO'}
        ]
        mapa_herdado = {'__STR_0__': "'TEXTO ANTIGO'"}
        contador_herdado = 1

        linhas_processadas, mapa_final, contador_final = holerith_constants(dados_teste, mapa_herdado, contador_herdado)

        self.assertEqual(linhas_processadas[0]['code'], '      FORMAT(__STR_1__)')
        self.assertEqual(linhas_processadas[1]['code'], '      MSG = __STR_2__ // __STR_3__O')
        self.assertEqual(mapa_final['__STR_1__'], '14HMENSAGEM CURTA')
        self.assertEqual(mapa_final['__STR_2__'], '5HTESTE')
        self.assertEqual(mapa_final['__STR_3__'], '4H ERR')
        self.assertEqual(contador_final, 4)

    # TESTES FASE 5
    def test_remove_spaces(self):
        input_data = [{'label': '', 'code': 'MSG = __STR_2__ // __STR_3__O'}]
        output = remove_spaces(input_data)
        self.assertEqual(output[0]['code'], 'MSG=__STR_2__//__STR_3__O')

    # TESTES FASE 6
    def test_finalize(self):
        input_data = [{'label': '100', 'code': 'PRINT*,__STR_0__,__STR_1__'}]
        mapa = {
            '__STR_0__': "'ERRO 1'",
            '__STR_1__': "4HFAIL"
        }
        output = finalize(input_data, mapa)
        self.assertEqual(output[0]['code'], "PRINT*,'ERRO 1',4HFAIL")

    # TESTE GLOBAL DE INTEGRAÇÃO
    def test_preprocess_fortran77_integration(self):
        raw_source = (
            "C Programa de Teste\n"
            "10    P R I N T *, '  MENSAGEM  ' ,\n"
            "     + 4H FIM\n"
            "* Fim do programa\n"
            "      E N D"
        )

        resultado = preprocess_fortran77(raw_source)

        self.assertEqual(len(resultado), 2)

        self.assertEqual(resultado[0]['label'], '10')
        self.assertEqual(resultado[0]['code'], "PRINT*,'  MENSAGEM  ',4H FIM")

        self.assertEqual(resultado[1]['label'], '')
        self.assertEqual(resultado[1]['code'], "END")\


    def test_holerith_adjacente_operador(self):
        """Verifica se o extrator isola o Hollerith colado a operadores sem corrompê-los."""
        dados = [{'label': '', 'code': 'X=5HABCDE+1'}]
        mapa_ini = {}
        cnt_ini = 0
        res, mapa, _ = holerith_constants(dados, mapa_ini, cnt_ini)
        self.assertEqual(res[0]['code'].strip(), 'X=__STR_0__+1')  # O '+' deve ser preservado
        self.assertEqual(mapa['__STR_0__'], '5HABCDE')

    def test_comentarios_intercalados_continuacao(self):
        """Valida se o group_lines ignora comentários entre linhas de continuação após normalização."""
        raw_source = (
            "      A = 1\n"
            "C COMENTARIO INTERCALADO\n"
            "     + + 2"
        )
        # A Fase 1 remove os comentários e normaliza para 72 colunas
        f1 = normalize_f77_source(raw_source)

        # A Fase 2 agrupa as linhas resultantes
        resultado = group_lines(f1)

        codigo_limpo = resultado[0]['code'].replace(' ', '')
        self.assertEqual(codigo_limpo, "A=1+2")

    def test_labels_com_espacos(self):
        """Testa se rótulos com espaços internos são normalizados corretamente."""
        source = self.pad_72(["1 2 3 CONTINUE"])
        resultado = group_lines(source)
        self.assertEqual(resultado[0]['label'], '123')  # Espaços em labels são irrelevantes

    def test_linha_vazia_no_meio(self):
        """Garante que linhas totalmente vazias não quebram o fluxo de normalização."""
        raw = "      A = 1\n\n      END"
        resultado = normalize_f77_source(raw)
        self.assertEqual(len(resultado), 2)  # A=1 e END


if __name__ == '__main__':
    unittest.main()