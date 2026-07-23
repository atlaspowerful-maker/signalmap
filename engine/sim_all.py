import json,math,sys,os
from clutter_engine import terrain_K_dem, Jv as _Jv
USE_SCENARIOS='--scenarios' in sys.argv
ANFR=None
if not USE_SCENARIOS and os.path.exists('data/sites_anfr.json'):
    ANFR=json.load(open('data/sites_anfr.json'))['matched']
elif not USE_SCENARIOS:
    print('AVERTISSEMENT: sites_anfr.json absent -> scenarios'); USE_SCENARIOS=True
def _brg(lat1,lon1,lat2,lon2):
    p1,p2=math.radians(lat1),math.radians(lat2);dl=math.radians(lon2-lon1)
    x=math.sin(dl)*math.cos(p2);y=math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)
    return (math.degrees(math.atan2(x,y))+360.0)%360.0
def _sg(dphi,hpbw=65.0,ftb=25.0):
    d=abs(dphi)%360.0
    if d>180.0:d=360.0-d
    return -min(12.0*(d/hpbw)**2,ftb)
S=json.load(open('all_sites_elev.json'));sites=S['sites']
DEM=json.load(open('data/dem.json')) if os.path.exists('data/dem.json') else json.load(open('dem.json'))
for _s in S['sites']:
    _s['real']={}
    if ANFR and _s['id'] in ANFR:
        for e in ANFR[_s['id']]['systems']:
            _s['real'][(e['op'],e['tech'],e['band_mhz'])]=e['azimuts']
profiles=json.load(open('profiles.json'))
G=json.load(open('grid.json'));grid=G['grid'];gel=json.load(open('grid_elev.json'))
_HL,_HO=G['H']
HM=1.5;C=299792458.0;kR=4/3*6371000.0
def hav(a,b,c,d):
    R=6371000.0;p1,p2=math.radians(a),math.radians(c);dp=math.radians(c-a);dl=math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2;return 2*R*math.asin(math.sqrt(x))
DMH={_s['id']:hav(_HL,_HO,_s['lat'],_s['lon']) for _s in sites}
def Jv(v):
    if v<=-0.78:return 0.0
    return 6.9+20*math.log10(math.sqrt((v-0.1)**2+1)+v-0.1)
def deygout(z,i0,i1,ha,hb,step,lam,depth):
    if i1-i0<2 or depth==0:return 0.0
    bv=-1e9;km=-1
    for k in range(i0+1,i1):
        d1=(k-i0)*step;d2=(i1-k)*step;los=ha+(hb-ha)*((k-i0)/(i1-i0))
        h=z[k]+d1*d2/(2*kR)-los;v=h*math.sqrt(2/lam*(1/d1+1/d2))
        if v>bv:bv=v;km=k
    if bv<=-0.78 or km<0:return 0.0
    return Jv(bv)+deygout(z,i0,km,ha,z[km],step,lam,depth-1)+deygout(z,km,i1,z[km],hb,step,lam,depth-1)
def fspl(f,dm):return 32.45+20*math.log10(f)+20*math.log10(dm/1000.0)
# scenario: freq, EIRP, offset, max practical range km, tech
SC={
 '4G700':(700,60,27.8,16,'4G'),
 '4G800':(800,61,27.8,16,'4G'),
 '4G1800':(1800,63,29.5,10,'4G'),
 '4G2100':(2100,63,29.5,7,'4G'),
 '4G2600':(2600,64,30.8,5,'4G'),
 '5G700':(700,60,27.8,16,'5G'),
 '5G2100':(2100,62,29.5,6,'5G'),
 '5G3500':(3500,66,35.2,5.0,'5G'),
}
LAM={k:C/(v[0]*1e6) for k,v in SC.items()}
OPS=['Orange','SFR','Bouygues','Free']
for s in sites:s['top']=s['elev']+s['h']
S_=-999;pts=[]
for idx,((la,lo),pe) in enumerate(zip(grid,gel)):
    row=[round(la,6),round(lo,6)]
    for op in OPS:
        for sc,(f,e,o,rng,tech) in SC.items():
            lam=LAM[sc];best=-999
            for s in sites:
                sg=0.0
                if not USE_SCENARIOS and s['real']:
                    key=(op,tech,f)
                    if key not in s['real']:continue
                    azs=s['real'][key]
                    if azs:
                        br=_brg(s['lat'],s['lon'],la,lo)
                        sg=max(_sg(br-a) for a in azs)
                elif op not in s['ops'] or tech not in s['ops'][op]:continue
                if s['dist']>rng:continue
                dm=hav(la,lo,s['lat'],s['lon'])
                Ks=terrain_K_dem(DEM,profiles[s['id']],DMH[s['id']],la,lo,pe,s['lat'],s['lon'],dm,s['top'],HM)
                import math as _m
                d=sum(_Jv(K/_m.sqrt(lam)) for K in Ks)
                r=e+sg-o-fspl(f,dm)-d
                if r>best:best=r
            row.append(round(best) if best>-900 else S_)
    pts.append(row)
    if idx%150==0:print("pt",idx,flush=True)
json.dump({'ops':OPS,'sc':list(SC.keys()),'pts':pts},open('sim_all_grid.json','w'))
NS=len(SC)
def pct(oi,si):
    n=sum(1 for r in pts if r[2+oi*NS+si]>-113);return round(100*n/len(pts))
print(f"{'op':9} "+" ".join(f"{s:>7}" for s in SC))
for oi,op in enumerate(OPS):
    print(f"{op:9} "+" ".join(f"{pct(oi,si):>6}%" for si in range(NS)))
print("DONE")
