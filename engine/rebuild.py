import json,subprocess,math,os,time
IDS="504168 591912 624487 688339 760207 1316162 1560353 1584007 1675273 1689267 1732577 1732624 2258368 2318460 2522147 2628556 2662410 2913797 3024927 3104272 3123304 3169161".split()
H=(45.309894,5.146978)
OPS={23:'Orange',137:'SFR',6:'Bouygues',240:'Free'}
def hav(a,b,c,d):
    R=6371.0;p1,p2=math.radians(a),math.radians(c);dp=math.radians(c-a);dl=math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2;return 2*R*math.asin(math.sqrt(x))
def brg(a,b,c,d):
    p1,p2=math.radians(a),math.radians(c);dl=math.radians(d-b)
    x=math.sin(dl)*math.cos(p2);y=math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)
    return (math.degrees(math.atan2(x,y))+360)%360
def comp(b):
    D=['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSO','SO','OSO','O','ONO','NO','NNO'];return D[round(b/22.5)%16]
sites=[]
for id in IDS:
    for att in range(4):
        try:
            out=subprocess.run(['curl','-s','--max-time','20',f'https://www.cartoradio.fr/api/v1/sites/{id}'],
                capture_output=True,text=True,timeout=25).stdout
            d=json.loads(out)['data'];break
        except Exception:
            if att==3: raise
            time.sleep(2)
    lat=d['coordonnees']['coord_x'];lon=d['coordonnees']['coord_y']
    ops={}
    for cat in d['categories']:
        if cat['code']=='TEL':
            for e in cat['exploitants']:
                if e['id'] in OPS: ops[OPS[e['id']]]=e['systemes']
    b=brg(H[0],H[1],lat,lon)
    sites.append(dict(id=id,lat=lat,lon=lon,h=d['description'].get('hauteur') or 20,
        nature=d['description'].get('nature'),commune=d['adresse'].get('commune'),
        dist=round(hav(H[0],H[1],lat,lon),2),brg=round(b),dir=comp(b),ops=ops))
    print("site",id,"ok",flush=True)
# elevations
lons='|'.join([str(H[1])]+[str(s['lon']) for s in sites])
lats='|'.join([str(H[0])]+[str(s['lat']) for s in sites])
for att in range(4):
    try:
        out=subprocess.run(['curl','-s','--max-time','30','-G',
          'https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json',
          '--data-urlencode',f'lon={lons}','--data-urlencode',f'lat={lats}',
          '--data-urlencode','resource=ign_rge_alti_wld','--data-urlencode','delimiter=|','--data-urlencode','zonly=true'],
          capture_output=True,text=True,timeout=35).stdout
        elev=json.loads(out)['elevations'];break
    except Exception:
        if att==3: raise
        time.sleep(2)
H_EL=elev[0]
for i,s in enumerate(sites): s['elev']=elev[i+1]
json.dump({'house_elev':H_EL,'sites':sites},open('all_sites_elev.json','w'))
print("sites+elev saved, house",H_EL,flush=True)
# profiles
profiles={}
for s in sites:
    z=None
    for att in range(5):
        try:
            out=subprocess.run(['curl','-s','--max-time','18','-G',
              'https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevationLine.json',
              '--data-urlencode',f'lon={H[1]}|{s["lon"]}','--data-urlencode',f'lat={H[0]}|{s["lat"]}',
              '--data-urlencode','resource=ign_rge_alti_wld','--data-urlencode','delimiter=|',
              '--data-urlencode','sampling=50'],capture_output=True,text=True,timeout=22).stdout
            z=[p['z'] for p in json.loads(out)['elevations']]
            if z: break
        except Exception: time.sleep(1)
    if not z: raise SystemExit(f"profile fail {s['id']}")
    profiles[s['id']]=z
    print("profile",s['id'],"ok",flush=True)
json.dump(profiles,open('profiles.json','w'))
# tool_data (antennas for map)
ant=[]
for s in sites:
    ant.append(dict(lat=round(s['lat'],6),lon=round(s['lon'],6),dist=s['dist'],dir=s['dir'],h=s['h'],
        elev=round(s['elev']),commune=s['commune'],nature=s['nature'],
        ops={k:{'tech':v} for k,v in s['ops'].items()},color='#888',best4=0))
json.dump({'house':{'lat':H[0],'lon':H[1],'elev':round(H_EL)},'antennas':ant},open('tool_data.json','w'))
print("REBUILD DONE",flush=True)
# backup to scratchpad
bk='/private/tmp/claude-501/-Users-bourdatloic-TEST/7ff29d6c-a75c-45bc-bb82-67ac21097682/scratchpad'
os.makedirs(bk,exist_ok=True)
for f in ['all_sites_elev.json','profiles.json','tool_data.json','clutter_bld.json','clutter_veg.json','finegrid.json','params.json','clutter_engine.py','run_fine.py','gen_fine_map.py']:
    if os.path.exists(f):
        open(os.path.join(bk,f),'w').write(open(f).read())
print("BACKUP DONE",flush=True)
