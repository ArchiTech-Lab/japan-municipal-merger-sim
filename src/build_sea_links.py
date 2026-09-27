"""陸で隣接しない市町村（離島）どうしの合併を可能にする海越しの隣接ペアを作る -> docs/gappei_sea_links.js
方式②（最小全域木で全成分を連結）のうち、本州＋四国／九州／北海道／沖縄本島の4大陸塊どうしは
直接橋を架けない版（2026-09-27 本人承認）。人口推計のない地点（無人島・北方領土等）は
橋の両端にしない。距離は境界線どうしの最短距離（km）。依存: shapely。
"""
import os, json, time
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree
from shapely.ops import unary_union

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, "..", "docs", "gappei_real_data.js")
OUT = os.path.join(HERE, "..", "docs", "gappei_sea_links.js")
BIG_MIN_SIZE = 20  # これ以上の陸続き成分は「大陸塊」とみなし、大陸塊どうしの直接架橋は禁止


def load(p):
    s = open(p, encoding="utf-8").read()
    return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


def main():
    t0 = time.time()
    D = load(SRC)
    M = D["munis"]
    N = len(M)
    ok = [m["p2050"] is not None for m in M]  # 推計のある市町村だけを橋の対象にする

    geo = []
    for m in M:
        ps = [Polygon(r) for r in m["rings"] if len(r) >= 4]
        ps = [p if p.is_valid else p.buffer(0) for p in ps]
        geo.append(unary_union(ps) if ps else Point(m["c"]))
    print(f"geom {time.time()-t0:.1f}s", flush=True)

    # 陸の隣接関係（既存nb）だけで連結成分を求める（推計ありのみ）
    comp = [-1] * N
    nc = 0
    for s0 in range(N):
        if not ok[s0] or comp[s0] >= 0:
            continue
        stack = [s0]
        comp[s0] = nc
        while stack:
            i = stack.pop()
            for j in M[i]["nb"]:
                if ok[j] and comp[j] < 0:
                    comp[j] = nc
                    stack.append(j)
        nc += 1
    sizes = {}
    for c in comp:
        if c >= 0:
            sizes[c] = sizes.get(c, 0) + 1
    big_orig = {c for c, k in sizes.items() if k >= BIG_MIN_SIZE}
    print(f"inhabited land components={nc}  big(>= {BIG_MIN_SIZE})={sorted(sizes[c] for c in big_orig)}", flush=True)

    lab = comp[:]          # 現在のスーパーグループのラベル（初期値=陸の連結成分）
    is_big = {c: (c in big_orig) for c in sizes}
    edges = []              # 採用した橋 (i, j, dist_km)

    def groups():
        g = {}
        for i in range(N):
            if ok[i]:
                g.setdefault(lab[i], []).append(i)
        return g

    round_no = 0
    while True:
        round_no += 1
        g = groups()
        if len(g) <= 1:
            break
        best = {}
        for grp, mem in g.items():
            src_big = is_big.get(grp, False)
            out = [j for j in range(N) if ok[j] and lab[j] != grp and not (src_big and is_big.get(lab[j], False))]
            if not out:
                continue  # このグループは今回架橋できる相手がない（＝大陸塊どうしのみ残っている）
            tree = STRtree([geo[j] for j in out])
            for a in mem:
                idx, dist = tree.query_nearest(geo[a], return_distance=True)
                b, d = out[int(idx[0])], float(dist[0])
                if grp not in best or d < best[grp][2]:
                    best[grp] = (a, b, d)
        if not best:
            break  # 残っているのは大陸塊どうしだけ＝終了（意図通り、直接架橋しない）
        progressed = False
        for grp, (a, b, d) in sorted(best.items(), key=lambda kv: kv[1][2]):
            la, lb = lab[a], lab[b]
            if la == lb:
                continue
            edges.append((a, b, d * 111.0))
            merged_big = is_big.get(la, False) or is_big.get(lb, False)
            for i in range(N):
                if lab[i] == lb:
                    lab[i] = la
            is_big[la] = merged_big
            progressed = True
        if not progressed:
            break
        print(f"  round {round_no}: groups={len(g)} -> new edges this round={len([1 for grp in best])}", flush=True)

    final_groups = len(groups())
    print(f"final groups={final_groups} (大陸塊4つが残れば正常) edges={len(edges)}  {time.time()-t0:.1f}s", flush=True)
    nm = lambda i: M[i]["name"]
    for a, b, d in sorted(edges, key=lambda e: -e[2]):
        print(f"  {nm(a)}—{nm(b)} {d:.1f}km")

    pairs = [[a, b] for a, b, _ in edges]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// 陸で隣接しない離島どうしの合併を可能にする海越し隣接ペア（build_sea_links.py が生成）\n")
        f.write("const GAPPEI_SEA_LINKS = ")
        json.dump(pairs, f, separators=(",", ":"))
        f.write(";\n")
    print(f"-> {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
