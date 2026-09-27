"""実データ版パイプライン：N03(行政区域) -> 市町村ポリゴン+隣接+都道府県 -> real_data.js
政令市の区は同一市にdissolve（N03_003=親市名で判定）。
依存: numpy, shapely, pyproj のみ（geopandas/GDAL不使用、density方式）。
"""
import sys, os, json, time, struct
sys.path.insert(0, os.path.dirname(__file__))
from dbf_reader import read_dbf_cols
from shapely.ops import unary_union
from shapely.geometry import mapping

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
SHP = os.path.join(RAW, "N03-23_230101.shp")
DBF = os.path.join(RAW, "N03-23_230101.dbf")
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "gappei_real_data.js")

REC_SIMPLIFY = 0.0003   # 個々のレコード（島・パーツ）を先に間引く（union高速化用）
FINAL_SIMPLIFY = 0.0012  # dissolve後、描画用にさらに間引く
ADJ_BUFFER = 0.0012      # 隣接判定はこのバッファ分の誤差を許容


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def main():
    log("DBF読み込み...")
    cols, nrec = read_dbf_cols(DBF, ["N03_001", "N03_003", "N03_004", "N03_007"])
    pref = cols["N03_001"]; parent = cols["N03_003"]; name = cols["N03_004"]; code = cols["N03_007"]
    log(f"{nrec} レコード")

    # N03_003は「郡・政令都市」列＝郡名（末尾「郡」）とも政令市名（末尾「市」）とも共用。
    # 郡は複数の独立した市町村を束ねるだけなので、政令市の区（末尾「市」）のときだけdissolve対象にする。
    group_key = []
    disp_name = []
    disp_code = []
    for i in range(nrec):
        if parent[i] and parent[i].endswith("市"):
            group_key.append((pref[i], parent[i]))
            disp_name.append(parent[i])
            disp_code.append(None)  # 政令市は区を統合しており単一のJISコードに対応しないため名前で結合
        else:
            group_key.append((pref[i], code[i]))
            disp_name.append(name[i])
            disp_code.append(code[i])

    # group_key -> (order, name_for_display, code_for_join)
    order = []
    order_name = []
    order_code = []
    seen = {}
    for i, gk in enumerate(group_key):
        if gk not in seen:
            seen[gk] = len(order)
            order.append(gk)
            order_name.append(disp_name[i])
            order_code.append(disp_code[i])
    n_groups = len(order)
    log(f"{n_groups} 市区町村（政令市は区を統合済み）")

    from shp_polygon import iter_shp_polygons

    acc = [[] for _ in range(n_groups)]
    t0 = time.time()
    for i, geom in enumerate(iter_shp_polygons(SHP, simplify_tol=REC_SIMPLIFY)):
        if geom is not None:
            acc[seen[group_key[i]]].append(geom)
        if i % 20000 == 0:
            log(f"  shp {i}/{nrec}")
    log(f"shp読み込み完了 {time.time()-t0:.1f}s")

    log("市区町村ごとにdissolve(unary_union)...")
    dissolved = [None] * n_groups
    t0 = time.time()
    for gi in range(n_groups):
        if acc[gi]:
            dissolved[gi] = unary_union(acc[gi])
        if gi % 200 == 0:
            log(f"  dissolve {gi}/{n_groups}")
    acc = None
    log(f"dissolve完了 {time.time()-t0:.1f}s")

    log("最終簡略化...")
    simplified = []
    for gi in range(n_groups):
        g = dissolved[gi]
        if g is None or g.is_empty:
            simplified.append(None)
            continue
        simplified.append(g.simplify(FINAL_SIMPLIFY, preserve_topology=True))

    log("隣接判定（STRtree）...")
    from shapely.strtree import STRtree
    buffered = [g.buffer(ADJ_BUFFER) if g is not None and not g.is_empty else None for g in simplified]
    valid_idx = [i for i, g in enumerate(buffered) if g is not None]
    tree = STRtree([buffered[i] for i in valid_idx])
    adjacency = [[] for _ in range(n_groups)]
    t0 = time.time()
    for local_i, gi in enumerate(valid_idx):
        cand = tree.query(buffered[gi])
        for local_j in cand:
            gj = valid_idx[local_j]
            if gj == gi:
                continue
            if buffered[gi].intersects(buffered[gj]):
                adjacency[gi].append(gj)
        if local_i % 200 == 0:
            log(f"  adj {local_i}/{len(valid_idx)}")
    log(f"隣接判定完了 {time.time()-t0:.1f}s")
    n_isolated = sum(1 for gi in range(n_groups) if not adjacency[gi])
    log(f"孤立（隣接なし＝離島等）: {n_isolated} / {n_groups}")

    # 投影：正距円筒＋平均緯度のcos補正（面積は使わないので簡易でよい）
    all_lats = []
    for g in simplified:
        if g is not None and not g.is_empty:
            b = g.bounds
            all_lats.append((b[1] + b[3]) / 2)
    lat0 = sum(all_lats) / len(all_lats)
    import math
    coslat = math.cos(math.radians(lat0))
    log(f"投影基準緯度 {lat0:.2f}度 cos={coslat:.3f}")

    def project_ring(coords):
        return [[round((lon) * coslat, 5), round(lat, 5)] for lon, lat in coords]

    def geom_to_rings(g):
        rings = []
        if g is None or g.is_empty:
            return rings
        polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
        for p in polys:
            rings.append(project_ring(list(p.exterior.coords)))
            for interior in p.interiors:
                rings.append(project_ring(list(interior.coords)))
        return rings

    prefs = []
    pref_index = {}
    munis = []
    for gi, gk in enumerate(order):
        pname = gk[0]
        cname = order_name[gi]
        if pname not in pref_index:
            pref_index[pname] = len(prefs)
            prefs.append(pname)
        g = simplified[gi]
        rings = geom_to_rings(g)
        if g is not None and not g.is_empty:
            rp = g.representative_point()
            c = [round(rp.x * coslat, 5), round(rp.y, 5)]
        else:
            c = [0, 0]
        munis.append({
            "name": cname,
            "pref": pref_index[pname],
            "rings": rings,
            "nb": adjacency[gi],
            "c": c,
            "code": order_code[gi],
        })

    total_pts = sum(len(r) for m in munis for r in m["rings"])
    log(f"最終: {len(munis)}市区町村 / {len(prefs)}都道府県 / 頂点数 {total_pts}")

    data = {"prefs": prefs, "coslat": coslat, "munis": munis}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("const GAPPEI_REAL_DATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    sz = os.path.getsize(OUT)
    log(f"書き出し: {OUT} ({sz/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
