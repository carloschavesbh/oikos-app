# -*- coding: utf-8 -*-
import os
import sys
import time
import shutil
import subprocess
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DB = r"C:\Users\carlo\Downloads\OIKOS_BACKUP_PRE_REMODELACAO_20261101\database\financas_casa_backup_consistente_20261101.db"
TEMP_DB = os.path.join(BASE_DIR, "temp_screenshots.db")
SHOTS_DIR = r"C:\Users\carlo\Downloads\OIKOS_BACKUP_PRE_REMODELACAO_20261101\capturas_telas"
os.makedirs(SHOTS_DIR, exist_ok=True)

shutil.copy2(BACKUP_DB, TEMP_DB)

PORT = 8009
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_PATH):
    EDGE_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# Script auxiliar para iniciar uvicorn apontando para TEMP_DB
runner_code = f"""
import os, sys
sys.path.insert(0, r"{BASE_DIR}")
import web_app
web_app.DB_PATH = r"{TEMP_DB}"
import uvicorn
uvicorn.run(web_app.app, host="127.0.0.1", port={PORT}, log_level="warning")
"""

runner_file = os.path.join(BASE_DIR, "scratch", "_runner_shots.py")
with open(runner_file, "w", encoding="utf-8") as f:
    f.write(runner_code)

print(f"Iniciando servidor temporário na porta {PORT}...")
proc = subprocess.Popen([sys.executable, runner_file])

# Aguardar servidor ficar disponível
server_ready = False
for _ in range(30):
    time.sleep(0.5)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1) as resp:
            if resp.status == 200:
                server_ready = True
                break
    except Exception:
        pass

if not server_ready:
    print("ERRO: O servidor temporário não respondeu a tempo.")
    proc.terminate()
    if os.path.exists(TEMP_DB): os.remove(TEMP_DB)
    sys.exit(1)

print("Servidor temporário pronto. Capturando telas com navegador headless...")

telas = [
    ("01_visao_geral.png", f"http://127.0.0.1:{PORT}/"),
    ("02_extrato_lancamentos.png", f"http://127.0.0.1:{PORT}/lancamentos"),
    ("03_contas_e_cofrinhos.png", f"http://127.0.0.1:{PORT}/contas"),
    ("04_cartoes_credito.png", f"http://127.0.0.1:{PORT}/cartoes"),
    ("05_planejamento_metas.png", f"http://127.0.0.1:{PORT}/planejamento"),
    ("06_modulo_paga_leve.png", f"http://127.0.0.1:{PORT}/pagaleve"),
    ("07_oikos_drive.png", f"http://127.0.0.1:{PORT}/motorista"),
    ("08_missoes_semana.png", f"http://127.0.0.1:{PORT}/missoes"),
]

for filename, url in telas:
    out_path = os.path.join(SHOTS_DIR, filename)
    cmd = [
        EDGE_PATH,
        "--headless",
        "--disable-gpu",
        f"--screenshot={out_path}",
        "--window-size=1280,900",
        url
    ]
    try:
        subprocess.run(cmd, check=True, timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sz = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        print(f"  [OK] {filename} ({sz / 1024:.1f} KB)")
    except Exception as e:
        print(f"  [FALHA] {filename}: {e}")

# Encerramento e limpeza
print("Encerrando servidor temporário...")
proc.terminate()
proc.wait()
if os.path.exists(runner_file):
    os.remove(runner_file)
if os.path.exists(TEMP_DB):
    os.remove(TEMP_DB)

print(f"Todas as capturas foram salvas em: {SHOTS_DIR}")

