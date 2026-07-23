"""Clutter-aware RF coverage engine. Terrain Deygout + building knife-edge + Weissberger vegetation."""
import json, math
C=299792458.0; kR=4/3*6371000.0
def Jv(v):
    if v<=-0.78: return 0.0
    return 6.9+20*math.log10(math.sqrt((v-0.1)**2+1)+v-0.1)
def deygout_K(z,i0,i1,ha,hb,step,depth,out):
    """Collect K_i (freq-independent edge constants; v=K/sqrt(lambda)) via Deygout recursion."""
    if i1-i0<2 or depth==0: return
    bK=-1e9; km=-1
    for k in range(i0+1,i1):
        d1=(k-i0)*step; d2=(i1-k)*step
        los=ha+(hb-ha)*((k-i0)/(i1-i0))
        h=z[k]+d1*d2/(2*kR)-los
        K=h*math.sqrt(2*(1/d1+1/d2))
        if K>bK: bK=K; km=k
    if bK<=-0.5 or km<0: return
    out.append(bK)
    deygout_K(z,i0,km,ha,z[km],step,depth-1,out)
    deygout_K(z,km,i1,z[km],hb,step,depth-1,out)
def terrain_K(profile,pe,dm,top_asl,hm):
    z=list(profile); z[0]=pe
    n=len(z); step=dm/(n-1)
    out=[]; deygout_K(z,0,n-1,pe+hm,top_asl,step,3,out)
    return out
def to_xy(lat,lon,lat0,lon0):
    return ((lon-lon0)*111320.0*math.cos(math.radians(lat0)), (lat-lat0)*110540.0)
def seg_intersect_ts(px,py,qx,qy,poly_xy):
    """Return sorted list of t in (0,1) where segment P->Q crosses polygon edges."""
    ts=[]
    dx=qx-px; dy=qy-py
    n=len(poly_xy)
    for i in range(n-1):
        ax,ay=poly_xy[i]; bx,by=poly_xy[i+1]
        ex=bx-ax; ey=by-ay
        den=dx*ey-dy*ex
        if abs(den)<1e-12: continue
        t=((ax-px)*ey-(ay-py)*ex)/den
        u=((ax-px)*dy-(ay-py)*dx)/den
        if 0.0<t<1.0 and 0.0<=u<=1.0: ts.append(t)
    ts.sort()
    return ts
def point_in_poly_xy(x,y,poly_xy):
    ins=False; n=len(poly_xy)
    for i in range(n-1):
        xi,yi=poly_xy[i]; xj,yj=poly_xy[i+1]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi)+xi: ins=not ins
    return ins
def ray_clutter(px,py,ux,uy,W,polys,inside_skip=None):
    """polys: list of dicts {xy,bbox,h}. Returns crossings [(t_mid*W, h)] for buildings mode,
       or total length inside for veg mode (use spans=True)."""
    qx,qy=px+ux*W,py+uy*W
    rminx,rmaxx=min(px,qx),max(px,qx); rminy,rmaxy=min(py,qy),max(py,qy)
    hits=[]
    for pl in polys:
        if pl is inside_skip: continue
        bx0,by0,bx1,by1=pl['bbox']
        if bx1<rminx or bx0>rmaxx or by1<rminy or by0>rmaxy: continue
        ts=seg_intersect_ts(px,py,qx,qy,pl['xy'])
        inside0=point_in_poly_xy(px,py,pl['xy'])
        if inside0: ts=[0.0]+ts
        if len(ts)>=2:
            for a,b in zip(ts[0::2],ts[1::2]):
                hits.append((a,b,pl))
        elif len(ts)==1 and inside0:
            hits.append((0.0,ts[0],pl))
    return hits
def weissberger(f_ghz,d):
    if d<=0: return 0.0
    if d<=14: L=0.45*(f_ghz**0.284)*d
    else: L=1.33*(f_ghz**0.284)*(d**0.588)
    return L

def sector_gain(dphi_deg,hpbw=65.0,ftb=25.0):
    """3GPP horizontal pattern: A_h = -min(12*(dphi/hpbw)^2, front_to_back). Returns dB (<=0)."""
    d=abs(dphi_deg)%360.0
    if d>180.0: d=360.0-d
    return -min(12.0*(d/hpbw)**2, ftb)
def bearing_deg(lat1,lon1,lat2,lon2):
    import math as _m
    p1,p2=_m.radians(lat1),_m.radians(lat2);dl=_m.radians(lon2-lon1)
    x=_m.sin(dl)*_m.cos(p2);y=_m.cos(p1)*_m.sin(p2)-_m.sin(p1)*_m.cos(p2)*_m.cos(dl)
    return (_m.degrees(_m.atan2(x,y))+360.0)%360.0
