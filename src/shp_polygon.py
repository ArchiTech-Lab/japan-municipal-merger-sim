"""Streaming ESRI Shapefile Polygon(type 5) reader -> shapely geometries.
No geopandas/fiona/GDAL (density/src/shpdbf.py style), but unlike that module
(centroid-only) this extracts full rings, classifying outer/hole by signed area.
"""
import struct
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid


def _ring_area2(xy):
    x = xy[:, 0]
    y = xy[:, 1]
    return float((x[:-1] * y[1:] - x[1:] * y[:-1]).sum() + (x[-1] * y[0] - x[0] * y[-1]))


def iter_shp_polygons(path, simplify_tol=None):
    """Yields one shapely (Multi)Polygon per shapefile record, in record order."""
    with open(path, "rb") as f:
        buf = f.read()
    pos = 100
    n = len(buf)
    while pos + 8 <= n:
        _, clen = struct.unpack_from(">II", buf, pos)
        rec = pos + 8
        shp = struct.unpack_from("<I", buf, rec)[0]
        if shp != 5:
            pos = rec + clen * 2
            continue
        nparts = struct.unpack_from("<I", buf, rec + 36)[0]
        npo = struct.unpack_from("<I", buf, rec + 40)[0]
        parts = struct.unpack_from(f"<{nparts}i", buf, rec + 44)
        base = rec + 44 + 4 * nparts
        import numpy as np
        xy = np.frombuffer(buf, "<f8", count=2 * npo, offset=base).reshape(-1, 2)
        bounds = list(parts) + [npo]
        outers, holes = [], []
        for k in range(nparts):
            ring = xy[bounds[k]:bounds[k + 1]]
            if len(ring) < 4:
                continue
            a2 = _ring_area2(ring)
            # ESRI: outer ring clockwise (a2 < 0 in standard x-right,y-up signed area)
            if a2 < 0:
                outers.append(ring)
            else:
                holes.append(ring)
        polys = []
        for o in outers:
            hs = [h for h in holes]  # assign all holes; unary_union will sort out containment
            try:
                p = Polygon(o, hs) if hs else Polygon(o)
                if simplify_tol:
                    p = p.simplify(simplify_tol, preserve_topology=True)
                if not p.is_valid:
                    p = make_valid(p)
                if not p.is_empty:
                    polys.append(p)
            except Exception:
                pass
        pos = rec + clen * 2
        if not polys:
            yield None
        elif len(polys) == 1:
            yield polys[0]
        else:
            yield MultiPolygon([g for p in polys for g in (p.geoms if p.geom_type == "MultiPolygon" else [p])])
