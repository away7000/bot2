import yaml
import os

def load_skill():
    path = "awp_skill/skill.md"
    
    if not os.path.exists(path):
        return None
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    return content
