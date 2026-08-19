from pathlib import Path

p = Path('src/cli.c')
s = p.read_text()
old = '''    if (!strcmp(kind, "DEP")) return "dependency";
    if (!strcmp(kind, "CC")) return "compile";'''
new = '''    if (!strcmp(kind, "DEP")) return "dependency";
    if (!strcmp(kind, "GEN")) return "generate";
    if (!strcmp(kind, "WHY")) return "reason";
    if (!strcmp(kind, "CC")) return "compile";'''
if s.count(old) != 1:
    raise SystemExit(f'step formatter match count: {s.count(old)}')
p.write_text(s.replace(old, new, 1))
print('explain/generator CLI records enabled')
