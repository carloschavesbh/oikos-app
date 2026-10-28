import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re
import json

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
print("ANÁLISE DE PROFUNDIDADE DOS ARQUIVOS ORGANIZZE")
print("=" * 80)

for fname in files:
    fpath = os.path.join("Organizze", fname)
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    
    print(f"\n================================================================================")
    print(f"ARQUIVO: {fname} ({len(html):,} caracteres)")
    print(f"================================================================================")
    
    # 1. Procura ocorrências de cartões específicos (Inter, Mercado Pago, Nubank, etc.)
    cartoes_m = re.findall(r'(Inter|Aparecida|Mercado Pago|Nubank|Mastercard|Visa|Elo|Hipercard)', html, re.I)
    print(f"Menções a cartões/bancos: {set(cartoes_m)}")
    
    # 2. Procura linhas de transações ou lançamentos
    # Procura blocos com data, descrição e valor
    # No Organizze Angular, transações geralmente têm ng-repeat="transaction in ..." ou classes como transaction-item, transaction-row
    ng_repeats = re.findall(r'ng-repeat=["\']([^"\']+)["\']', html)
    print(f"ng-repeats encontrados ({len(ng_repeats)}): {set(ng_repeats)}")
    
    # Procura valores monetários com contexto
    money_matches = list(re.finditer(r'R\$\s*[\d\.,]+', html))
    print(f"Total de valores monetários: {len(money_matches)}")
    if money_matches:
        for m in money_matches[:10]:
            start = max(0, m.start() - 60)
            end = min(len(html), m.end() + 60)
            snip = re.sub(r'<[^>]+>', ' ', html[start:end])
            snip = re.sub(r'\s+', ' ', snip).strip()
            print(f"   • {snip}")
            
    # Procura datas com contexto
    date_matches = list(re.finditer(r'\b\d{2}/\d{2}/\d{4}\b', html))
    print(f"Total de datas completas (dd/mm/aaaa): {len(date_matches)}")
    if date_matches:
        for dm in date_matches[:10]:
            start = max(0, dm.start() - 60)
            end = min(len(html), dm.end() + 60)
            snip = re.sub(r'<[^>]+>', ' ', html[start:end])
            snip = re.sub(r'\s+', ' ', snip).strip()
            print(f"   📅 {snip}")
            
    # Procura se há JSON embutido
    json_scripts = re.findall(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    print(f"Scripts JSON encontrados: {len(json_scripts)}")
    
    # Procura palavras-chave de parcelamento
    parcelas = re.findall(r'\b\d{1,2}/\d{1,2}\b', html)
    print(f"Menções a parcelas (ex: 1/4, 2/12): {set(parcelas[:15])}")
