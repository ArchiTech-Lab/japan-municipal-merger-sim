"""X値（案A: 最小値型）を実データから計算し、docs/gappei_real_data.js のmunisに 'x' を追加する。
P: IPSS令和5年推計 2050年 生産年齢人口(15-64歳) ／ I: 令和7年度 課税対象所得(千円) を
現在の納税義務者1人当たりに換算して2050年生産年齢人口に掛け直した将来値。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import openpyxl

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
DATA_JS = os.path.join(os.path.dirname(__file__), "..", "docs", "gappei_real_data.js")

P_STAR = 200_000          # 2050年生産年齢人口の基準値（仕様書§3.3b）
I_STAR = 200_000 * 3_210_000  # 6,400億円（P*×全国平均の生産年齢1人当たり課税対象所得 約321万円）


def load_ipss_2050():
    wb = openpyxl.load_workbook(os.path.join(RAW, "ipss_suikei_kekka.xlsx"), data_only=True, read_only=True)
    ws = wb["Sheet1"]
    out = {}
    out_by_name = {}
    for row in ws.iter_rows(min_row=6, values_only=True):
        code, kind, prefn, munin, year = row[0], row[1], row[2], row[3], row[4]
        if year != "2050年":
            continue
        if kind in (1, 2, 3):
            pass
        elif kind == 0 and prefn == "東京都":
            pass  # 東京23区は真の基礎自治体（政令市の区とは違う）
        else:
            continue
        p1564 = row[74]
        if code is None or p1564 is None:
            continue
        rec = {"pref": prefn, "name": munin, "p2050": float(p1564)}
        out[int(code)] = rec
        if kind == 1:  # 政令市（区を集計した市全体の行）だけは名前結合の対象にする
            out_by_name[(prefn, munin)] = rec
    return out, out_by_name


def load_ipss_pref_2050(pref_code5):
    """IPSSの都道府県計の行（種別'a'）から2050年生産年齢人口を返す"""
    wb = openpyxl.load_workbook(os.path.join(RAW, "ipss_suikei_kekka.xlsx"), data_only=True, read_only=True)
    for row in wb["Sheet1"].iter_rows(min_row=6, values_only=True):
        if row[0] == pref_code5 and row[1] == "a" and row[4] == "2050年":
            return float(row[74])
    raise ValueError(pref_code5)


# ===== 福島県浜通り13市町村の2050年生産年齢人口（簡易推定・2026-10-01 本人指示） =====
# IPSS令和5年推計は原発事故の影響で13市町村の個別推計を出していないが、福島県計には含めている。
# そこで ①13市町村の2050年合計＝福島県計−59市町村の合計（IPSSの値をそのまま使う）とし、
# ②それを2026年9月1日現在の実際の居住者（15〜64歳）の比で13市町村に配分する。
# ＝13市町村は2026→2050年で同じ率で減ると仮定する簡易推定。
FUKUSHIMA_13 = ["いわき市", "相馬市", "南相馬市", "広野町", "楢葉町", "富岡町", "川内村",
                "大熊町", "双葉町", "浪江町", "葛尾村", "新地町", "飯舘村"]
GENJU_XLSX = "fukushima_genju_age5.xlsx"  # 福島県現住人口調査 年齢5歳階級別人口（令和8年9月1日現在）
# 県の現住人口調査で15〜64歳が「-」（推計困難）または内訳が負値になる町村は、各町村が公表する
# 町村内居住者数に、15〜64歳比（県調査で値のある避難指示解除町村＝広野・楢葉・川内の合計）を掛けて補う
# 町村名 -> (居住者数, 基準日, 出典, 15〜64歳の公表値 or None)。2026-10-01 に各公式サイト等で確認
# 大熊町は住民登録がある町内居住者（東京電力単身寮の住民登録なし433人は一時的な就労者として含めない）
# 葛尾村は村サイトの人口（1,187人）が住民登録ベースのため、県現住人口調査の総数（内訳は負値を含む）を使う
TOWN_RESIDENTS_2026 = {
    "富岡町": (2849, "2026-09-01", "https://www.tomioka-town.jp/soshiki/jumin/10467.html", None),
    "大熊町": (1249, "2026-08-31", "https://www.town.okuma.fukushima.jp/soshiki/juminzeimu/35146.html", 882),
    "双葉町": (220, "2026-04-01", "福島民報 2026-04-21 https://www.minpo.jp/articles/-/114508", None),
    "浪江町": (2523, "2026-08-31", "https://www.town.namie.fukushima.jp/", None),
    "葛尾村": (229, "2026-09-01", "福島県現住人口調査（総数）", None),
    "飯舘村": (1507, "2026-09-01", "https://www.vill.iitate.fukushima.jp/uploaded/attachment/18143.pdf", None),
}


def load_fukushima_genju_1564():
    """福島県現住人口調査（2026-09-01）の市町村別15〜64歳。'-'や負値の内訳を含む町村はNone"""
    wb = openpyxl.load_workbook(os.path.join(RAW, GENJU_XLSX), data_only=True, read_only=True)
    out = {}
    for r in wb.active.iter_rows(values_only=True):
        name = str(r[0]).strip() if r[0] else ""
        if name not in FUKUSHIMA_13:
            continue
        vals = r[1:23]  # 総数・0〜4歳…85歳以上・不明・0〜14・15〜64
        ok = all(isinstance(v, (int, float)) and v >= 0 for v in vals)
        out[name] = (float(r[1]), float(r[22])) if ok else None
    return out


def estimate_fukushima_13(p_others_sum):
    """13市町村それぞれの2050年生産年齢人口の推定値と、注記用の内訳を返す"""
    total_2050 = load_ipss_pref_2050(7000) - p_others_sum
    genju = load_fukushima_genju_1564()
    base = [n for n in ("広野町", "楢葉町", "川内村") if genju.get(n)]
    ratio = sum(genju[n][1] for n in base) / sum(genju[n][0] for n in base)
    w, src = {}, {}
    for n in FUKUSHIMA_13:
        if genju.get(n):
            w[n], src[n] = genju[n][1], "県現住人口調査"
        else:
            res, day, _, p1564 = TOWN_RESIDENTS_2026[n]
            if p1564 is not None:
                w[n], src[n] = p1564, f"町公表の15〜64歳居住者（{day}）"
            else:
                w[n], src[n] = res * ratio, f"居住者数{res:,}人（{day}）×15〜64歳比{ratio:.3f}"
    sw = sum(w.values())
    est = {n: total_2050 * w[n] / sw for n in FUKUSHIMA_13}
    return est, {"total_2050": total_2050, "w2026": w, "src": src, "ratio": ratio, "w_sum": sw}


def load_tax_current():
    wb = openpyxl.load_workbook(os.path.join(RAW, "J51-25-b.xlsx"), data_only=True)
    ws = wb[wb.sheetnames[0]]
    out, out_by_name = {}, {}
    for row in ws.iter_rows(min_row=5, values_only=True):
        year, orgcode, prefn, munin, hyou = row[0], row[1], row[2], row[3], row[4]
        if hyou != "市町村民税" or orgcode is None:
            continue
        taxpayers = row[5]
        taxable_income_1000yen = row[13]  # N列＝課税対象所得（千円）
        code5 = int(str(orgcode)[:5])
        if taxpayers and taxable_income_1000yen:
            rec = {"pref": prefn, "name": munin, "taxpayers": float(taxpayers),
                   "income_1000yen": float(taxable_income_1000yen)}
            out[code5] = rec
            if munin.endswith("市") and prefn != munin:
                out_by_name[(prefn, munin)] = rec  # 政令市名での結合用（区は別コードで来ないため）
    return out, out_by_name


def main():
    ipss, ipss_by_name = load_ipss_2050()
    tax, tax_by_name = load_tax_current()
    print(f"IPSS 2050 生産年齢人口: {len(ipss)}件 / 課税対象所得: {len(tax)}件")

    with open(DATA_JS, encoding="utf-8") as f:
        txt = f.read()
    prefix = "const GAPPEI_REAL_DATA = "
    assert txt.startswith(prefix)
    data = json.loads(txt[len(prefix):].rstrip("; \n"))

    # 結合キー：N03のJISコードが分かる市区町村（政令市以外）はコードで結合する
    # （同名の市区町村が複数の都道府県、まれに同一都道府県内にも存在するため＝北方領土の
    #  「泊村」が北海道古宇郡の「泊村」と名前衝突していたのを2026-09-27に発見・修正）。
    # 政令市は区をdissolveしてコードを持たないため、(都道府県名, 市名) で結合する。
    #
    # IPSS・課税データのどちらにも出てこない（＝結合できない）地点は2種類ある：
    # ①北方領土（日本が実効支配していないため推計・課税データが存在しない）
    # ②無人島・埋立地・境界未定地（N03のコード末尾800番台＝実際の居住者がいない地点。国土数値情報の
    #   命名規則で、通常の市区町村コードとは別に割り振られる）
    # これらは「本当に人がいない／統計が取れない」だけで、行政単体としては実在するので、
    # 2026-09-27 本人指示によりP=I=0（X=0）として扱い、通常の市町村と同様に合併対象にする。
    # ③福島県浜通り13市町村は、現に相当数の住民がいるのにIPSS推計が個別に出ていないだけなので、
    # 2026-10-01 本人指示により簡易推定値（estimate_fukushima_13）を入れ、通常の市町村として合併対象にする
    # （それまでは「常に達成扱い」で合併させず、県の生産年齢人口にも0として入っていた）。
    HOPPO_CODES = {"01695", "01696", "01697", "01698", "01699", "01700"}  # 色丹村・泊村・留夜別村・留別村・紗那村・蘂取村
    matched_p = matched_i = zeroed = 0
    unmatched_p, unmatched_i = [], []
    fk13 = []
    for m in data["munis"]:
        pref_name = data["prefs"][m["pref"]]
        code = m.get("code")
        if code:
            ip = ipss.get(int(code))
            tx = tax.get(int(code))
        else:
            key = (pref_name, m["name"])
            ip = ipss_by_name.get(key)
            tx = tax_by_name.get(key)
        if ip:
            matched_p += 1
        else:
            unmatched_p.append(f"{pref_name}{m['name']}")
        if tx:
            matched_i += 1
        else:
            unmatched_i.append(f"{pref_name}{m['name']}")

        is_uninhabited = code is not None and (code in HOPPO_CODES or int(code[-3:]) >= 800)
        if ip and tx and tx["taxpayers"] > 0:
            per_capita = tx["income_1000yen"] * 1000 / tx["taxpayers"]  # 円/人
            p2050 = ip["p2050"]
            i2050 = per_capita * p2050
            m["p2050"] = round(p2050)
            m["i2050"] = round(i2050)
        elif pref_name == "福島県" and m["name"] in FUKUSHIMA_13 and tx:
            fk13.append((m, tx))  # 県計からの残差で後から推定する（estimate_fukushima_13）
        elif is_uninhabited:
            m["p2050"] = 0
            m["i2050"] = 0  # 北方領土・無人島・埋立地＝X=0で合併対象にする（2026-09-27）
            zeroed += 1
        else:
            m["p2050"] = None
            m["i2050"] = None  # 未結合（福島の帰還困難区域等）＝JS側で「常に達成扱い」にフォールバック

    fk = data["prefs"].index("福島県")
    p_others = sum(m["p2050"] for m in data["munis"]
                   if m["pref"] == fk and m["name"] not in FUKUSHIMA_13 and m.get("p2050"))
    est, info = estimate_fukushima_13(p_others)
    assert len(fk13) == len(FUKUSHIMA_13), [m["name"] for m, _ in fk13]
    for m, tx in fk13:
        per_capita = tx["income_1000yen"] * 1000 / tx["taxpayers"]
        m["p2050"] = round(est[m["name"]])
        m["i2050"] = round(per_capita * est[m["name"]])
        m["p2050_est"] = 1  # 簡易推定値の印（画面の注記用）
    print(f"福島13市町村：2050年合計 {info['total_2050']:,.0f}人（IPSS県計−46市町村）、15〜64歳比 {info['ratio']:.3f}")
    for n in FUKUSHIMA_13:
        print(f"  {n}: 2026年15〜64歳 {info['w2026'][n]:,.0f} → 2050年 {est[n]:,.0f}（{info['src'][n]}）")

    print(f"P(2050生産年齢人口) 結合: {matched_p}/{len(data['munis'])}")
    print(f"I(課税対象所得) 結合: {matched_i}/{len(data['munis'])}")
    n_missing = sum(1 for m in data["munis"] if m.get("p2050") is None)
    print(f"北方領土・無人島・埋立地＝X=0にした地点: {zeroed}")
    print(f"P・I未結合（常に達成扱いにフォールバック・福島の帰還困難区域等）: {n_missing}")
    if unmatched_p:
        print("P未結合の例:", unmatched_p[:15], "..." if len(unmatched_p) > 15 else "")
    if unmatched_i:
        print("I未結合の例:", unmatched_i[:15], "..." if len(unmatched_i) > 15 else "")

    # D案（規模の経済）の閾値：仕様書§3.3bのDX前提モデル（固定費比率10%以下）による
    # 2050年生産年齢人口換算。実際の歳出データではなく、実データの人口に当てはめる概算モデル。
    D_XMAX_P2050 = 210_000
    data["xmeta"] = {"P_STAR": P_STAR, "I_STAR": I_STAR, "D_XMAX_P2050": D_XMAX_P2050}
    with open(DATA_JS, "w", encoding="utf-8") as f:
        f.write(prefix)
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print("書き出し完了", os.path.getsize(DATA_JS) / 1e6, "MB")


if __name__ == "__main__":
    main()
