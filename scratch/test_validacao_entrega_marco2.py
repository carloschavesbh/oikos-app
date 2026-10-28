import sys
import os

sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

import sqlite3
from streamlit.testing.v1 import AppTest
import saldo_service

print("=== VALIDAÇÃO INTEGRADA: RENDA E PRODUÇÃO FAMILIAR + MARCO 99 ===")

# 1. Integridade do banco de produção
conn = sqlite3.connect("financas_casa.db")
cur = conn.cursor()
cur.execute("PRAGMA integrity_check")
check = cur.fetchone()[0]
assert check == "ok"
cur.execute("SELECT COUNT(*) FROM transacoes")
tx_count = cur.fetchone()[0]
saldo_info = saldo_service.calcular_saldo_consolidado(conn)
saldo_real_str = f"{float(saldo_info['saldo_consolidado']):.2f}".replace('.', ',')
conn.close()
print(f"✅ 1. Integridade do banco preservada: {tx_count} transações cadastradas, PRAGMA = {check}, Saldo consolidado = R$ {saldo_real_str}.")

# 2. Executar AppTest
app_path = os.path.abspath('app.py')
at = AppTest.from_file(app_path, default_timeout=30)
at.run()
assert not at.exception, f"Exceção ao carregar Visão Geral: {[e.value for e in at.exception]}"
print("✅ 2. App executado com 0 exceções.")

# 3. Validar Card 1 dos 5 Indicadores Superiores
metric_renda = next((m for m in at.metric if "Renda e Produção" in m.label), None)
assert metric_renda is not None, f"Card 'Renda e Produção Familiar' não encontrado! Labels encontrados: {[m.label for m in at.metric]}"
print(f"Card 1 encontrado: label='{metric_renda.label}', value='{metric_renda.value}', delta='{metric_renda.delta}'")
assert "4.863,83" in metric_renda.value, f"Valor esperado 'R$ 4.863,83', obtido '{metric_renda.value}'"
assert "Ref. Mista" in str(metric_renda.delta), f"Delta esperado contendo 'Ref. Mista', obtido '{metric_renda.delta}'"
print("✅ 3. Card 1 exibe perfeitamente o total combinado de R$ 4.863,83 com discriminação de referência mista!")

# 4. Validar abertura do detalhe da Renda (btn_kpi_renda)
btn_renda = next((b for b in at.button if "btn_kpi_renda" in str(b.key)), None)
assert btn_renda is not None
btn_renda.click()
at.run()
assert not at.exception, f"Exceção ao abrir detalhes da renda: {[e.value for e in at.exception]}"

# 5. Validar ausência de </strong> ou tags HTML quebradas no detalhamento da renda
detalhes_renda_markdown = [
    m.value for m in at.markdown
    if "Salário Fernanda" in m.value or "Produção 99" in m.value or "Discriminação da Renda" in m.value or "Total Combinado" in m.value
]
assert len(detalhes_renda_markdown) >= 4, f"Esperados pelo menos 4 blocos de markdown no detalhe, encontrados: {len(detalhes_renda_markdown)}"

for t in detalhes_renda_markdown:
    assert "</strong>" not in t, f"Tag </strong> encontrada no detalhamento: {t}"
    assert "<strong>" not in t, f"Tag <strong> encontrada no detalhamento: {t}"

# Verificar menções obrigatórias no detalhe aberto
texto_detalhe_geral = " ".join(detalhes_renda_markdown)
assert "3.523,43" in texto_detalhe_geral, "Salário Fernanda (R$ 3.523,43) não encontrado no detalhamento!"
assert "1.340,40" in texto_detalhe_geral, "Produção Bruta 99 (R$ 1.340,40) não encontrada no detalhamento!"
assert "4.863,83" in texto_detalhe_geral, "Total Combinado (R$ 4.863,83) não encontrado no detalhamento!"
print("✅ 4. Painel de detalhes da renda 100% corrigido: sem HTML quebrado, com todas as discriminações contábeis.")

# Fechar detalhe
btn_close = next((b for b in at.button if "btn_close_renda" in str(b.key)), None)
if btn_close:
    btn_close.click()
    at.run()

# 6. Validar presença do botão de Marco 99
btn_marco = next((b for b in at.button if "btn_abrir_modal_marco_99" in str(b.key)), None)
assert btn_marco is not None
print(f"✅ 5. Botão de gerenciamento do Marco presente: '{btn_marco.label}'")

print("🎉 TODAS AS VALIDAÇÕES DE ENTREGA PASSARAM COM SUCESSO!")
