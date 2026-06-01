import json, sys
import networkx as nx
from networkx.readwrite import json_graph
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

data = json.loads(Path('graphify-out/graph.json').read_text(encoding='utf-8'))
G = json_graph.node_link_graph(data, edges='links')

term = 'Carol Sierra'
term_lower = term.lower()

scored = sorted(
    [(sum(1 for w in term_lower.split() if w in G.nodes[n].get('label','').lower()), n)
     for n in G.nodes()],
    reverse=True
)

if not scored or scored[0][0] == 0:
    print(f'No node matching {term!r}')
    sys.exit(0)

nid = scored[0][1]
data_n = G.nodes[nid]
print(f'NODE: {data_n.get("label", nid)}')
print(f'  source: {data_n.get("source_file","unknown")}')
print(f'  type: {data_n.get("file_type","unknown")}')
rationale = data_n.get('rationale', '')
if rationale:
    print(f'  rationale: {rationale}')
print(f'  degree: {G.degree(nid)}')
print()
print('CONNECTIONS:')
for neighbor in G.neighbors(nid):
    edge_data = G[nid][neighbor]
    edge = next(iter(edge_data.values()), {}) if isinstance(G, nx.MultiGraph) else edge_data
    nlabel = G.nodes[neighbor].get('label', neighbor)
    rel = edge.get('relation', '')
    conf = edge.get('confidence', '')
    src_file = G.nodes[neighbor].get('source_file', '')
    print(f'  --{rel}--> {nlabel} [{conf}] (src: {src_file})')
