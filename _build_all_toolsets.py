#!/usr/bin/env python3
import re
from pathlib import Path

SKILLS = Path("/workspace/skills-general/skills")
TOOLS = Path("/workspace/AgentToolStore/toolsets")
DONE = {"pdf","xlsx","docx","pptx","verify","batch","simplify","lorem-ipsum"}

BUILT = []

for sf in sorted(SKILLS.rglob("SKILL.md")):
    name = sf.parent.name
    if name in DONE:
        continue
    
    content = sf.read_text()
    desc = re.search(r'^description:\s*(.+)$', content, re.MULTILINE)
    short = desc.group(1) if desc else name
    
    ts = name + "-toolkit"
    td = TOOLS / ts
    td.mkdir(parents=True, exist_ok=True)
    
    # doc.md = full skill content
    (td / "doc.md").write_text("# " + name + "\n\n" + content)
    
    # toolset.py = minimal code
    sep = "=" * (len(ts) + 4)
    code = '"""' + ts + " - " + short + "\n" + sep + '"""\n\n'
    code += "from pathlib import Path\n\n"
    code += "try:\n    from toolstore.toolset import tool\n"
    code += "except ImportError:\n    def tool(fn):\n        return fn\n\n\n"
    code += "@tool\n"
    code += "def get_guidance(*, topic: str = \"\") -> dict:\n"
    code += '    """Return best practices for ' + name + '.\n\n'
    code += "    Args:\n        topic: Optional sub-topic.\n"
    code += "    Returns:\n        dict with guidelines.\n"
    code += '    """\n'
    code += "    return {\n"
    code += '        "toolset": "' + ts + '",\n'
    code += '        "guidance": "See doc.md for full ' + name + ' guidance.",\n'
    code += '        "topic": topic if topic else None,\n    }\n'
    
    (td / "toolset.py").write_text(code)
    BUILT.append(ts)

print("Built " + str(len(BUILT)) + " toolsets:")
for b in BUILT:
    print("  OK " + b)
