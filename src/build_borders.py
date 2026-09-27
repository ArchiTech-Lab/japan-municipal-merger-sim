"""隣接する市町村ペアごとの共有境界線を作る -> docs/gappei_borders.js
画面では「現在の所属都道府県が違うペア」の線だけを太線で描く（合併で県境が動くため毎フレーム選び直す）。
入力は build_real.py が書いた docs/gappei_real_data.js（描画に使う簡略化済みリングそのもの）なので、
太線は画面上の市町村輪郭とずれない。依存: shapely のみ。
"""
import os, json, time
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection
from shapely.ops import linemerge

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, "..", "docs", "gappei_real_data.js")
OUT = os.path.join(HERE, "..", "docs", "gappei_borders.js")
TOL = 0.0025        # 隣の市町村の輪郭からこの距離以内にある自分の輪郭＝共有境界（独立に簡略化されたずれを吸収）
SIMPLIFY = 0.0006   # 線をさらに間引く
MIN_LEN = 0.002     # これより短い断片は捨てる（角で触れているだけ等）


def load():
    s = open(SRC, encoding="utf-8").read()
    s = s[s.index("=") + 1:].strip().rstrip(";")
    return json.loads(s)


def to_geom(rings):
    # rings は外周・穴の区別なしに並んでいるので、各リングを面として作り、偶奇で合成する代わりに
    # 境界判定用には「全リングの輪郭線」と「全リングの面の和」を使えば十分
    polys = [Polygon(r) for r in rings if len(r) >= 4]
    polys = [p if p.is_valid else p.buffer(0) for p in polys]
    return polys


def lines_of(g):
    if g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    if isinstance(g, MultiLineString):
        return list(g.geoms)
    if isinstance(g, GeometryCollection):
        out = []
        for h in g.geoms:
            out += lines_of(h)
        return out
    return []


def main():
    t0 = time.time()
    D = load()
    M = D["munis"]
    n = len(M)
    boundary = []
    area = []
    for m in M:
        polys = to_geom(m["rings"])
        boundary.append(MultiLineString([list(p.exterior.coords) for p in polys if not p.is_empty and p.geom_type == "Polygon"]) if polys else None)
        area.append(MultiPolygon([p for p in polys if p.geom_type == "Polygon"]) if polys else None)
    near = [a.buffer(TOL) if a is not None else None for a in area]

    borders = []
    npts = 0
    for i in range(n):
        for j in M[i]["nb"]:
            if j <= i or boundary[i] is None or near[j] is None:
                continue
            seg = boundary[i].intersection(near[j])
            ls = [l for l in lines_of(seg) if l.length >= MIN_LEN]
            if not ls:
                continue
            merged = linemerge(ls) if len(ls) > 1 else ls[0]
            parts = []
            for l in lines_of(merged):
                l = l.simplify(SIMPLIFY)
                if l.length < MIN_LEN:
                    continue
                parts.append([[round(x, 5), round(y, 5)] for x, y in l.coords])
                npts += len(l.coords)
            if parts:
                borders.append([i, j, parts])
        if i % 300 == 0:
            print(f"  {i}/{n}  pairs={len(borders)}  {time.time()-t0:.0f}s", flush=True)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("const GAPPEI_BORDERS = ")
        json.dump(borders, f, separators=(",", ":"))
        f.write(";\n")
    print(f"pairs={len(borders)} points={npts} -> {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB) {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
