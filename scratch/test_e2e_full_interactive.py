import sys
import os
from streamlit.testing.v1 import AppTest

sys.stdout.reconfigure(encoding='utf-8')

print("=== TESTE COMPLETO E2E COM APPTEST (INTERATIVO) ===")

app_path = os.path.abspath('app.py')
at = AppTest.from_file(app_path, default_timeout=30)

at.run()

if at.exception:
    print("❌ Erro na renderização inicial:")
    for ex in at.exception:
        print("  ->", ex.value)
    sys.exit(1)
print("✅ 1. Renderização Inicial (Visão Geral - Claro): 0 exceções!")

# 2. Teste do Tema Noturno
at.session_state["tema"] = "Noturno"
at.run()
if at.exception:
    print("❌ Erro no Tema Noturno:")
    for ex in at.exception:
        print("  ->", ex.value)
    sys.exit(1)
print("✅ 2. Tema Noturno: 0 exceções!")

# 3. Teste do Tema Claro
at.session_state["tema"] = "Claro"
at.run()
if at.exception:
    print("❌ Erro no Tema Claro:")
    for ex in at.exception:
        print("  ->", ex.value)
    sys.exit(1)
print("✅ 3. Tema Claro: 0 exceções!")

# 4. Teste de Metas: Hoje (padrão)
print("Radio de metas:", [r.value for r in at.radio])
# 5. Teste de Metas: Semana
for r in at.radio:
    if "Horizonte de Produção" in str(r.label):
        r.set_value("Semana")
at.run()
if at.exception:
    print("❌ Erro na Visão Semana:")
    for ex in at.exception:
        print("  ->", ex.value)
    sys.exit(1)
print("✅ 4. Visão Semana: 0 exceções!")

# 6. Teste de Metas: Mês
for r in at.radio:
    if "Horizonte de Produção" in str(r.label):
        r.set_value("Mês")
at.run()
if at.exception:
    print("❌ Erro na Visão Mês:")
    for ex in at.exception:
        print("  ->", ex.value)
    sys.exit(1)
print("✅ 5. Visão Mês: 0 exceções!")

# 7. Teste de Navegação para Planejamento & Metas
at.session_state["pagina_ativa"] = "🎯 Planejamento & Metas"
at.run()
if at.exception:
    print("❌ Erro na página Planejamento & Metas:")
    for ex in at.exception:
        print("  ->", ex.value)
    sys.exit(1)
print("✅ 6. Navegação para 🎯 Planejamento & Metas: 0 exceções!")

# 8. Retorno para Visão Geral
at.session_state["pagina_ativa"] = "Visão Geral"
at.run()
if at.exception:
    print("❌ Erro no retorno para Visão Geral:")
    for ex in at.exception:
        print("  ->", ex.value)
    sys.exit(1)
print("✅ 7. Retorno para Visão Geral: 0 exceções!")

print("\n🎉 TODOS OS TESTES INTERATIVOS DE RENDERIZAÇÃO PASSARAM COM SUCESSO!")
