import re
with open(r'voice bot1\voice_automation.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Look for lines that contain only Hindi/Bengali characters (potential bare identifiers)
        if stripped and re.match(r'^[\u0900-\u097F\u0980-\u09FF]+$', stripped):
            print(f'Line {i}: {repr(line)}')
