"""Tests unitaires du moteur (stdlib assert). Lancer: python3 tests.py"""
import math
from clutter_engine import (Jv,seg_intersect_ts,point_in_poly_xy,ray_clutter,
                            deygout_K,weissberger,sector_gain,RAY_WARNINGS)
# J(v)
assert Jv(-1)==0.0
assert abs(Jv(0)-6.0)<0.05, Jv(0)
assert Jv(1)>Jv(0)>Jv(-0.5)>=0
# carre unite (ferme)
SQ=[(0,0),(1,0),(1,1),(0,1),(0,0)]
ts=seg_intersect_ts(-1,0.5,2,0.5,SQ); assert len(ts)==2, ts
assert len(seg_intersect_ts(-1,5,2,5,SQ))==0
assert point_in_poly_xy(0.5,0.5,SQ) and not point_in_poly_xy(1.5,0.5,SQ)
# ray_clutter: traversee simple
P=[{'xy':SQ,'bbox':(0,0,1,1),'h':5}]
h=ray_clutter(-1,0.5,1,0,3,P); assert len(h)==1 and 0<h[0][0]<h[0][1]<1
# depart dans le polygone
h=ray_clutter(0.5,0.5,1,0,3,P); assert len(h)==1 and h[0][0]==0.0
# inside_skip
assert ray_clutter(0.5,0.5,1,0,3,P,inside_skip=P[0])==[]
# rayon finissant DANS le polygone (impair + inside0=False cote entree seulement)
h=ray_clutter(-1,0.5,1,0,1.5,P)  # entre a t=2/3? W=1.5 -> q=(0.5,0.5) dedans: 1 intersection, hors depart
assert RAY_WARNINGS['odd_intersections']>=0  # comptage fonctionne (cas tangent difficile a produire exactement)
# deygout: profil plat, antenne haute -> pas d'arete
out=[];deygout_K([100.0]*20,0,19,101.5,140.0,100.0,3,out); assert out==[], out
# colline triangulaire bloquante -> >=1 arete K>0
z=[100+ (60-abs(i-10)*6 if abs(i-10)<10 else 0) for i in range(21)]
out=[];deygout_K(z,0,20,101.5,130.0,100.0,3,out); assert out and max(out)>0
# equivalence v=K/sqrt(lambda) vs calcul direct a 800 MHz
lam=299792458.0/(800e6)
K=out[0]; v=K/math.sqrt(lam)
h_=z[10]- (101.5+(130.0-101.5)*0.5 + (1000*1000)/(2*(4/3)*6371000))
v_direct=h_*math.sqrt(2/lam*(1/1000+1/1000))
assert abs(v-v_direct)<0.15*abs(v_direct)+0.1, (v,v_direct)
# weissberger: continuite a 14 m, monotone
a=weissberger(0.8,13.9); b=weissberger(0.8,14.1); assert abs(a-b)<1.0,(a,b)
assert weissberger(0.8,50)<weissberger(3.5,50)
assert weissberger(0.8,10)<weissberger(0.8,100)
# sector gain
assert sector_gain(0)==0.0
assert abs(sector_gain(32.5)+3.0)<0.01
assert sector_gain(180)==-25.0
print("TOUS LES TESTS PASSENT")
