import json, math, time, sys, os
from clutter_engine import *
P=json.load(open('params.json'))
USE_SCENARIOS='--scenarios' in sys.argv
ANFR=None
if not USE_SCENARIOS and os.path.exists('data/sites_anfr.json'):
    ANFR=json.load(open('data/sites_anfr.json'))['matched']
elif not USE_SCENARIOS:
    print('AVERTISSEMENT: data/sites_anfr.json absent -> mode scenarios'); USE_SCENARIOS=True
HPBW=P.get('sector_hpbw_deg',65.0); FTB=P.get('sector_front_to_back_dB',25.0)
OMNI_FALLBACK=[0]
S=json.load(open('all_sites_elev.json')); sites=S['sites']
profiles=json.load(open('profiles.json'))
FG=json.load(open('finegrid.json')); grid=FG['grid']; gel=FG['elev']
blds=json.load(open('clutter_bld.json')); vegs=json.load(open('clutter_veg.json'))
HM=P['rx_height_m']; W=P['clutter_window_m']
LAT0,LON0=FG['H']
# precompute polygon xy + bbox
def prep(polys):
    out=[]
    for p in polys:
        xy=[to_xy(la,lo,LAT0,LON0) for la,lo in p['r']]
        if xy[0]!=xy[-1]: xy.append(xy[0])
        xs=[a for a,b in xy]; ys=[b for a,b in xy]
        out.append({'xy':xy,'bbox':(min(xs),min(ys),max(xs),max(ys)),'h':p['h']})
    return out
BLD=prep(blds); VEG=prep(vegs)
for s in sites:
    s['top']=s['elev']+s['h']; s['xy']=to_xy(s['lat'],s['lon'],LAT0,LON0)
    s['real']={}
    if ANFR and s['id'] in ANFR:
        for e in ANFR[s['id']]['systems']:
            s['real'][(e['op'],e['tech'],e['band_mhz'])]=e['azimuts']
    elif ANFR:
        print(f"  site {s['id']} non apparie ANFR -> fallback scenarios/omni")
SC=P['scenarios']; SCK=list(SC.keys())
LAMS={k:C/(v['f']*1e6) for k,v in SC.items()}
FGHZ={k:v['f']/1000.0 for k,v in SC.items()}
OFF={k:10*math.log10(12*v['nrb']) for k,v in SC.items()}
IND=P['indoor_entry_loss_dB']
OPS=['Orange','SFR','Bouygues','Free']
def fspl(f,dm): return 32.45+20*math.log10(f)+20*math.log10(dm/1000.0)
rows=[]; t0=time.time()
for idx,((la,lo),pe) in enumerate(zip(grid,gel)):
    px,py=to_xy(la,lo,LAT0,LON0)
    # indoor check
    inbld=None
    for pl in BLD:
        b=pl['bbox']
        if b[0]<=px<=b[2] and b[1]<=py<=b[3] and point_in_poly_xy(px,py,pl['xy']):
            inbld=pl; break
    # geometry cache per site
    geo={}
    for s in sites:
        dxy=(s['xy'][0]-px, s['xy'][1]-py)
        dm=math.hypot(*dxy)
        if dm<1: dm=1
        ux,uy=dxy[0]/dm, dxy[1]/dm
        Ks=terrain_K(profiles[s['id']], pe, dm, s['top'], HM)
        wl=min(W,dm)
        bh=ray_clutter(px,py,ux,uy,wl,BLD,inside_skip=inbld)
        bedges=[]
        for a,b,pl in bh:
            xm=0.5*(a+b)*wl
            if xm<1: xm=1.0
            d2=dm-xm
            if d2<1: d2=1.0
            yray=(pe+HM)+(s['top']-(pe+HM))*(xm/dm)
            hrel=(pe+pl['h'])-yray
            K=hrel*math.sqrt(2*(1/xm+1/d2))
            if K>-0.5: bedges.append(K)
        vh=ray_clutter(px,py,ux,uy,wl,VEG,inside_skip=None)
        vsegs=[]; vtot=0.0
        for a,b,pl in vh:
            xm=0.5*(a+b)*wl
            yray=(pe+HM)+(s['top']-(pe+HM))*(max(xm,1)/dm)
            if yray < pe+pl['h']:
                L=(b-a)*wl
                if vtot+L>P['veg_length_cap_m']: L=max(0.0,P['veg_length_cap_m']-vtot)
                if L>0: vsegs.append(L); vtot+=L
        geo[s['id']]=(dm,Ks,bedges,vsegs,len(bh))
    row=[round(la,6),round(lo,6),1 if inbld else 0]
    summary=None; bestglob=-999
    for op in OPS:
        for sc in SCK:
            cfg=SC[sc]; lam=LAMS[sc]; sq=math.sqrt(lam); fg=FGHZ[sc]
            best=-999; bgeo=None
            for s in sites:
                sg=0.0
                if not USE_SCENARIOS and s['real']:
                    key=(op,cfg['tech'],cfg['f'])
                    if key not in s['real']: continue
                    azs=s['real'][key]
                    if azs:
                        br=bearing_deg(s['lat'],s['lon'],la,lo)
                        sg=max(sector_gain(br-a,HPBW,FTB) for a in azs)
                elif op not in s['ops'] or cfg['tech'] not in s['ops'][op]: continue
                dm,Ks,bedges,vsegs,nb=geo[s['id']]
                if dm/1000.0>cfg['range_km']: continue
                Lt=sum(Jv(K/sq) for K in Ks)
                Lb=min(sum(min(Jv(K/sq),P['building_shadow_cap_per_dB']) for K in bedges), P['building_shadow_cap_total_dB'])
                Lv=min(sum(weissberger(fg,L) for L in vsegs), P['veg_loss_cap_dB'])
                r=cfg['eirp']+sg-OFF[sc]-fspl(cfg['f'],dm)-Lt-Lb-Lv
                if r>best: best=r; bgeo=(nb,round(sum(vsegs)))
            row.append(round(best) if best>-900 else -999)
            if sc=='4G800' and best>bestglob and bgeo:
                bestglob=best; summary=bgeo
    row.append(summary[0] if summary else 0)
    row.append(round(summary[1]) if summary else 0)
    rows.append(row)
    if idx%200==0: print(f"pt {idx}/{len(grid)} t={time.time()-t0:.0f}s",flush=True)
json.dump({'ops':OPS,'sc':SCK,'rows':rows},open('fine_cov.json','w'))
print("DONE",len(rows),"in",round(time.time()-t0),"s")
