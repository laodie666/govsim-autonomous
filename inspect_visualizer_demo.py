import json

d = json.load(open('outputs/visualizer_demo.json'))
turns = [t for r in d['rounds'] for p in r['phases'] for t in p['turns']]
print(f'Total turns: {len(turns)}')
print(f'Agents: {d["config"]["agents"]["names"]}')
for i, t in enumerate(turns):
    a = t['agent']
    msg = (t.get('message') or '')[:50]
    if t['action'] != 'pass':
        print(f'turn {i:3d}: a={a:10s} act={t["action"]:10s} msg={msg:50s} priv={t.get("is_private",False)}')
