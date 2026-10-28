import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

with open('app.py', 'r', encoding='utf-8') as f:
    app_text = f.read()

print("--- APP.PY SEARCH ---")
for line_no, line in enumerate(app_text.splitlines(), 1):
    lower = line.lower()
    if any(k in lower for k in ['meta antiga', 'obrigações antigas', 'obrigacoes antigas', 'planejamento antigo', 'planejamento novo', '2841', '2804', '2928', '236', 'paga leve', 'meta diária', 'meta diaria', 'necessidade_caixa']):
        print(f"Line {line_no}: {line.strip()[:140]}")
