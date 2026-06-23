"""Граф кода только собственного кода miro_vizor (без vendor/tests)."""
import sys
from pathlib import Path
sys.path.insert(0, 'miro_vizor/vendor/graphify')
from graphify.extract import collect_files, extract as extract_files
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.export import to_html

project = Path('miro_vizor')
all_files = collect_files(project)
# только собственный код miro_vizor, без vendor и tests
own = [f for f in all_files if 'vendor' not in str(f) and 'tests' not in str(f)]
print('own files:', len(own))
for f in own:
    print('  ', f)

extractions = []
for f in own:
    ext = extract_files([f])
    if ext.get('nodes'):
        extractions.append(ext)
combined = {
    'nodes': [n for e in extractions for n in e.get('nodes', [])],
    'edges': [e for ex in extractions for e in ex.get('edges', [])],
}
seen = set()
uniq = []
for n in combined['nodes']:
    if n['id'] not in seen:
        seen.add(n['id'])
        uniq.append(n)
combined['nodes'] = uniq
G = build_from_json(combined)
communities = cluster(G)
cohesion = score_all(G, communities)
print('nodes', G.number_of_nodes(), 'edges', G.number_of_edges(), 'communities', len(communities))

import networkx as nx
deg = sorted(G.degree, key=lambda x: -x[1])[:20]
print('TOP DEGREE NODES:')
for nid, d in deg:
    lbl = G.nodes[nid].get('label', nid)
    sf = G.nodes[nid].get('source_file', '')
    print('  %-30s deg=%3d src=%s' % (lbl, d, sf))
from collections import Counter
rels = Counter(d.get('relation', '') for _, _, d in G.edges(data=True))
print('relations:', dict(rels))
top_coh = sorted(cohesion.items(), key=lambda x: -x[1])[:6]
print('top cohesion:', top_coh)
to_html(G, communities, 'reports/graphify/code_graph_own.html')
print('saved reports/graphify/code_graph_own.html')

# сохраним данные для отчёта
import json
data = {
    'nodes': G.number_of_nodes(),
    'edges': G.number_of_edges(),
    'communities': len(communities),
    'relations': dict(rels),
    'top_degree': [{'label': G.nodes[nid].get('label', nid), 'degree': d, 'source_file': G.nodes[nid].get('source_file', '')} for nid, d in deg],
    'top_cohesion': [{'community': cid, 'cohesion': c} for cid, c in top_coh],
}
json.dump(data, open('reports/graphify/code_graph_stats.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('saved code_graph_stats.json')
