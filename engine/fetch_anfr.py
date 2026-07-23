"""TACHE A — Recupere l'open data ANFR (installations > 5 W) et produit data/sites_anfr.json.

Source : data.gouv.fr, jeu "Donnees sur les installations radioelectriques de plus de 5 watts"
(Licence Ouverte v2.0). Tables : SUP_SUPPORT (position DMS, hauteur), SUP_STATION (-> operateur),
SUP_ANTENNE (azimut, hauteur aerien), SUP_EMETTEUR (systeme "LTE 800", "5G NR 3500"...).
SUP_BANDE (200 Mo) n'est pas lue : la bande est deja dans le libelle systeme.

Usage :
  python3 fetch_anfr.py                 # telecharge le dernier export (~66 Mo) puis filtre
  python3 fetch_anfr.py --zip X.zip --ref Y.zip   # utilise des archives locales

Stdlib uniquement (urllib, zipfile, csv, json, math). Ecrit data/sites_anfr.json.
"""
import sys, os, io, json, csv, math, zipfile, urllib.request

RADIUS_KM = 10.0
MATCH_M = 60.0
DATASET_API = ("https://www.data.gouv.fr/api/1/datasets/"
               "donnees-sur-les-installations-radioelectriques-de-plus-de-5-watts-1/")
MOBILE_OPS = {"ORANGE": "Orange", "SFR": "SFR",
              "BOUYGUES TELECOM": "Bouygues", "FREE MOBILE": "Free"}
TECH_OF = {"GSM": "2G", "UMTS": "3G", "LTE": "4G", "5G NR": "5G"}

def hav_m(a, b, c, d):
    R = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = math.radians(c - a), math.radians(d - b)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(x))

def dms(dg, mn, sc, hemi):
    v = float(dg) + float(mn)/60.0 + float(sc)/3600.0
    return -v if hemi in ("S", "W") else v

def latest_urls():
    d = json.load(urllib.request.urlopen(DATASET_API, timeout=30))
    exp = ref = None
    for r in d["resources"]:
        t = r["title"].lower()
        if exp is None and "supports" in t: exp = r["url"]
        if ref is None and ("référence" in t or "reference" in t): ref = r["url"]
    if not exp or not ref: raise SystemExit("resources introuvables sur data.gouv")
    return exp, ref

def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 1000: return dest
    print(f"telechargement {url.split('/')[-1]} ...", flush=True)
    urllib.request.urlretrieve(url, dest)
    return dest

def rows(zf, name):
    with zf.open(name) as f:
        r = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                           delimiter=";")
        for row in r: yield row

def main():
    args = sys.argv[1:]
    zpath = rpath = None
    if "--zip" in args: zpath = args[args.index("--zip")+1]
    if "--ref" in args: rpath = args[args.index("--ref")+1]
    if not zpath or not rpath:
        exp_u, ref_u = latest_urls()
        zpath = fetch(exp_u, "anfr_export.zip")
        rpath = fetch(ref_u, "anfr_ref.zip")

    FG = json.load(open("data/finegrid.json")) if os.path.exists("data/finegrid.json") \
        else json.load(open("finegrid.json"))
    H_LAT, H_LON = FG["H"]

    zref = zipfile.ZipFile(rpath)
    op_name = {}
    for r in rows(zref, "SUP_EXPLOITANT.txt"):
        nm = r["ADM_LB_NOM"].strip().upper()
        for key, std in MOBILE_OPS.items():
            if key in nm: op_name[r["ADM_ID"]] = std

    z = zipfile.ZipFile(zpath)
    # 1) supports dans le rayon
    sups = {}          # sup_id -> {lat, lon, haut, stas:set}
    sta_sup = {}       # sta -> sup_id
    for r in rows(z, "SUP_SUPPORT.txt"):
        try:
            la = dms(r["COR_NB_DG_LAT"], r["COR_NB_MN_LAT"], r["COR_NB_SC_LAT"], r["COR_CD_NS_LAT"])
            lo = dms(r["COR_NB_DG_LON"], r["COR_NB_MN_LON"], r["COR_NB_SC_LON"], r["COR_CD_EW_LON"])
        except (ValueError, KeyError):
            continue
        if abs(la - H_LAT) > 0.12 or abs(lo - H_LON) > 0.17: continue
        if hav_m(H_LAT, H_LON, la, lo) > RADIUS_KM*1000: continue
        sid = r["SUP_ID"]
        s = sups.setdefault(sid, {"lat": round(la, 6), "lon": round(lo, 6),
                                  "haut": float((r["SUP_NM_HAUT"] or "0").replace(",", ".")),
                                  "stas": set()})
        s["stas"].add(r["STA_NM_ANFR"]); sta_sup[r["STA_NM_ANFR"]] = sid
    print(f"supports dans les {RADIUS_KM:.0f} km : {len(sups)}", flush=True)

    # 2) operateur par station
    sta_op = {}
    for r in rows(z, "SUP_STATION.txt"):
        if r["STA_NM_ANFR"] in sta_sup and r["ADM_ID"] in op_name:
            sta_op[r["STA_NM_ANFR"]] = op_name[r["ADM_ID"]]
    print(f"stations mobiles : {len(sta_op)}", flush=True)

    # 3) aeriens (azimut, hauteur)
    aer = {}
    for r in rows(z, "SUP_ANTENNE.txt"):
        if r["STA_NM_ANFR"] in sta_op:
            az = r["AER_NB_AZIMUT"].strip().replace(",", ".")
            hb = r["AER_NB_ALT_BAS"].strip().replace(",", ".")
            aer[(r["STA_NM_ANFR"], r["AER_ID"])] = {
                "azimut": float(az) if az else None,
                "haut": float(hb) if hb else None}

    # 4) emetteurs -> systemes mobiles
    seen_labels = {}
    systems = {}       # sup_id -> {(op, tech, band): set(azimuts)} ; sectors detail
    for r in rows(z, "SUP_EMETTEUR.txt"):
        sta = r["STA_NM_ANFR"]
        if sta not in sta_op: continue
        lab = r["EMR_LB_SYSTEME"].strip()
        tech = band = None
        for pre, t in TECH_OF.items():
            if lab.upper().startswith(pre):
                tech = t
                tail = lab[len(pre):].strip()
                digits = "".join(ch for ch in tail if ch.isdigit())
                if digits: band = int(digits)
                break
        seen_labels[lab] = seen_labels.get(lab, 0) + 1
        if not tech or not band: continue
        op = sta_op[sta]; sup = sta_sup[sta]
        a = aer.get((sta, r["AER_ID"]))
        d = systems.setdefault(sup, {})
        key = (op, tech, band)
        e = d.setdefault(key, {"sectors": [], "date": r.get("EMR_DT_SERVICE", "")})
        if a: e["sectors"].append({"azimut": a["azimut"], "haut": a["haut"]})

    # 5) appariement avec les 22 sites Cartoradio
    base = "data/all_sites_elev.json" if os.path.exists("data/all_sites_elev.json") \
        else "all_sites_elev.json"
    carto = json.load(open(base))["sites"]
    out, unmatched = {}, []
    for site in carto:
        best = None
        for sid, s in sups.items():
            dm = hav_m(site["lat"], site["lon"], s["lat"], s["lon"])
            ops_here = {sta_op[st] for st in s["stas"] if st in sta_op}
            if dm < MATCH_M and set(site["ops"]) & ops_here:
                if best is None or dm < best[1]: best = (sid, dm)
        if not best:
            unmatched.append(site["id"]); continue
        sid, dm = best
        sysl, secl = [], []
        for (op, tech, band), e in systems.get(sid, {}).items():
            azs = sorted({round(x["azimut"]) for x in e["sectors"] if x["azimut"] is not None})
            sysl.append({"op": op, "tech": tech, "band_mhz": band,
                         "date_service": e["date"], "azimuts": azs})
            for x in e["sectors"]:
                if x["azimut"] is not None:
                    secl.append({"op": op, "band_mhz": band,
                                 "azimut_deg": x["azimut"], "hauteur_m": x["haut"]})
        out[site["id"]] = {"anfr_sup_id": sid, "dist_m": round(dm, 1),
                           "lat": sups[sid]["lat"], "lon": sups[sid]["lon"],
                           "systems": sorted(sysl, key=lambda s: (s["op"], s["tech"], s["band_mhz"])),
                           "sectors": secl}
    os.makedirs("data", exist_ok=True)
    json.dump({"radius_km": RADIUS_KM, "match_m": MATCH_M, "source": os.path.basename(zpath),
               "matched": out, "unmatched": unmatched},
              open("data/sites_anfr.json", "w"), ensure_ascii=False, indent=1)
    print(f"apparies : {len(out)}/{len(carto)} ; non apparies : {unmatched}")
    mob = {k: v for k, v in sorted(seen_labels.items(), key=lambda x: -x[1])
           if any(k.upper().startswith(p) for p in TECH_OF)}
    print("libelles systemes mobiles vus :", dict(list(mob.items())[:15]))

if __name__ == "__main__":
    main()
