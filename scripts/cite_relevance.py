"""Heuristic cite relevance (--strict: use the type/function head, e.g. DeepModule from DeepModule.Probe, and skip generic words): a prose line/paragraph with <cite>f:a-b</cite> is 'relevant' if at least one
backticked identifier (>=4 chars, not a path/command) from the same line appears in f[a-3:b+3]."""
import re, sys, pathlib, json
STRICT = '--strict' in sys.argv
args = [a for a in sys.argv[1:] if a != '--strict']
hb, src = pathlib.Path(args[0]), pathlib.Path(args[1])
# words that appear almost everywhere and prove nothing about the cited range
GENERIC = {'probe', 'probes', 'probe_exporter', 'config', 'error', 'errors', 'context', 'result', 'results', 'string',
           'handler', 'server', 'client', 'router', 'request', 'response', 'model', 'models', 'service', 'services',
           'settings', 'main', 'value', 'target', 'status', 'detail', 'fastapi', 'router', 'false', 'true', 'none'}
content = next(hb.rglob('content'))
CITE = re.compile(r'<cite>([^:<]+):(\d+)(?:-(\d+))?</cite>')
tot = rel = 0; bad = []
for p in content.rglob('*.md'):
    t = re.sub(r'```.*?```', '', p.read_text(), flags=re.S)
    lines = t.split('\n')
    for i, line in enumerate(lines):
        cites = CITE.findall(line)
        if not cites: continue
        text = line if CITE.sub('', line).strip() else (lines[i-1] if i else '')
        ids = {x for x in re.findall(r'`([A-Za-z_][A-Za-z0-9_.]{3,})`', text) if '/' not in x and not x.endswith(('.py','.go','.md','.yml','.rst','.json','.sql','.toml'))}
        if STRICT:
            ids = {x.split('.')[0] for x in ids}
            ids = {x for x in ids if len(x) >= 5 and x.lower() not in GENERIC}
        else:
            ids = {x.split('.')[-1] for x in ids if len(x.split('.')[-1]) >= 4}
        if not ids: continue
        tot += 1
        hit = False
        for f, a, b in cites:
            fp = src / f.strip()
            if not fp.is_file(): continue
            L = fp.read_text(errors='replace').split('\n'); a = int(a); b = int(b or a)
            win = '\n'.join(L[max(0, a-4):b+3])
            if any(x in win for x in ids): hit = True; break
        if hit: rel += 1
        else: bad.append({'page': str(p.relative_to(content)), 'ids': sorted(ids)[:4], 'cites': [f'{f}:{a}-{b or a}' for f,a,b in cites][:2]})
print(json.dumps({'checked': tot, 'relevant': rel, 'relevant_pct': round(100*rel/max(tot,1),1), 'examples': bad[:8]}, ensure_ascii=False))
