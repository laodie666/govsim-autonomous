import json

d = json.load(open('outputs/five_agents_stub.json'))
agent_names = [n.lower() for n in d['config']['agents']['names']]
print('Agents:', agent_names)

# Build flat turns
turns = []
for r in d['rounds']:
    for p in r['phases']:
        for t in p['turns']:
            t['_round'] = r['round']
            t['_phase'] = p['phase']
            turns.append(t)

print(f'Total turns: {len(turns)}')

for i in range(0, len(turns)):
    t = turns[i]
    a = t['agent']
    msg = (t['message'] or '')[:40]
    print(f'turn {i:3d}: agent={a:10s} action={t["action"]:10s} msg={msg:40s} private={t["is_private"]}')
