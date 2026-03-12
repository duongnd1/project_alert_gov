code = """
with open('monitor.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_marker = "# ============================================================\\n# AI ARTICLE READER (NODE.JS PIPELINE)\\n# ============================================================\\nimport subprocess"
end_marker = "@bot.message_handler(commands=['stats'])"

start_idx = text.find(start_marker)
end_idx = text.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"Markers not found. Start: {start_idx}, End: {end_idx}")
else:
    replacement = '''# ============================================================
# AI ARTICLE READER (NODE.JS PIPELINE) - Processed via ai_reader_feature.py
# ============================================================
from ai_reader_feature import register_ai_handlers
register_ai_handlers(bot)

'''
    new_text = text[:start_idx] + replacement + text[end_idx:]
    with open('monitor.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Success")
"""

with open('update_monitor.py', 'w', encoding='utf-8') as f:
    f.write(code)
