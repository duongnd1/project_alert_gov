"""Dedup data.json by game ID"""
import json

with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Before: {len(data)} games")

seen = set()
unique = []
dupes = []
for g in data:
    gid = g.get("id", "")
    if gid and gid in seen:
        dupes.append(g.get("name", "?"))
        continue
    if gid:
        seen.add(gid)
    unique.append(g)

if dupes:
    print(f"Duplicates removed: {dupes}")
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)
    print(f"After: {len(unique)} games")
else:
    print("No duplicates found.")
