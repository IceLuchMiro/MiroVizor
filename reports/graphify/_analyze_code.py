import sys
sys.path.insert(0, 'miro_vizor/vendor/graphify')
from miro_vizor.graphify_adapter import build_code_graph
g = build_code_graph('miro_vizor')
G = g['graph']
import networkx as nx
deg = sorted(G.degree, key=lambda x: -x[1])[:15]
print('TOP DEGREE NODES:')
for nid, d in deg:
    lbl = G.nodes[nid].get('label', nid)
    ft = G.nodes[nid].get('file_type', '')
    sf = G.nodes[nid].get('source_file', '')
    print('  %-30s deg=%3d type=%s src=%s' % (lbl, d, ft, sf))
print()
print('nodes', G.number_of_nodes(), 'edges', G.number_of_edges())
com = g['communities']
print('communities', len(com))
coh = g['cohesion']
top_coh = sorted(coh.items(), key=lambda x: -x[1])[:5]
print('top cohesion:', top_coh)
from collections import Counter
rels = Counter(d.get('relation', '') for _, _, d in G.edges(data=True))
print('relations:', dict(rels))
# files covered
files = sorted(set(nx.get_node_attributes(G, 'source_file').values()))
files = [f for f in files if f]
print('files covered:', len(files))
for f in files[:25]:
    print('  ', f)
