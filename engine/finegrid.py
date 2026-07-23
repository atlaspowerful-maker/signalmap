import json,subprocess
H=(45.309894,5.146978)
N=50; dlat=0.0040; dlon=0.0057
grid=[]
for i in range(N):
    for j in range(N):
        la=H[0]-dlat+2*dlat*i/(N-1); lo=H[1]-dlon+2*dlon*j/(N-1)
        grid.append([round(la,6),round(lo,6)])
elev=[]
CH=120
for c in range(0,len(grid),CH):
    ch=grid[c:c+CH]
    lons='|'.join(str(p[1]) for p in ch); lats='|'.join(str(p[0]) for p in ch)
    ok=False
    for att in range(4):
        try:
            out=subprocess.run(['curl','-s','--max-time','30','-G',
              'https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json',
              '--data-urlencode',f'lon={lons}','--data-urlencode',f'lat={lats}',
              '--data-urlencode','resource=ign_rge_alti_wld','--data-urlencode','delimiter=|','--data-urlencode','zonly=true'],
              capture_output=True,text=True,timeout=35).stdout
            e=json.loads(out)['elevations']
            if len(e)==len(ch): elev+=e; ok=True; break
        except Exception: pass
    if not ok:
        elev+=[371.0]*len(ch); print("chunk",c,"FALLBACK",flush=True)
    print("elev",c+len(ch),"/",len(grid),flush=True)
json.dump({'grid':grid,'elev':elev,'N':N,'dlat':dlat,'dlon':dlon,'H':H},open('finegrid.json','w'))
print("DONE",len(grid))
