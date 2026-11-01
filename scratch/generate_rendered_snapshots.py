# -*- coding: utf-8 -*-
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
import web_app
from starlette.testclient import TestClient

BACKUP_DB = r"C:\Users\carlo\Downloads\OIKOS_BACKUP_PRE_REMODELACAO_20261101\database\financas_casa_backup_consistente_20261101.db"
web_app.DB_PATH = BACKUP_DB

client = TestClient(web_app.app)
out_dir = r"C:\Users\carlo\Downloads\OIKOS_BACKUP_PRE_REMODELACAO_20261101\capturas_telas\html_renderizados"
os.makedirs(out_dir, exist_ok=True)

telas = [
    ("01_visao_geral.html", "/"),
    ("02_extrato_lancamentos.html", "/lancamentos"),
    ("03_contas_e_cofrinhos.html", "/contas"),
    ("04_cartoes_credito.html", "/cartoes"),
    ("05_planejamento_metas.html", "/planejamento"),
    ("06_modulo_paga_leve.html", "/pagaleve"),
    ("07_oikos_drive.html", "/motorista"),
    ("08_missoes_semana.html", "/missoes"),
]

for filename, path in telas:
    resp = client.get(path)
    dest = os.path.join(out_dir, filename)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(resp.text)
    sz_kb = os.path.getsize(dest) / 1024
    print(f"[SNAPSHOT SALVO] {filename} ({sz_kb:.1f} KB) - HTTP {resp.status_code}")

print("\nTodos os snapshots HTML renderizados com dados reais preservados com sucesso!")

