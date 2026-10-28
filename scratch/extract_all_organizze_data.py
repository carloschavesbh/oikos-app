import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re
import json

print("=" * 80)
print("EXTRAÇÃO DETALHADA DE CONTAS, CARTÕES E LANÇAMENTOS DO ORGANIZZE")
print("=" * 80)

# 1. CONTAS em Organizze _ Contas.html e Visão geral.html
print("\n--- 1. CONTAS BANCÁRIAS ENCONTRADAS ---")
with open("Organizze/Organizze _ Contas.html", "r", encoding="utf-8", errors="ignore") as f:
    html_contas = f.read()

# Procura blocos de contas
# No Organizze, as contas aparecem com nomes e saldos
contas_raw = re.findall(r'<div class="[^"]*account[^"]*"[^>]*>(.*?)</div>', html_contas, re.DOTALL)
print(f"Blocos de contas encontrados em Contas.html: {len(contas_raw)}")

# Procura nomes de contas e saldos em Contas.html e Visão Geral
with open("Organizze/Organizze _ Visão geral.html", "r", encoding="utf-8", errors="ignore") as f:
    html_vg = f.read()

contas_vg = re.findall(r'<span class="account-name[^"]*"[^>]*>(.*?)</span>.*?<span class="amount[^"]*"[^>]*>(.*?)</span>', html_vg, re.DOTALL)
if not contas_vg:
    # Procura via ng-binding próximo a account
    contas_vg = re.findall(r'<div class="account-item[^"]*"[^>]*>(.*?)</div>', html_vg, re.DOTALL)

print(f"Itens de conta em Visão Geral: {len(contas_vg)}")
for c in contas_vg:
    c_clean = re.sub(r'<[^>]+>', ' ', c)
    c_clean = re.sub(r'\s+', ' ', c_clean).strip()
    print("  Conta:", c_clean[:120])

# 2. CARTÕES DE CRÉDITO em Cartões de Crédito.html e Visão Geral
print("\n--- 2. CARTÕES DE CRÉDITO ENCONTRADOS ---")
with open("Organizze/Organizze _ Cartões de Crédito.html", "r", encoding="utf-8", errors="ignore") as f:
    html_cartoes = f.read()

cards_blocks = re.findall(r'<div class="[^"]*credit-card[^"]*"[^>]*>(.*?)</div>', html_cartoes, re.DOTALL)
print(f"Blocos de cartão em Cartões de Crédito.html: {len(cards_blocks)}")

# Procura por Inter, Aparecida, etc. no HTML de cartões
for match in re.finditer(r'(Inter|Aparecida|Mercado Pago|Nubank|Visa|Mastercard)', html_cartoes, re.I):
    start = max(0, match.start() - 100)
    end = min(len(html_cartoes), match.end() + 150)
    snip = re.sub(r'<[^>]+>', ' ', html_cartoes[start:end])
    snip = re.sub(r'\s+', ' ', snip).strip()
    print("  Trecho Cartão:", snip)
    break

# Cartões na Visão Geral
cards_vg = re.findall(r'<div class="credit-card-item[^"]*"[^>]*>(.*?)</div>', html_vg, re.DOTALL)
print(f"Itens de cartão em Visão Geral: {len(cards_vg)}")
for c in cards_vg:
    c_clean = re.sub(r'<[^>]+>', ' ', c)
    c_clean = re.sub(r'\s+', ' ', c_clean).strip()
    print("  Cartão VG:", c_clean[:140])

# 3. LANÇAMENTOS em Lançamentos.html
print("\n--- 3. LANÇAMENTOS EM Organizze _ Lançamentos.html ---")
with open("Organizze/Organizze _ Lançamentos.html", "r", encoding="utf-8", errors="ignore") as f:
    html_lanc = f.read()

# Procura linhas de transações
# No Organizze, linhas são <tr class="transaction-row" ou <div class="transaction...
trans_matches = re.findall(r'<div class="[^"]*transaction-cell[^"]*"[^>]*>(.*?)</div>', html_lanc, re.DOTALL)
print(f"Células de transação encontradas: {len(trans_matches)}")

# Procura padrões de data, descrição, categoria e valor
# Ex: 10/10/2026 ... R$ 100,00
linhas_lanc = re.findall(r'(\d{2}/\d{2}/\d{4}|\d{2}/\d{2})\s*<.*?class="description[^"]*"[^>]*>(.*?)<.*?class="category[^"]*"[^>]*>(.*?)<.*?class="amount[^"]*"[^>]*>(.*?)<', html_lanc, re.DOTALL)
print(f"Linhas estruturadas com regex específico: {len(linhas_lanc)}")

# Vamos fazer uma varredura por blocos de transação no HTML
# Procura por ng-repeat com transaction
blocos_t = re.findall(r'class="[^"]*transaction-item[^"]*"[^>]*>(.*?)<!-- end ngRepeat: item in transactions', html_lanc, re.DOTALL)
print(f"Blocos transaction-item: {len(blocos_t)}")

# Vamos varrer todo texto em busca de lançamentos (data + texto + valor)
padrao_geral = re.findall(r'(\d{2}/\d{2}/\d{4})\s*([^<]+?)\s*(R\$\s*[\d\.,]+)', html_lanc)
print(f"Padrões gerais (Data Descrição R$): {len(padrao_geral)}")
for p in padrao_geral[:15]:
    print(f"  • {p[0]} | {p[1].strip()[:40]} | {p[2]}")

# 4. CONTAS A PAGAR / A RECEBER em Visão Geral
print("\n--- 4. CONTAS A PAGAR / A RECEBER EM VISÃO GERAL ---")
bills = re.findall(r'<div class="bill-item[^"]*"[^>]*>(.*?)</div>', html_vg, re.DOTALL)
if not bills:
    bills = re.findall(r'<div [^>]*class="[^"]*bill-[^"]*"[^>]*>(.*?)</div>', html_vg, re.DOTALL)
print(f"Contas em Visão Geral: {len(bills)}")
for b in bills:
    b_clean = re.sub(r'<[^>]+>', ' ', b)
    b_clean = re.sub(r'\s+', ' ', b_clean).strip()
    print("  Conta a pagar/receber:", b_clean[:140])

# Procura todas as ocorrências de contas vencidas ou a vencer em Visão Geral
contas_venc_vg = re.findall(r'class="bill-title[^"]*"[^>]*>(.*?)</span>.*?class="bill-date[^"]*"[^>]*>(.*?)</span>.*?class="amount[^"]*"[^>]*>(.*?)</span>', html_vg, re.DOTALL)
print(f"Contas mapeadas diretamente por título/data/valor: {len(contas_venc_vg)}")
for cv in contas_venc_vg:
    t = re.sub(r'<[^>]+>', '', cv[0]).strip()
    d = re.sub(r'<[^>]+>', '', cv[1]).strip()
    v = re.sub(r'<[^>]+>', '', cv[2]).strip()
    print(f"  • {d} | {t} | {v}")
