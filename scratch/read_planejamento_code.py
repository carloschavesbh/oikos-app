with open('web_app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if '@app.get("/planejamento"' in line:
        print(''.join(lines[idx:idx+120]))
        break
