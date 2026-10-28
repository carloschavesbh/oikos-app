import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines = []
    def handle_data(self, data):
        t = data.strip()
        if t:
            self.lines.append(t)

def get_clean_lines(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    p = TextExtractor()
    p.feed(html)
    return p.lines

files = [
    "Organizze _ Cartões de Crédito.html",
    "Organizze _ Categorias.html",
    "Organizze _ Contas.html",
    "Organizze _ Lançamentos.html",
    "Organizze _ Limite de gastos.html",
    "Organizze _ Relatórios.html",
    "Organizze _ Visão geral.html"
]

print("=" * 80)
print("INVENTÁRIO COMPLETO DO CONTEÚDO VISÍVEL DOS 7 ARQUIVOS HTML DO ORGANIZZE")
print("=" * 80)

for fname in files:
    fpath = os.path.join("Organizze", fname)
    lines = get_clean_lines(fpath)
    print(f"\n📄 {fname}: {len(lines)} linhas de texto visível.")
    
    # Procura valores monetários (R$)
    money_lines = [l for l in lines if 'R$' in l]
    date_lines = [l for l in lines if re.search(r'\b\d{2}/\d{2}/\d{4}\b', l)]
    
    print(f"   • Valores monetários ({len(money_lines)}): {money_lines[:8]}")
    print(f"   • Datas completas ({len(date_lines)}): {date_lines[:8]}")
    
    # Amostra das primeiras 25 linhas relevantes
    print("   • Amostra de conteúdo:")
    for l in lines[10:30]:
        if l not in ("Organizze", "Painel", "Configurações", "Ajuda", "Sair", "|"):
            print(f"       - {l[:80]}")
