from pathlib import Path
from html.parser import HTMLParser
import re
import json

class SimpleDOMParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []
        self.current_tag = None
        self.current_attrs = {}
        self.text_buffer = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        self.elements.append(('start', tag, attr_dict))

    def handle_endtag(self, tag):
        self.elements.append(('end', tag, {}))

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.elements.append(('text', text, {}))

def parse_bills_visao_geral():
    content = Path('Organizze/Organizze _ Visão geral.html').read_text(encoding='utf-8', errors='ignore')
    
    # Vamos encontrar blocos de contas a pagar e a receber
    # Regex para pegar trechos com ng-repeat="bill in billToPay.data...
    print("=== CONTAS A PAGAR / RECEBER EM VISÃO GERAL ===")
    pattern = r'<li[^>]*ng-repeat="bill in billToPay\.data\.(overdue|upcoming|today)[^"]*"[^>]*>(.*?)</li>'
    matches = re.findall(pattern, content, re.DOTALL)
    print(f"Total contas a pagar encontradas: {len(matches)}")
    for status, block in matches:
        # strip tags
        clean_text = re.sub(r'<[^>]+>', ' ', block)
        clean_text = ' '.join(clean_text.split())
        print(f"  [{status.upper()}] {clean_text}")

    pattern_rec = r'<li[^>]*ng-repeat="bill in billToReceive\.data\.upcoming[^"]*"[^>]*>(.*?)</li>'
    matches_rec = re.findall(pattern_rec, content, re.DOTALL)
    print(f"\nTotal contas a receber encontradas: {len(matches_rec)}")
    for block in matches_rec:
        clean_text = re.sub(r'<[^>]+>', ' ', block)
        clean_text = ' '.join(clean_text.split())
        print(f"  [A RECEBER] {clean_text}")

def parse_transactions_lancamentos():
    content = Path('Organizze/Organizze _ Lançamentos.html').read_text(encoding='utf-8', errors='ignore')
    print("\n=== TRANSAÇÕES EM LANÇAMENTOS.HTML ===")
    pattern = r'<tr[^>]*ng-repeat="item in transactions\.data\.transactions[^"]*"[^>]*>(.*?)</tr>'
    matches = re.findall(pattern, content, re.DOTALL)
    print(f"Total linhas de transações encontradas: {len(matches)}")
    for idx, block in enumerate(matches):
        clean_text = re.sub(r'<[^>]+>', ' | ', block)
        clean_text = ' '.join(clean_text.split())
        # enxugar pipes repetidos
        clean_text = re.sub(r'(\s*\|\s*)+', ' | ', clean_text)
        print(f"  #{idx+1}: {clean_text[:160]}")

parse_bills_visao_geral()
parse_transactions_lancamentos()
