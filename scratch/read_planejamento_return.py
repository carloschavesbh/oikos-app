with open('web_app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

found = False
for idx, line in enumerate(lines):
    if '@app.get("/planejamento"' in line:
        found = True
    if found and 'return templates.TemplateResponse' in line:
        print(''.join(lines[idx-30:idx+25]))
        break
