import sqlite3

conn = sqlite3.connect('financas_remodelacao.db')
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM planejamento_despesas_eventuais")
qtd = cur.fetchone()[0]
print(f"Total despesas eventuais no banco: {qtd}")

if qtd == 0:
    despesas_iniciais = [
        ("IPVA HB20 2027", "Impostos Veículo", "Carlos", "2027-01-15", "2027-01", 1200.0, None, "anual", "planejada", None, 1, "mensal", "Previsão do IPVA do veículo de trabalho"),
        ("Seguro Auto HB20 AGV", "Manutenção Veículo", "Carlos", "2027-02-10", "2027-02", 630.0, None, "anual", "planejada", None, None, "mensal", "Renovação anual da proteção veicular"),
        ("Matrícula & Material Escolar", "Educação", "Família", "2027-01-20", "2027-01", 850.0, None, "anual", "planejada", None, None, "mensal", "Início do ano letivo e livros"),
        ("Manutenção Preventiva HB20", "Manutenção Veículo", "Carlos", "2027-04-15", "2027-04", 550.0, None, "anual", "planejada", None, None, "mensal", "Troca de óleo, pastilhas e filtros"),
        ("Natal & Festas de Fim de Ano", "Lazer", "Família", "2026-12-20", "2026-12", 600.0, None, "anual", "planejada", None, 6, "mensal", "Ceia familiar e presentes")
    ]
    cur.executemany("""
        INSERT INTO planejamento_despesas_eventuais (
            nome, categoria, responsavel, data_prevista, mes_previsto,
            valor_estimado, valor_confirmado, recorrencia, status,
            transacao_id, cofrinho_id, frequencia_contribuicao, observacoes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, despesas_iniciais)
    conn.commit()
    print(f"Inseridos {len(despesas_iniciais)} compromissos anuais/eventuais realistas!")

conn.close()
