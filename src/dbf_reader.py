"""Minimal DBF reader (no geopandas/GDAL/fiona), adapted from density/src/shpdbf.py."""
import struct
import numpy as np


def read_dbf_cols(path, cols):
    with open(path, "rb") as f:
        buf = f.read()
    nrec, hlen, rlen = struct.unpack_from("<IHH", buf, 4)
    fields, off, pos = {}, 32, 1
    while buf[off] != 0x0D:
        name = buf[off:off + 11].split(b"\x00")[0].decode("ascii", "replace")
        typ = chr(buf[off + 11])
        ln = buf[off + 16]
        fields[name] = (typ, pos, ln)
        pos += ln
        off += 32
    M = np.frombuffer(buf, np.uint8, count=nrec * rlen, offset=hlen).reshape(nrec, rlen)
    out = {}
    for c in cols:
        typ, p0, ln = fields[c]
        raw = M[:, p0:p0 + ln].tobytes()
        arr = np.frombuffer(raw, dtype=f"S{ln}")
        if typ in "NF":
            t = np.char.strip(arr)
            t = np.where(t == b"", b"0", t)
            out[c] = t.astype(float)
        else:
            out[c] = np.array([s.decode("cp932", "replace").strip() for s in arr])
    return out, nrec
