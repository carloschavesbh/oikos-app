import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re
from html.parser import HTMLParser

class SimpleHTMLSummary(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.tags = set()
        self.table_count = 0
        self.text_chunks = []
        self.scripts = []
        self.in_script = False
        self.current_script = []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        if tag == "title":
            self.in_title = True
        elif tag == "table":
            self.table_count += 1
        elif tag == "script":
            self.in_script = True
            self.current_script = []

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "script":
            self.in_script = False
            self.scripts.append("".join(self.current_script))

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.in_script:
            self.current_script.append(data)
        else:
            text = data.strip()
            if text:
                self.text_chunks.append(text)

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
print("INVENTÁRIO E AUDITORIA DETALHADA DOS ARQUIVOS HTML DO ORGANIZZE")
print("=" * 80)

for fname in files:
    fpath = os.path.join("Organizze", fname)
    if not os.path.exists(fpath):
        print(f"Arquivo não encontrado: {fpath}")
        continue
    size = os.path.getsize(fpath)
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        html_content = f.read()

    parser = SimpleHTMLSummary()
    try:
        parser.feed(html_content)
    except Exception as e:
        pass

    title = parser.title.strip() if parser.title else "Sem título"
    print(f"\n📄 ARQUIVO: {fname} ({size:,} bytes)")
    print(f"   Título da Página: {title}")
    print(f"   Total de tabelas HTML: {parser.table_count}")

    # Extrai trechos de scripts com gon ou window
    gon_vars = []
    for s in parser.scripts:
        if "gon." in s:
            for line in s.splitlines():
                if "gon." in line:
                    gon_vars.append(line.strip())

    if gon_vars:
        print(f"   Variáveis 'gon' (dados embutidos do backend Rails): {len(gon_vars)}")
        for g in gon_vars[:8]:
            print(f"     • {g[:120]}")

    # Analisa texto visível e termos chave
    texto_total = " ".join(parser.text_chunks)
    has_cartoes = len(re.findall(r'cart[aã]o|fatura|limite', texto_total, re.I))
    has_contas = len(re.findall(r'saldo|banco|conta', texto_total, re.I))
    has_transacoes = len(re.findall(r'lan[cç]amento|transa[cç][aã]o|receita|despesa', texto_total, re.I))
    has_valores = re.findall(r'R\$\s*[\d\.,]+', texto_total)
    has_datas = re.findall(r'\b\d{2}/\d{2}/\d{4}\b|\b\d{2}/\d{2}\b', texto_total)

    print(f"   Elementos de conteúdo extraíveis:")
    print(f"     - Valores monetários encontrados: {len(has_valores)} (Exemplos: {has_valores[:5]})")
    print(f"     - Datas encontradas: {len(has_datas)} (Exemplos: {has_datas[:5]})")
    print(f"     - Ocorrências de termos: Cartão ({has_cartoes}), Contas ({has_contas}), Lançamentos ({has_transacoes})")

    
    # Textos específicos de interesse
    has_cartoes = bool(re.search(r'cart[aã]o|fatura|limite', html_content, re.I))
    has_contas = bool(re.search(r'saldo|banco|conta', html_content, re.I))
    has_transacoes = bool(re.search(r'lan[cç]amento|transa[cç][aã]o|receita|despesa', html_content, re.I))
    has_recorrente = bool(re.search(r'recorrente|fixa|repetir', html_content, re.I))
    has_parcelamento = bool(re.search(r'parcela|\d+/\d+', html_content, re.I))
    
    print(f"   Conteúdo temático detectado:")
    print(f"     - Cartões/Faturas: {has_cartoes}")
    print(f"     - Contas/Saldos: {has_contas}")
    print(f"     - Lançamentos/Transações: {has_transacoes}")
    print(f"     - Recorrência/Fixas: {has_recorrente}")
    print(f"     - Parcelas: {has_parcelamento}")

