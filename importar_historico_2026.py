# -*- coding: utf-8 -*-
"""
Script de saneamento e importação do histórico de 2026 (Janeiro a Outubro)
processando extratos externos no banco de dados SQLite 'financas_casa.db' (Oikos).

NOTA DE USO E DADOS EXTERNOS:
Este script de importação foi projetado para execução administrativa pontual.
Os arquivos de entrada (extratos / relatórios em PDF ou XLS) DEVEM ser fornecidos
externamente através da variável configurável ORGANIZZE_DIR (ou parâmetro de linha
de comando), fora da árvore de código do projeto, garantindo a privacidade dos dados.
"""

import os
import re
import sys
import glob
import shutil
import sqlite3
import unicodedata
from pypdf import PdfReader

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("OIKOS_DB_PATH", os.path.join(BASE_DIR, "financas_casa.db"))
BACKUP_PATH = os.path.join(BASE_DIR, "financas_casa_backup_pre_correcao.db")

ORGANIZZE_DIR = r"c:\Users\carlo\Downloads\Movimentações Organizze"


def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_chave_descricao(descricao: str) -> str:
    """Normaliza a descrição para deduplicação estrita (data + descrição + valor)."""
    limpo = remover_acentos(descricao or "").upper()
    limpo = re.sub(r"\s+", " ", limpo).strip()
    limpo = re.sub(r"[^A-Z0-9]", "", limpo)
    return limpo


def eh_receita_carlos_99(descricao: str, cat_original: str = "") -> bool:
    """Verifica se a receita pertence a 'CARLOS ALBERTO CHAVES JUNIOR' ou 99."""
    desc_up = remover_acentos(descricao or "").upper()
    cat_up = remover_acentos(cat_original or "").upper()
    desc_compacto = re.sub(r"[^A-Z0-9]", "", desc_up)
    combinado = f"{desc_up} {cat_up}"

    return (
        "CARLOSALBERTOCHAVESJUNIOR" in desc_compacto
        or "99 POP" in combinado
        or "99 PJ" in combinado
        or "99 SALARIO" in combinado
        or "SALARIO 99" in combinado
        or "RENDA 99" in combinado
        or "99 JUNIOR" in combinado
        or "99 TECNOLOGIA" in desc_up
        or "CHAVES TRANSPORTES" in combinado
        or "99 / CHAVES" in cat_up
    )


def mapear_categoria_e_subcategoria(tipo: str, descricao: str, cat_original: str = ""):
    """
    Mapeia categorias e subcategorias conforme as regras de negócio:
    - Toda receita em nome de 'CARLOS ALBERTO CHAVES JUNIOR' -> '99 / Chaves (Carlos)'
    - Transferência -> 'Transferência Entre Contas'
    - Salário da Fernanda, Copasa, Cemig, farmácias, Acordo BV, manutenção do HB20 e demais despesas
      mapeados para as categorias existentes na tabela 'transacoes'.
    """
    if tipo == "transferencia":
        return "Transferência Entre Contas", "Transferência Interna"

    desc_up = remover_acentos(descricao or "").upper()
    cat_up = remover_acentos(cat_original or "").upper()
    combinado = f"{desc_up} {cat_up}"

    if tipo == "receita":
        if eh_receita_carlos_99(descricao, cat_original):
            return "99 / Chaves (Carlos)", "Corridas App"

        if (
            "SALARIO FERNANDA" in combinado
            or "FERNANDA CRISTINE DA SILVA SOUSA MACHADO" in desc_up
            or "COMPLEMENTO SALARIO" in desc_up
            or "13 SALARIO FERNANDA" in desc_up
        ):
            return "Salário Fernanda", "Salário Mensal"

        if "RENDIMENTO" in combinado:
            return "Rendimentos", "Rendimentos Conta"

        if (
            "EMPRESTIMO" in combinado
            or "APORTE" in combinado
            or "MARIA APARECIDA" in desc_up
            or "CARLOS ALBERTO CHAVES" in desc_up
            or "CRISTOPHER FELLIPE" in desc_up
            or "NAYARA THAMIRES" in desc_up
            or "IZAURA DAS GRACAS" in desc_up
            or "PARCELAMENTO DE FATURA" in desc_up
            or "PARCELAMENTO DEFATURA" in desc_up
        ):
            return "Empréstimo / Aporte", "Aporte/Familiar"

        return "Receitas Extras", "Outras Receitas"

    # === DESPESAS ===
    if "COPASA" in combinado or "SANEAMENTO DE MINAS GERAIS" in desc_up:
        return "HABITAÇÃO", "Água/Copasa"

    if "CEMIG" in combinado or "ENERGIA" in cat_up:
        return "Energia", "Energia/CEMIG"

    if "ACORDO BV" in combinado or "BANCO BV" in desc_up:
        return "Acordo BV", "Acordo BV"

    if (
        ("HB20" in combinado and "IPVA" not in combinado)
        or "MANUTENCAO VEICULO" in cat_up
        or "MANUTENCOES HB20" in desc_up
        or "MANUTENCAO SANDERO" in desc_up
        or "HARD DISK HB20" in desc_up
        or "SEGURO HB20" in desc_up
        or desc_up.startswith("SEGURO")
        or "BHMSMANUTENCOES" in desc_up
        or "BHMS MANUTENCOES" in desc_up
        or "TROCA DE PASTILHAS" in desc_up
        or "TROCA DE OLEO" in desc_up
        or "LAVAGEM" in desc_up
    ):
        return "Manutenção Veículo", "Manutenção"

    if "IPVA" in combinado or "DOCUMENTACAO" in cat_up or "MULTA" in desc_up:
        return "Impostos Veículo", "IPVA/Licenciamento"

    if (
        "RAIA DROGASIL" in desc_up
        or "RAIA4144" in desc_up
        or "RD SAUDE" in desc_up
        or "DROGARIA" in desc_up
        or "PAGUE MENOS" in desc_up
        or "PRAFARMA" in desc_up
        or "VENVANSE" in desc_up
        or "OZIVY" in desc_up
        or "PSYLLIUM" in desc_up
        or "RAIA WHEY" in desc_up
        or "RAIA FRALDAS" in desc_up
        or "VITAMINAS" in desc_up
        or "MEDICAMENTO" in cat_up
        or "FARMACIA" in cat_up
    ):
        return "Medicamentos", "Saúde/Farmácia"

    if (
        "POSTO " in desc_up
        or desc_up.startswith("POSTO")
        or "ABASTECIMENTO" in desc_up
        or "ABASTECER BH" in desc_up
        or "SAO PEDRO COMBUSTIVEIS" in desc_up
        or "CALANGO TANGO" in desc_up
        or "CALANGO-TANGO" in desc_up
        or "CALANDO TANGO" in desc_up
        or "MIRAMAR" in desc_up
        or "VIA DO MINERIO" in desc_up
        or "GASLUB" in desc_up
        or "PETRO OURO" in desc_up
        or "COMBUSTIVEL" in cat_up
    ):
        return "Combustível (Trabalho)", "Etanol"

    if (
        "CLARO " in desc_up
        or "FATURA CLARO" in desc_up
        or "MAXXNET" in desc_up
        or "MULTILINK" in desc_up
        or "INTERNET BANDA LARGA" in desc_up
    ):
        return "HABITAÇÃO", "Telefone/Internet/Claro"

    if "GOOGLE ONE" in desc_up or "GOOGLE G1" in desc_up:
        return "HABITAÇÃO", "Assinaturas/Google One"

    if "PAGALEVE" in desc_up or "PAGA LEVE" in desc_up:
        return "Moradia/Contas", "PagaLeve"

    if "PAGAMENTO DE FATURA" in combinado or "PAGAMENTO DEFATURA" in combinado or "FATURA PICPAY" in desc_up:
        return "Pagamento de fatura", "Cartão de Crédito"

    if (
        "CREDISERV" in desc_up
        or "EMPRESTIMO" in desc_up
        or "DIVIDA" in combinado
        or "NAYARA" in desc_up
        or "IZAURA" in desc_up
        or desc_up in ("PAI", "PAGAMENTO EMPRESTIMO CONTAS PAI")
    ):
        return "Outras Dívidas", "Empréstimos/Acordos"

    if (
        "PLANO DE SAUDE" in combinado
        or "PLANOS ODONTOLOGICOS" in combinado
        or "PLANO ODONTO" in combinado
        or "COPARTICIPACAO" in combinado
        or "COPARTIPACAO" in combinado
        or "UNIMED" in desc_up
        or "SAUDE" in cat_up
    ):
        return "SAÚDE", "Plano de Saúde"

    if "WELLHUB" in combinado or "ACADEMIA" in cat_up or "BOLAO EMAGRECIMENTO" in desc_up:
        return "Academia / Wellhub", "Academia"

    if (
        "GM VISAGE" in desc_up
        or "BARBEARIA" in combinado
        or "BARBEADOR" in desc_up
        or "SARAH CAMILA" in desc_up
        or "CABELO" in cat_up
        or "MAKE FERNANDA" in desc_up
    ):
        return "Barbearia", "Corte/Barba"

    if (
        "POS-GRADUACAO" in combinado
        or "AUDIBLE" in desc_up
        or "EVERAND" in desc_up
        or "AULA DE CANTO" in desc_up
        or "CIFRACLUB" in desc_up
        or "EDUCACAO" in cat_up
    ):
        return "Educação", "Cursos/Livros"

    if (
        "YOUCINE" in desc_up
        or "ANTPAY" in desc_up
        or "YOUTUBE PREMIUM" in desc_up
        or "AMAZON PRIME" in desc_up
        or "STREAMING" in cat_up
    ):
        return "Streaming", "Assinaturas"

    if "99 TECNOLOGIA" in desc_up or "TAXI / UBER" in cat_up or "TRANSPORTE FERNANDA" in desc_up:
        return "Transporte", "Transporte Fernanda/Escola"
    if "ALLPARK" in desc_up or "ESTACIONAMENTO" in desc_up:
        return "Transporte", "Estacionamento"

    if (
        "PADARIA" in desc_up
        or "MAISKIPAO" in desc_up
        or "PANIFICADORA" in desc_up
        or "SABOR DA VILA" in desc_up
        or "PONGELUPE" in desc_up
    ):
        return "Alimentação", "Padaria"

    if "SACOLAO" in desc_up or "FEIRA" in desc_up or "RENATA RODRIGUES" in desc_up:
        return "Alimentação", "Feira/Sacolão"

    if (
        "99 FOOD" in desc_up
        or "IFOOD" in desc_up
        or "PH LANCHES" in desc_up
        or "PHLANCHES" in desc_up
        or "OUTBACK" in desc_up
        or "KFC" in desc_up
        or "LANCHE" in desc_up
        or "ALMOCO" in desc_up
        or "SODRESSORVETE" in desc_up
        or "BEM-TI-VI" in desc_up
        or "RESTAURANTE" in cat_up
        or "ALIMENTACAO NA RUA" in cat_up
    ):
        return "Alimentação", "Restaurante"

    if (
        "SUPERMERCADO" in combinado
        or "MERCADO JE" in desc_up
        or "SUPERMERCADOS BH" in desc_up
        or "SUP EPA" in desc_up
        or "DMA DISTRIBUIDORA" in desc_up
        or "QUASE T" in desc_up
        or "ABC BACANA" in desc_up
        or "ABC ATACADO" in desc_up
        or "SAMS" in desc_up
        or "MUMU" in desc_up
        or "DELICIAS DO LEITE" in desc_up
        or "LATICINIOS" in desc_up
        or "SUPERLOG" in desc_up
        or "IRMAOS MATTAR" in desc_up
        or "BRAZALMEIDA" in desc_up
        or "ADICAO DISTRIBUICAO" in desc_up
        or "EDIVALDO FERREIRA" in desc_up
        or "DANIEL ALVES" in desc_up
        or "DANIELALVESDE" in desc_up
        or "SELMIR APARECIDO" in desc_up
        or "ORCIM COMERCIO" in desc_up
        or "CONCILIACAO ALIMENTACAO" in desc_up
        or "ALIMENTACAO" in cat_up
    ):
        return "Alimentação", "Supermercado"

    if "HABITACAO" in cat_up or "CONSTRUIR" in desc_up or "LAVANDERIA" in desc_up or "GAS DE COZINHA" in desc_up:
        return "HABITAÇÃO", "Manutenção Casa"

    return "Pessoal", "Outros"


def extrair_pdfs_oficiais_organizze():
    """
    Lê EXCLUSIVAMENTE os 10 PDFs oficiais do Organizze (Janeiro a Outubro de 2026)
    e retorna tanto os registros extraídos quanto os valores de rodapé oficiais de cada mês.
    """
    arquivos = sorted(glob.glob(os.path.join(ORGANIZZE_DIR, "*.pdf")))
    padrao_linha = re.compile(
        r"(?m)^(receita|despesa|transferência|saldo inicial)\s+(\d{2}/\d{2}/\d{4})\s+([\s\S]*?)\s+R\$\s*([-0-9.,]+)\s+(Pago|Não pago)"
    )
    padrao_conta = re.compile(
        r"^(.*?)\s+(Cartão\s*Mercado\s*Pago|Mercado\s*Pago|Chaves\s*transportes|Nubank\s*Fernanda|Sicoob\s*Fernanda|Sicoob\s*-\s*Capital\s*Socia\w*|PicPay(?:\s*Júnior)?|Carteira|Reserva\s*de\s*Segurança|Conta\s*BV|Cofrinhos)\s+(.*)$",
        re.I,
    )

    registros = []
    rodapes_oficiais = {}

    for caminho in arquivos:
        reader = PdfReader(caminho)
        texto = "\n".join(page.extract_text() or "" for page in reader.pages)

        # Extrair rodapé oficial do PDF do Organizze
        ep = re.search(r"Entradas previstas\s*R\$\s*([-0-9.,]+)", texto)
        er = re.search(r"Entradas realizadas\s*R\$\s*([-0-9.,]+)", texto)
        sp = re.search(r"Saídas previstas\s*R\$\s*([-0-9.,]+)", texto)
        sr = re.search(r"Saídas realizadas\s*R\$\s*([-0-9.,]+)", texto)

        texto_limpo = re.sub(
            r"Mostrando todos os lançamentos.*?\nTipo Data Descrição Conta/Cartão Categoria Valor Situação\n?",
            "",
            texto,
            flags=re.S,
        )
        texto_limpo = re.sub(r"Mostrando \d+ - \d+ de \d+\s*\d+/\d+\s*", "\n", texto_limpo)

        mes_arquivo = None
        for m in padrao_linha.finditer(texto_limpo):
            tipo_raw, data_br, meio, valor_str, situacao = m.groups()
            dia, mes, ano = data_br.split("/")
            data_iso = f"{ano}-{mes}-{dia}"
            mes_arquivo = f"{ano}-{mes}"

            meio_limpo = " ".join(meio.split())
            mc = padrao_conta.match(meio_limpo)
            if mc:
                descricao, conta_orig, cat_orig = mc.groups()
            else:
                descricao, conta_orig, cat_orig = meio_limpo, "Mercado Pago", ""

            descricao = re.sub(r"CHAVESJUNIOR", "CHAVES JUNIOR", descricao.strip(), flags=re.I)
            desc_up = remover_acentos(descricao).upper()

            # Regra 3.1: NÃO importar linhas de 'Saldo Anterior', 'saldo inicial' ou 'Ajuste de Saldo' como receita/despesa
            if tipo_raw == "saldo inicial" or "AJUSTE DE SALDO" in desc_up or "SALDO ANTERIOR" in desc_up:
                continue

            valor = round(abs(float(valor_str.replace(".", "").replace(",", "."))), 2)
            if valor <= 0:
                continue

            # Regra 3.2: Tratar 'transferência' apenas como transferência interna
            if tipo_raw == "transferência":
                tipo_db = "transferencia"
            else:
                tipo_db = tipo_raw

            categoria, subcategoria = mapear_categoria_e_subcategoria(tipo_db, descricao, cat_orig)

            # Regra 3.3: Receitas no nome de 'CARLOS ALBERTO CHAVES JUNIOR' vão para '99 / Chaves (Carlos)'
            if tipo_db == "receita" and eh_receita_carlos_99(descricao, cat_orig):
                categoria = "99 / Chaves (Carlos)"
                subcategoria = "Corridas App"

            # Regra 3.4: Lançamentos com status 'Pago' nos PDFs anteriores a outubro devem ser salvos com pago=1 e data_liquidacao=data
            pago_int = 1 if situacao == "Pago" else 0
            status_pgto = "pago" if situacao == "Pago" else "pendente"
            dt_liquidacao = data_iso if pago_int == 1 else None

            registros.append(
                {
                    "data": data_iso,
                    "data_liquidacao": dt_liquidacao,
                    "descricao": descricao,
                    "valor": valor,
                    "tipo": tipo_db,
                    "categoria": categoria,
                    "subcategoria": subcategoria,
                    "conta": "Mercado Pago",
                    "conta_id": 1,
                    "pago": pago_int,
                    "status_pagamento": status_pgto,
                    "origem": os.path.basename(caminho),
                }
            )

        if mes_arquivo:
            rodapes_oficiais[mes_arquivo] = {
                "entradas_prev": float(ep.group(1).replace(".", "").replace(",", ".")) if ep else 0.0,
                "entradas_real": float(er.group(1).replace(".", "").replace(",", ".")) if er else 0.0,
                "saidas_prev": abs(float(sp.group(1).replace(".", "").replace(",", "."))) if sp else 0.0,
                "saidas_real": abs(float(sr.group(1).replace(".", "").replace(",", "."))) if sr else 0.0,
            }

    return registros, rodapes_oficiais


def executar_saneamento_e_importacao():
    # Passo 1: Cópia de segurança do banco financas_casa.db para financas_casa_backup_pre_correcao.db
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"[1/4] Backup criado com sucesso em: {BACKUP_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Passo 2: Remover as transações importadas pelo script anterior (id > 126)
    # e limpar lançamentos anteriores a 01/10/2026 / 'Saldo Anterior Setembro' (id = 1)
    cursor.execute("SELECT COUNT(*) FROM transacoes WHERE id > 126 OR data < '2026-10-01'")
    qtd_removida = cursor.fetchone()[0]
    cursor.execute("DELETE FROM transacoes WHERE id > 126 OR data < '2026-10-01'")
    conn.commit()
    print(f"[2/4] Limpeza concluída: {qtd_removida} registros anteriores/inflacionados removidos.")

    # Passo 3: Ler EXCLUSIVAMENTE os PDFs oficiais do Organizze (Janeiro a Outubro de 2026)
    org_regs, rodapes = extrair_pdfs_oficiais_organizze()
    print(f"[3/4] Lidos {len(org_regs)} lançamentos dos 10 PDFs oficiais do Organizze (sem Saldo Anterior/Ajuste de Saldo).")

    # Carregar o que já existe em Outubro/2026 no banco (id <= 126) para deduplicação estrita
    cursor.execute("SELECT id, data, descricao, valor, tipo FROM transacoes")
    existentes_db = cursor.fetchall()

    chaves_exatas = set()
    chaves_outubro_dv = set()
    for _, dt, desc, val, tp in existentes_db:
        chaves_exatas.add((dt, normalizar_chave_descricao(desc), round(float(val), 2), tp))
        if dt.startswith("2026-10"):
            chaves_outubro_dv.add((dt, tp, round(float(val), 2)))

    inseridos = 0
    duplicados_ignorados = 0

    for reg in sorted(org_regs, key=lambda x: x["data"]):
        # Em Outubro/2026, o banco já possui os lançamentos conciliados de Outubro (IDs 2 a 126);
        # não reinserimos lançamentos de Organizzeout .pdf para não duplicar faturas/contas de Outubro.
        if reg["data"].startswith("2026-10"):
            duplicados_ignorados += 1
            continue

        chave = (reg["data"], normalizar_chave_descricao(reg["descricao"]), reg["valor"], reg["tipo"])
        if chave in chaves_exatas:
            duplicados_ignorados += 1
            continue

        chaves_exatas.add(chave)

        # Transferências internas não entram em receita/despesa; afeta_saldo_bancario=1 apenas para histórico normal anterior ao marco 2026-10-21
        afeta_saldo = 0 if reg["tipo"] == "transferencia" else (1 if reg["data"] < "2026-10-21" else 0)

        cursor.execute(
            """
            INSERT INTO transacoes (
                data, data_liquidacao, descricao, valor, tipo, categoria, subcategoria,
                conta, conta_id, pago, afeta_saldo_bancario, status_pagamento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reg["data"],
                reg["data_liquidacao"],
                reg["descricao"],
                reg["valor"],
                reg["tipo"],
                reg["categoria"],
                reg["subcategoria"],
                reg["conta"],
                reg["conta_id"],
                reg["pago"],
                afeta_saldo,
                reg["status_pagamento"],
            ),
        )
        inseridos += 1

    conn.commit()
    print(f"[4/4] Importação limpa concluída: {inseridos} registros inseridos ({duplicados_ignorados} duplicatas ignoradas).")

    # Conferência Mês a Mês contra o Rodapé Oficial do Organizze
    print("\n" + "=" * 120)
    print("CONFERÊNCIA MENSAL (JANEIRO A OUTUBRO 2026): BANCO 'financas_casa.db' vs RODAPÉ OFICIAL ORGANIZZE")
    print("=" * 120)
    print(
        f"{'Mês':<8} | {'Qtd':>4} | {'Receita 99':>13} | {'Receita Total':>14} | {'Rodapé Org Rec':>14} | {'Desp. Realiz.':>14} | {'Desp. Total':>13} | {'Rodapé Org Desp':>15}"
    )
    print("-" * 120)

    cursor.execute(
        """
        SELECT
            substr(data, 1, 7) AS mes,
            COUNT(CASE WHEN tipo IN ('receita', 'despesa') THEN 1 END) AS qtd,
            SUM(CASE WHEN tipo = 'receita' AND categoria = '99 / Chaves (Carlos)' THEN valor ELSE 0 END) AS rec_99,
            SUM(CASE WHEN tipo = 'receita' THEN valor ELSE 0 END) AS rec_total,
            SUM(CASE WHEN tipo = 'despesa' AND pago = 1 THEN valor ELSE 0 END) AS desp_paga,
            SUM(CASE WHEN tipo = 'despesa' THEN valor ELSE 0 END) AS desp_total
        FROM transacoes
        WHERE data >= '2026-01-01' AND data <= '2026-10-31'
        GROUP BY mes
        ORDER BY mes
        """
    )

    tot_qtd = 0
    tot_99 = 0.0
    tot_rec = 0.0
    tot_desp_paga = 0.0
    tot_desp_all = 0.0

    for mes, qtd, rec_99, rec_total, desp_paga, desp_total in cursor.fetchall():
        rec_99 = rec_99 or 0.0
        rec_total = rec_total or 0.0
        desp_paga = desp_paga or 0.0
        desp_total = desp_total or 0.0

        tot_qtd += qtd
        tot_99 += rec_99
        tot_rec += rec_total
        tot_desp_paga += desp_paga
        tot_desp_all += desp_total

        rod = rodapes.get(mes, {})
        r_rec = rod.get("entradas_real", 0.0)
        r_desp = rod.get("saidas_prev", 0.0)

        print(
            f"{mes:<8} | {qtd:>4} | R$ {rec_99:>10,.2f} | R$ {rec_total:>11,.2f} | R$ {r_rec:>11,.2f} | R$ {desp_paga:>11,.2f} | R$ {desp_total:>10,.2f} | R$ {r_desp:>12,.2f}"
        )

    print("-" * 120)
    print(
        f"{'TOTAL':<8} | {tot_qtd:>4} | R$ {tot_99:>10,.2f} | R$ {tot_rec:>11,.2f} | {'-':>14} | R$ {tot_desp_paga:>11,.2f} | R$ {tot_desp_all:>10,.2f} | {'-':>15}"
    )
    print("=" * 120)

    conn.close()


if __name__ == "__main__":
    executar_saneamento_e_importacao()
