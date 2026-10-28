import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re

def inspect_file_chunks(filename, query_list):
    print(f"\n=======================================================")
    print(f"ARQUIVO: {filename}")
    print(f"=======================================================")
    with open(os.path.join("Organizze", filename), "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    for q in query_list:
        print(f"\n--- Busca por: '{q}' ---")
        matches = list(re.finditer(re.escape(q), content, re.IGNORECASE))
        print(f"Total de ocorrências: {len(matches)}")
        for i, m in enumerate(matches[:5]):
            start = max(0, m.start() - 150)
            end = min(len(content), m.end() + 250)
            snip = content[start:end]
            clean = re.sub(r'<[^>]+>', ' ', snip)
            clean = re.sub(r'\s+', ' ', clean).strip()
            print(f"[{i+1}] {clean}")

# 1. Cartões de Crédito
inspect_file_chunks("Organizze _ Cartões de Crédito.html", ["Cartão Inter Aparecida", "Inter", "Aparecida", "Mercado Pago", "limite", "fatura"])

# 2. Contas
inspect_file_chunks("Organizze _ Contas.html", ["Mercado Pago", "Carteira", "Dinheiro", "saldo", "Inter"])

# 3. Visão Geral
inspect_file_chunks("Organizze _ Visão geral.html", ["Copasa", "WellHub", "Audible", "BV", "fatura", "Cartão", "Inter"])

# 4. Lançamentos
inspect_file_chunks("Organizze _ Lançamentos.html", ["01/08/2026", "10/08/2026", "17/10/2026", "WellHub", "Copasa"])
