"""Compare two KiCad netlists by connectivity (which ref.pin belong together), ignoring net names."""
import sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import sexpr

def groups(path):
    t = sexpr.parse(open(path, encoding="utf-8").read())
    nets = sexpr.first(t, "nets")
    out = {}
    for n in sexpr.find(nets, "net"):
        name = sexpr.first(n, "name")[1]
        nodes = frozenset(f'{sexpr.first(x, "ref")[1]}.{sexpr.first(x, "pin")[1]}' for x in sexpr.find(n, "node"))
        out[nodes] = name
    return out

a, b = groups(sys.argv[1]), groups(sys.argv[2])
ignore = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else set()
strip = lambda g: frozenset(p for p in g if p not in ignore and not p.startswith("#"))
A = {strip(g): n for g, n in a.items() if len(strip(g)) > 0}
B = {strip(g): n for g, n in b.items() if len(strip(g)) > 0}
only_a = [(n, sorted(g)) for g, n in A.items() if g not in B]
only_b = [(n, sorted(g)) for g, n in B.items() if g not in A]
print(f"nets: old {len(A)}, new {len(B)}, identical {len(set(A) & set(B))}")
for n, g in only_a:
    print("OLD ONLY", n, g)
for n, g in only_b:
    print("NEW ONLY", n, g)
