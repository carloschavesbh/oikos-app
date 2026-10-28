import os
import glob
from pathlib import Path

export_dir = Path("Organizze") / "Exportações"
if not export_dir.exists():
    # tentar encontrar qualquer pasta com 'Export'
    for p in Path("Organizze").iterdir():
        if "Export" in p.name:
            export_dir = p
            break

print("Diretório de exportações:", export_dir)
files = list(export_dir.glob("*.xls"))
print(f"Total arquivos encontrados: {len(files)}")
for f in sorted(files):
    with open(f, 'rb') as fp:
        magic = fp.read(16)
    print(f"{f.name} ({f.stat().st_size} bytes) - Magic bytes: {magic}")
