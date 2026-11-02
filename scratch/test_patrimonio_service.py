# Teste unitario e funcional de patrimonio_service.py
import sys
import os
import shutil
sys.path.insert(0, os.path.abspath("."))

import sqlite3
import patrimonio_service
import saldo_service

# Banco temporario exclusivo para o teste (copiado do schema base)
TEMP_DB = "temp_test_patrimonio_service.db"
if os.path.exists(TEMP_DB):
    os.remove(TEMP_DB)

shutil.copyfile("financas_remodelacao.db", TEMP_DB)
conn = sqlite3.connect(TEMP_DB)

try:
    # 1. Obter saldo antes de qualquer operacao de bens
    saldo_antes = saldo_service.calcular_saldo_consolidado(conn)["saldo_consolidado"]

    # Contar transacoes antes
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM transacoes")
    qtd_transacoes_antes = cur.fetchone()[0]

# 2. Inicializar tabelas e cadastrar um bem antigo sem data nem preco de compra
bem1_id = patrimonio_service.criar_bem(conn, {
    "nome": "Notebook Dell Inspiron",
    "tipo": "Eletrônico",
    "proprietario": "Carlos",
    "valor_aquisicao": None, # sem preco de compra conhecido
    "data_aquisicao": "",    # sem data de compra conhecida
    "valor_atual_estimado": 2800.0,
    "data_avaliacao": "2026-11-01",
    "observacoes": "Notebook de trabalho"
})

print(f"Bem 1 cadastrado com sucesso: id={bem1_id}")

# 3. Cadastrar o Veiculo da Operacao Drive (HB20)
bem2_id = patrimonio_service.criar_bem(conn, {
    "nome": "Hyundai HB20 1.0 Flex",
    "tipo": "Veículo",
    "proprietario": "Carlos",
    "valor_aquisicao": 48000.0,
    "data_aquisicao": "2023-05-10",
    "valor_atual_estimado": 52000.0,
    "data_avaliacao": "2026-11-01",
    "observacoes": "Carro utilizado na operação Oikos Drive e família",
    "is_veiculo_drive": 1
})

print(f"Veículo Drive cadastrado com sucesso: id={bem2_id}")

# 4. Registrar reavaliacao do notebook (ex: depreciacao para 2500)
patrimonio_service.registrar_nova_avaliacao(
    conn,
    bem_id=bem1_id,
    valor_estimado=2500.0,
    data_avaliacao="2026-11-01",
    observacoes="Ajuste de mercado para notebook usado"
)
print("Nova avaliação registrada com sucesso no histórico")

# 5. Conferir historico de reavaliacoes
hist = patrimonio_service.listar_historico_avaliacoes(conn, bem1_id)
print(f"Histórico de avaliações do notebook ({len(hist)} registros):")
for h in hist:
    print(f"  - {h['data_avaliacao']}: R$ {h['valor_estimado']} ({h['observacoes']})")
assert len(hist) == 2, f"Esperado 2 avaliacoes, obtido {len(hist)}"

# 6. Conferir que NENHUMA transacao foi criada e que o saldo de caixa permaneceu identico
cur.execute("SELECT COUNT(*) FROM transacoes")
qtd_transacoes_depois = cur.fetchone()[0]
assert qtd_transacoes_depois == qtd_transacoes_antes, f"ERRO: Transações foram alteradas! Antes: {qtd_transacoes_antes}, Depois: {qtd_transacoes_depois}"

saldo_depois = saldo_service.calcular_saldo_consolidado(conn)["saldo_consolidado"]
assert saldo_depois == saldo_antes, f"ERRO: Saldo financeiro foi alterado! Antes: {saldo_antes}, Depois: {saldo_depois}"
print(f"[OK] Integridade de Caixa Preservada: Saldo {saldo_depois} e {qtd_transacoes_depois} transações")

# 7. Resumo Patrimonial
resumo = patrimonio_service.obter_resumo_patrimonial(conn)
print("\nResumo Patrimonial Calculado:")
print(f"  Total em Bens: R$ {resumo['total_bens']:.2f} ({resumo['total_bens_count']} bens ativos)")
print(f"  Saldo em Caixa: R$ {resumo['saldo_caixa']:.2f}")
print(f"  Passivos / Dívidas: R$ {resumo['total_dividas']:.2f}")
print(f"  Patrimônio Líquido: R$ {resumo['patrimonio_liquido']:.2f}")
if resumo["metricas_veiculo_drive"]:
    print(f"  Veículo Drive Vinculado: {resumo['metricas_veiculo_drive']['nome']} (KM total: {resumo['metricas_veiculo_drive']['km_total_rodado']} km)")

finally:
    conn.close()
    if os.path.exists(TEMP_DB):
        try:
            os.remove(TEMP_DB)
        except Exception:
            pass

print("\nTODOS OS TESTES DE PATRIMONIO PASSARAM COM SUCESSO!")
