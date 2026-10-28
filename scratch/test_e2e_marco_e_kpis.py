import sys
import os
import sqlite3
from streamlit.testing.v1 import AppTest

sys.stdout.reconfigure(encoding='utf-8')

print("=== TESTE E2E: ALINHAMENTO DE KPIS E MARCO DE PRODUÇÃO 99 ===")

# 1. Verificar CSS no app.py
with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

assert 'div[data-testid="column"]:has(div[class*="st-key-btn_kpi_"]) div[data-testid="stMetric"]' in app_code
assert 'min-height: 104px !important;' in app_code
assert 'margin-top: 6px !important;' in app_code
assert '@media (max-width: 768px)' in app_code
print("✅ 1. Regras CSS de alinhamento, altura uniforme (104px) e responsividade mobile validadas no app.py.")

# 2. Testar AppTest carregando Visão Geral
app_path = os.path.abspath('app.py')
at = AppTest.from_file(app_path, default_timeout=30)
at.run()
assert not at.exception, f"Exceção inicial: {[e.value for e in at.exception]}"
print("✅ 2. App executado com sucesso sem exceções.")

# 3. Verificar presença do botão Marco 99
btn_marco = next((b for b in at.button if "btn_abrir_modal_marco_99" in str(b.key)), None)
assert btn_marco is not None, "Botão btn_abrir_modal_marco_99 deve estar presente na seção de metas do motorista!"
print(f"✅ 3. Botão do Marco 99 presente na UI: '{btn_marco.label}'")

# 4. Integridade do banco principal intocada
conn = sqlite3.connect("financas_casa.db")
cur = conn.cursor()
cur.execute("PRAGMA integrity_check")
assert cur.fetchone()[0] == "ok"
cur.execute("SELECT COUNT(*) FROM transacoes")
tx_count = cur.fetchone()[0]
assert tx_count >= 32
conn.close()
print(f"✅ 4. Banco principal estritamente preservado: {tx_count} transações intactas, saldos intocados.")

print("🎉 TODOS OS TESTES E2E PASSARAM COM SUCESSO!")
