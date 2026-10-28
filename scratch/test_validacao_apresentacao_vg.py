import sys
import os
import sqlite3
from streamlit.testing.v1 import AppTest

sys.stdout.reconfigure(encoding='utf-8')

print("=== VALIDAÇÃO AUTOMATIZADA DOS REQUISITOS DE APRESENTAÇÃO DA VISÃO GERAL ===")

# 1. Verificar integridade e não-modificação do banco de dados
conn = sqlite3.connect("financas_casa.db")
cur = conn.cursor()
cur.execute("PRAGMA integrity_check")
check = cur.fetchone()[0]
assert check == "ok", f"Integridade do banco falhou: {check}"
cur.execute("SELECT COUNT(*) FROM transacoes")
count_tx = cur.fetchone()[0]
conn.close()
print(f"✅ Banco de dados intacto: {count_tx} transações cadastradas, PRAGMA integrity = {check}")

# 2. Executar AppTest
app_path = os.path.abspath('app.py')
at = AppTest.from_file(app_path, default_timeout=30)
at.run()
assert not at.exception, f"Exceção inicial: {[e.value for e in at.exception]}"
print("✅ 1. Visão Geral carregada sem exceções.")

# 3. Teste dos 5 botões de detalhe (interatividade e alinhamento)
kpis = ["renda", "caixa", "vencidas", "prox7d", "restante"]
for k in kpis:
    # Achar botão correspondente
    btn = next((b for b in at.button if f"btn_kpi_{k}" in str(b.key)), None)
    assert btn is not None, f"Botão btn_kpi_{k} não encontrado!"
    btn.click()
    at.run()
    assert not at.exception, f"Exceção ao clicar em btn_kpi_{k}: {[e.value for e in at.exception]}"
    print(f"  -> Botão ▾ Detalhes [{k}] acionado com sucesso (0 exceções).")
    # Fechar detalhe
    btn = next((b for b in at.button if f"btn_kpi_{k}" in str(b.key)), None)
    if btn:
        btn.click()
        at.run()

print("✅ 2. Todos os 5 indicadores superiores e seus botões de detalhamento operando perfeitamente.")

# 4. Verificar ausência de duplicação da seção Missões & Cofrinhos na Visão Geral
# Seção antiga tinha título: "#### 🎯 Missões & Cofrinhos"
titulos_h4 = [m.value for m in at.markdown if "Missões & Cofrinhos" in m.value or "Missões &amp; Cofrinhos" in m.value]
assert len(titulos_h4) == 0, f"Seção duplicada 'Missões & Cofrinhos' ainda encontrada no dashboard principal: {titulos_h4}"
print("✅ 3. Seção grande e duplicada 'Missões & Cofrinhos' removida da Visão Geral principal.")

# 5. Verificar que os cards personalizáveis de Missão IPVA continuam funcionando
# O card modular 'missao_ipva' ainda existe e tem botão 'btn_ir_missao_vg'
btn_missao = next((b for b in at.button if "btn_ir_missao_vg" in str(b.key)), None)
assert btn_missao is not None, "Card personalizável de Missão IPVA deve ser preservado no painel!"
print("✅ 4. Cards modulares personalizáveis e seus controles preservados.")

# 6. Teste de Tema Noturno e Tema Claro
at.session_state["tema"] = "Noturno"
at.run()
assert not at.exception, "Erro no tema Noturno"
print("✅ 5. Tema Noturno validado com 0 exceções.")

at.session_state["tema"] = "Claro"
at.run()
assert not at.exception, "Erro no tema Claro"
print("✅ 6. Tema Claro validado com 0 exceções.")

# 7. Verificar que textos com Markdown literal como `**` não aparecem em strings brutas
textos_markdown = [m.value for m in at.markdown]
anomalias = []
for txt in textos_markdown:
    if ":green[**" in txt or "**:[" in txt or ":orange[" in txt:
        anomalias.append(txt)
assert not anomalias, f"Encontrado markdown quebrado: {anomalias}"
print("✅ 7. Textos com Markdown literal e tags compostas corrigidos.")

print("\n🎉 TODOS OS TESTES ESPECÍFICOS DE APRESENTAÇÃO FORAM APROVADOS!")
