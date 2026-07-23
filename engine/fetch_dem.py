"""TACHE B1 — Dalle DEM locale (RGE ALTI via API altimetrie IGN), pas 25 m, boite 4,2x4,2 km.
Produit data/dem.json : {lat0, lon0, dlat, dlon, nrows, ncols, z:[...]} (row-major, sud->nord).
25 m (et non 5 m) : compromis assumé volume API / precision, documente dans methode.html."""
import json,subprocess,time,math
FG=json.load(open('data/finegrid.json'))
H_LAT,H_LON=FG['H']
STEP=25.0; HALF=2100.0
dlat=STEP/110540.0; dlon=STEP/(111320.0*math.cos(math.radians(H_LAT)))
n=int(2*HALF/STEP)+1
lats=[H_LAT-HALF/110540.0+i*dlat for i in range(n)]
lons=[H_LON-HALF/(111320.0*math.cos(math.radians(H_LAT)))+j*dlon for j in range(n)]
pts=[(la,lo) for la in lats for lo in lons]
print(f"DEM {n}x{n} = {len(pts)} points, pas {STEP} m",flush=True)
z=[];CH=120
for c in range(0,len(pts),CH):
    ch=pts[c:c+CH]
    ls='|'.join(str(p[1]) for p in ch);las='|'.join(str(p[0]) for p in ch)
    e=None
    for att in range(5):
        try:
            out=subprocess.run(['curl','-s','--max-time','25','-G',
              'https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json',
              '--data-urlencode',f'lon={ls}','--data-urlencode',f'lat={las}',
              '--data-urlencode','resource=ign_rge_alti_wld','--data-urlencode','delimiter=|','--data-urlencode','zonly=true'],
              capture_output=True,text=True,timeout=30).stdout
            e=json.loads(out)['elevations']
            if len(e)==len(ch): break
        except Exception: time.sleep(1+att)
    if not e or len(e)!=len(ch):
        e=[-9999.0]*len(ch); print(f"chunk {c} FAILED",flush=True)
    z+=e
    if (c//CH)%20==0: print(f"{c+len(ch)}/{len(pts)}",flush=True)
bad=sum(1 for v in z if v<-9000)
json.dump({'lat0':lats[0],'lon0':lons[0],'dlat':dlat,'dlon':dlon,'n':n,'step_m':STEP,'z':[round(v,1) for v in z]},
          open('data/dem.json','w'))
print(f"DONE dem.json {n}x{n}, {bad} points manquants",flush=True)
