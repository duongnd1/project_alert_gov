import json
import re

def analyze_rsc():
    with open("rsc_response.txt", "r", encoding="utf-8") as f:
        content = f.read()
        
    # RSC format is line-based: ID:Type[Args]
    lines = content.split('\n')
    
    print(f"Total lines: {len(lines)}")
    
    for line in lines:
        if not line: continue
        
        # Try to find arrays or objects
        try:
            # simple heuristic: look for JSON-like parts
            if '[' in line or '{' in line:
                # remove the prefix "ID:Type"
                params = line.split(':', 1)[1] if ':' in line else line
                
                # Check for "GAMOTA"
                if "GAMOTA" in line:
                    print("\n--- Found GAMOTA in line ---")
                    print(line[:500] + "..." if len(line) > 500 else line)
                    
                    # Try to extract the list of games
                    # Look for known fields like "Giấy phép", "Ngày cấp"
                    if "Giấy phép" in line:
                         print("✅ Found 'Giấy phép'! Data is here.")
                         
        except Exception as e:
            pass

if __name__ == "__main__":
    analyze_rsc()
