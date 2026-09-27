"""市区町村ごとの面積（km²）-> docs/gappei_area.js
build_real.pyと同じ順（政令市の区は1市に統合）で並べる。描画用に間引いた輪郭ではなく元のN03から、
GRS80楕円体上の測地線面積で計算する。N03のレコードは互いに重ならないので、unionせずに足してよい。
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))
from dbf_reader import read_dbf_cols
from shp_polygon import iter_shp_polygons
from pyproj import Geod

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "..", "data", "raw")
SHP = os.path.join(RAW, "N03-23_230101.shp")
DBF = os.path.join(RAW, "N03-23_230101.dbf")
REAL = os.path.join(HERE, "..", "docs", "gappei_real_data.js")
OUT = os.path.join(HERE, "..", "docs", "gappei_area.js")


def main():
    t0 = time.time()
    cols, nrec = read_dbf_cols(DBF, ["N03_001", "N03_003", "N03_004", "N03_007"])
    pref, parent, name, code = cols["N03_001"], cols["N03_003"], cols["N03_004"], cols["N03_007"]

    seen, names = {}, []
    group = []
    for i in range(nrec):
        if parent[i] and parent[i].endswith("市"):
            gk, nm = (pref[i], parent[i]), parent[i]
        else:
            gk, nm = (pref[i], code[i]), name[i]
        if gk not in seen:
            seen[gk] = len(names)
            names.append(nm)
        group.append(seen[gk])

    geod = Geod(ellps="GRS80")
    area = [0.0] * len(names)
    for i, geom in enumerate(iter_shp_polygons(SHP)):
        if geom is not None and not geom.is_empty:
            a, _ = geod.geometry_area_perimeter(geom)
            area[group[i]] += abs(a) / 1e6

    s = open(REAL, encoding="utf-8").read()
    real = json.loads(s[s.index("{"):s.rstrip().rstrip(";").rindex("}") + 1])
    assert [m["name"] for m in real["munis"]] == names, "build_real.pyと市区町村の並びが一致しない"

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("const GAPPEI_AREA = ")
        json.dump([round(a, 2) for a in area], f, separators=(",", ":"))
        f.write(";\n")
    print(f"{len(area)}市区町村 合計{sum(area):,.0f}km² {time.time()-t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
