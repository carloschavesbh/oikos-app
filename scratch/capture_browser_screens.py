import os
import sys
import time
import subprocess
import threading
import uvicorn
import urllib.request

sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
os.environ['DATABASE_PATH'] = 'financas_remodelacao.db'

artifact_dir = r"C:\Users\carlo\.gemini\antigravity\brain\895538f4-4f0c-45d1-addf-bc17659108ba"
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

from web_app import app

class ServerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        config = uvicorn.Config(app, host="127.0.0.1", port=8009, log_level="warning")
        self.server = uvicorn.Server(config)
        self.daemon = True

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True

print("Iniciando servidor temporário na porta 8009...")
srv = ServerThread()
srv.start()

# Aguardar inicialização
for i in range(20):
    try:
        urllib.request.urlopen("http://127.0.0.1:8009/", timeout=1)
        print("Servidor respondendo na porta 8009!")
        break
    except Exception:
        time.sleep(0.5)

# 1. Capturar Aba Renda Familiar
out_renda = os.path.join(artifact_dir, "screenshot_renda_familiar.png")
url_renda = "http://127.0.0.1:8009/planejamento#tab-renda"
print(f"Capturando {url_renda}...")
cmd_renda = [
    chrome_path,
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--hide-scrollbars",
    "--window-size=1280,1100",
    f"--screenshot={out_renda}",
    url_renda
]
subprocess.run(cmd_renda, check=True)
print(f"✓ Screenshot salva em: {out_renda}")

# 2. Capturar Aba Calendário Anual
out_cal = os.path.join(artifact_dir, "screenshot_calendario_anual.png")
url_cal = "http://127.0.0.1:8009/planejamento#tab-calendario"
print(f"Capturando {url_cal}...")
cmd_cal = [
    chrome_path,
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--hide-scrollbars",
    "--window-size=1280,1100",
    f"--screenshot={out_cal}",
    url_cal
]
subprocess.run(cmd_cal, check=True)
print(f"✓ Screenshot salva em: {out_cal}")

srv.stop()
print("Servidor finalizado. Capturas concluídas com sucesso!")
