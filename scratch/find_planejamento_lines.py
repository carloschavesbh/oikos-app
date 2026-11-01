with open('web_app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = None
end_idx = None

for idx, line in enumerate(lines):
    if '@app.get("/planejamento"' in line:
        start_idx = idx
    if start_idx is not None and 'return templates.TemplateResponse(' in line and idx + 2 < len(lines) and 'planejamento.html' in lines[idx+2]:
        end_idx = idx
        break

print(f"start_idx: {start_idx}, end_idx: {end_idx}")
if end_idx:
    print("Linhas anteriores ao retorno:")
    print(''.join(lines[end_idx-20:end_idx+35]))
