import json

d = json.load(open('outputs/five_agents_stub.json'))
turns = [t for r in d['rounds'] for p in r['phases'] for t in p['turns']]
print(f'Total turns: {len(turns)}')
for i, t in enumerate(turns):
    a = t['agent']
    msg = (t.get('message') or '')[:40]
    print(f'turn {i:3d}: a={a:10s} act={t["action"]:10s} msg={msg:40s} priv={t.get("is_private",False)}')
