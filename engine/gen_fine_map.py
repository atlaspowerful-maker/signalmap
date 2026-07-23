import json
FC=json.load(open('fine_cov.json'))
FG=json.load(open('finegrid.json'))
blds=json.load(open('clutter_bld.json')); vegs=json.load(open('clutter_veg.json'))
TD=json.load(open('tool_data.json'))
step_lat=2*FG['dlat']/(FG['N']-1); step_lon=2*FG['dlon']/(FG['N']-1)
# simplify big veg polys
def simp(r,maxv=60):
    if len(r)<=maxv: return r
    k=len(r)//maxv+1
    out=r[::k]
    if out[-1]!=r[-1]: out.append(r[-1])
    return out
vegs2=[{'r':simp(v['r']),'nat':v['nat']} for v in vegs]
ant=[{'lat':a['lat'],'lon':a['lon'],'commune':a['commune'],'dist':a['dist'],'dir':a['dir'],
      'g5':any('5G' in v['tech'] for v in a['ops'].values()),
      'ops':{k:v['tech'] for k,v in a['ops'].items()}} for a in TD['antennas']]
zone=[[45.309896,5.146548],[45.310055,5.146829],[45.310079,5.14692],[45.309847,5.147749],[45.309655,5.147588],[45.309692,5.14725],[45.309553,5.147079],[45.309806,5.14644]]
P=json.load(open('params.json'))
payload={'H':FG['H'],'hlat':round(step_lat/2,7),'hlon':round(step_lon/2,7),
 'sc':FC['sc'],'ops':FC['ops'],'rows':FC['rows'],'bld':blds,'veg':vegs2,'ant':ant,'zone':zone,
 'ind':P['indoor_entry_loss_dB']}
PJ=json.dumps(payload)
html=r'''<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Micro-simulation réseau — hameau de Thodure (maisons, arbres, relief)</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"/>
<style>
 html,body{margin:0;height:100%;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 #map{position:absolute;inset:0}
 #ctrl{position:absolute;top:10px;left:10px;z-index:1000;background:#fff;border-radius:12px;
  box-shadow:0 2px 12px rgba(0,0,0,.25);padding:12px 14px;font-size:13px;color:#1a1a1a;width:256px;max-height:94%;overflow:auto}
 #ctrl h1{font-size:15px;margin:0 0 2px}.sub{color:#777;font-size:11px;margin:0 0 8px;line-height:1.4}
 .lbl{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#888;margin:9px 0 4px}
 .row{display:flex;flex-wrap:wrap;gap:5px}
 .chip{border:1px solid #ccc;border-radius:15px;padding:3px 9px;cursor:pointer;background:#f6f6f8;font-size:12px}
 .chip.on{background:#2d2a70;color:#fff;border-color:#2d2a70}
 .muted{color:#888;font-size:11px;line-height:1.45;margin-top:8px}
 #leg div{display:flex;align-items:center;gap:6px;font-size:11px;color:#555;margin:2px 0}
 .sw{width:16px;height:11px;border-radius:2px;display:inline-block}
</style></head><body>
<div id="map"></div>
<div id="ctrl">
 <h1>Micro-simulation réseau</h1>
 <p class="sub">Hameau de Thodure · 2500 cellules (18 m) · maisons IGN avec hauteurs réelles, bois &amp; haies, relief. Ombres des bâtiments et pertes de végétation calculées rayon par rayon.</p>
 <div class="lbl">Opérateur</div><div class="row" id="ops"></div>
 <div class="lbl">4G — bande</div><div class="row" id="sc4"></div>
 <div class="lbl">5G — bande</div><div class="row" id="sc5"></div>
 <div class="lbl">Vue</div><div class="row" id="modes"></div>
 <div class="lbl">Niveau de signal</div>
 <div id="leg">
  <div><span class="sw" style="background:#1f9e75"></span> excellent (≥ −85 dBm)</div>
  <div><span class="sw" style="background:#7bc043"></span> bon (−85…−95)</div>
  <div><span class="sw" style="background:#e6a11a"></span> moyen (−95…−105)</div>
  <div><span class="sw" style="background:#e2662c"></span> faible (−105…−113)</div>
  <div><span class="sw" style="background:#b6b6b6"></span> pas de service</div>
  <div style="margin-top:4px"><span class="sw" style="background:#9ec49a"></span> bois / haie (donnée IGN)</div>
 </div>
 <p class="muted" id="note"></p>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<script>
const P=__P__;
const OPS=P.ops;const NS=P.sc.length;
const LBL={'4G700':'700','4G800':'800','4G1800':'1800','4G2100':'2100','4G2600':'2600','5G700':'700 (n28)','5G2100':'2100 (n1)','5G3500':'3500 (n78)'};
const SCI={};P.sc.forEach((s,i)=>SCI[s]=i);
const FRQ={'4G700':'700','4G800':'800','4G1800':'1800','4G2100':'2100','4G2600':'2600','5G700':'700','5G2100':'2100','5G3500':'3500'};
let curOp=0,curSc='4G800',mode='out';
const map=L.map('map',{preferCanvas:true});
const ign=L.tileLayer('https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/jpeg&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}',{maxZoom:20,maxNativeZoom:19,attribution:'© IGN'});
const plan=L.tileLayer('https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}',{maxZoom:20,maxNativeZoom:19,attribution:'© IGN'});
ign.addTo(map);L.control.layers({'Satellite IGN':ign,'Plan IGN':plan},null,{position:'bottomleft'}).addTo(map);
map.setView([P.H[0],P.H[1]],16);
function color(v){return v>=-85?'#1f9e75':v>=-95?'#7bc043':v>=-105?'#e6a11a':v>=-113?'#e2662c':'#b6b6b6';}
// vegetation context (always visible)
P.veg.forEach(v=>L.polygon(v.r,{color:'#5e8a58',weight:1,fillColor:'#9ec49a',fillOpacity:.3}).addTo(map));
const cells=L.layerGroup().addTo(map);
const bldLayer=L.layerGroup().addTo(map);
function cellPopup(r){
  let h='<b>Cellule</b> '+(r[2]?'(dans un bâtiment)':'')+'<br><table style="font-size:11px">';
  P.sc.forEach((sc,si)=>{const v=r[3+curOp*NS+si];h+='<tr><td>'+sc+'</td><td style="text-align:right">'+(v<=-900?'—':v+' dBm')+'</td></tr>';});
  h+='</table><div style="font-size:10px;color:#777">Rayon 800 MHz : '+r[3+OPS.length*NS]+' bâtiment(s) traversé(s), '+r[4+OPS.length*NS]+' m de végétation</div>';
  return h;
}
function draw(){
  cells.clearLayers();
  const hl=P.hlat,hn=P.hlon,off=3+curOp*NS+SCI[curSc];
  const dim=(mode==='in');
  P.rows.forEach(r=>{
    const v=r[off];const c=color(v<=-900?-999:v);
    L.rectangle([[r[0]-hl,r[1]-hn],[r[0]+hl,r[1]+hn]],
      {stroke:false,fillColor:c,fillOpacity:dim?0.12:0.48})
      .bindPopup(cellPopup(r)).addTo(cells);
  });
  drawBld();
  const f=FRQ[curSc];
  document.getElementById('note').textContent = mode==='in'
    ? 'Intérieur : signal extérieur local − perte d’entrée dans le bâti ('+P.ind[f]+' dB à '+f+' MHz, ITU-R P.2109).'
    : 'Extérieur à 1,5 m du sol. Ombres des maisons et végétation incluses.';
}
function nearestRow(lat,lon){
  let best=null,bd=1e9;
  P.rows.forEach(r=>{const d=(r[0]-lat)*(r[0]-lat)+(r[1]-lon)*(r[1]-lon);if(d<bd){bd=d;best=r;}});
  return best;
}
const bldCache=P.bld.map(b=>{
  let la=0,lo=0;b.r.forEach(p=>{la+=p[0];lo+=p[1]});
  return {b:b,c:[la/b.r.length,lo/b.r.length],row:null};
});
function drawBld(){
  bldLayer.clearLayers();
  const off=3+curOp*NS+SCI[curSc];const f=FRQ[curSc];const ent=P.ind[f];
  bldCache.forEach(bc=>{
    if(!bc.row)bc.row=nearestRow(bc.c[0],bc.c[1]);
    const v=bc.row?bc.row[off]:-999;
    const vin=(v<=-900)?-999:v-ent;
    if(mode==='in'){
      L.polygon(bc.b.r,{color:'#333',weight:1,fillColor:color(vin),fillOpacity:.85})
       .bindPopup('<b>Bâtiment</b> h='+bc.b.h+' m<br>Extérieur : '+(v<=-900?'—':v+' dBm')+'<br>Intérieur estimé : '+(vin<=-900?'—':vin+' dBm'))
       .addTo(bldLayer);
    } else {
      L.polygon(bc.b.r,{color:'#222',weight:1,fillColor:'#3a3a3a',fillOpacity:.35})
       .bindPopup('<b>Bâtiment</b> h='+bc.b.h+' m<br>Extérieur ici : '+(v<=-900?'—':v+' dBm')+'<br>Intérieur estimé ('+curSc+') : '+(vin<=-900?'—':vin+' dBm'))
       .addTo(bldLayer);
    }
  });
}
L.polygon(P.zone,{color:'#fff',weight:2,fill:false,dashArray:'4 4'}).addTo(map);
L.circleMarker([P.H[0],P.H[1]],{radius:6,color:'#fff',weight:2,fillColor:'#e02424',fillOpacity:1}).addTo(map).bindPopup('Maison (495 chemin de l\'Étang)');
P.ant.forEach(a=>L.circleMarker([a.lat,a.lon],{radius:5,color:'#111',weight:1,fillColor:a.g5?'#7A3CB8':'#1E6Fd6',fillOpacity:.9}).addTo(map).bindPopup('<b>'+a.commune+'</b> '+a.dist+' km '+a.dir+'<br>'+Object.entries(a.ops).map(([o,t])=>o+': '+t.join('/')).join('<br>')));
const opsDiv=document.getElementById('ops');
OPS.forEach((o,i)=>{const b=document.createElement('span');b.className='chip'+(i===curOp?' on':'');b.textContent=o;
 b.onclick=()=>{curOp=i;[...opsDiv.children].forEach(c=>c.classList.remove('on'));b.classList.add('on');draw();};opsDiv.appendChild(b);});
function mkchips(div,keys){keys.forEach(k=>{const b=document.createElement('span');b.className='chip'+(k===curSc?' on':'');b.textContent=LBL[k];
 b.onclick=()=>{curSc=k;document.querySelectorAll('#sc4 .chip,#sc5 .chip').forEach(c=>c.classList.remove('on'));b.classList.add('on');draw();};div.appendChild(b);});}
mkchips(document.getElementById('sc4'),P.sc.filter(s=>s[0]==='4'));
mkchips(document.getElementById('sc5'),P.sc.filter(s=>s[0]==='5'));
const modes=[['out','Extérieur'],['in','Intérieur maisons']];
const mDiv=document.getElementById('modes');
modes.forEach(([k,l])=>{const b=document.createElement('span');b.className='chip'+(k===mode?' on':'');b.textContent=l;
 b.onclick=()=>{mode=k;[...mDiv.children].forEach(c=>c.classList.remove('on'));b.classList.add('on');draw();};mDiv.appendChild(b);});
draw();
</script></body></html>'''
open('/Users/bourdatloic/TEST/micro-simulation-thodure.html','w').write(html.replace('__P__',PJ))
print("map written · rows",len(FC['rows']),"· bld",len(blds),"· veg",len(vegs2))
