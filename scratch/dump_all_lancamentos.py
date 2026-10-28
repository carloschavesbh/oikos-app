from pathlib import Path
import re
import json

content = Path('Organizze/Organizze _ Lançamentos.html').read_text(encoding='utf-8', errors='ignore')

pattern = r'<li[^>]*id="transaction-(\d+)"[^>]*>(.*?)(?=(?:<li[^>]*id="transaction-)|(?:</ul>)|(?:<!-- end ngRepeat: item in transactions\.data\.transactions))'
matches = re.findall(pattern, content, re.DOTALL)

parsed_txs = []
for tx_id, block in matches:
    # procurar por classe ou data-date
    # no HTML, vamos ver como a data e categoria estão marcadas
    # Vamos extrair todos os textos e classes
    lines = [s.strip() for s in re.sub(r'<[^>]+>', '\n', block).split('\n') if s.strip()]
    
    # Extrair se é paga ou prevista
    is_paid = "Despesa realizada" in block or "Receita realizada" in block or "transaction-paid" in block or "fa-check" in block
    is_overdue = "Conta vencida" in block or "is-overdue" in block
    
    # Extrair valor
    val_match = re.search(r'([+-]?\d{1,3}(?:\.\d{3})*,\d{2})', block)
    valor_str = val_match.group(1) if val_match else None
    
    parsed_txs.append({
        'id': tx_id,
        'lines': lines,
        'valor': valor_str,
        'is_overdue': is_overdue
    })

with open('scratch/organizze_lancamentos_extracted.json', 'w', encoding='utf-8') as f:
    json.dump(parsed_txs, f, indent=2, ensure_ascii=False)

print(f"Extracted {len(parsed_txs)} transactions to scratch/organizze_lancamentos_extracted.json")
for t in parsed_txs:
    print(f"ID {t['id']} | Valor: {t['valor']} | Linhas: {' // '.join(t['lines'][:6])}")
