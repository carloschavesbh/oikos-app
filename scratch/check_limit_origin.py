import json, sys
sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\carlo\.gemini\antigravity-ide\brain\3a771703-985f-422d-8cbd-51eb28b65bc9\.system_generated\logs\transcript.jsonl'
with open(transcript_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        obj = json.loads(line)
        content = str(obj.get('content', ''))
        if '1200' in content or '1.200' in content:
            source = obj.get('source', '')
            step_type = obj.get('type', '')
            print(f"Line {i} | Source: {source} | Type: {step_type}")
            # print surrounding snippet
            idx = content.find('1200') if '1200' in content else content.find('1.200')
            start = max(0, idx - 100)
            end = min(len(content), idx + 100)
            print("Snippet:", content[start:end].replace('\n', ' '))
            print("-" * 50)
