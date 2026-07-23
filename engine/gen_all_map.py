import json
SG=json.load(open('sim_all_grid.json'))
G=json.load(open('grid.json'))
bld=json.load(open('buildings.json'))
TD=json.load(open('tool_data.json'))
step_lat=2*G['dlat']/(G['N']-1);step_lon=2*G['dlon']/(G['N']-1)
zone=[[45.309896,5.146548],[45.310055,5.146829],[45.310079,5.14692],[45.309847,5.147749],[45.309655,5.147588],[45.309692,5.14725],[45.309553,5.147079],[45.309806,5.14644]]
ant=[{'lat':a['lat'],'lon':a['lon'],'commune':a['commune'],'dist':a['dist'],'dir':a['dir'],
      'g5':any('5G' in v['tech'] for v in a['ops'].values()),
      'ops':{k:v['tech'] for k,v in a['ops'].items()}} for a in TD['antennas']]
payload={'H':G['H'],'hlat':round(step_lat/2,6),'hlon':round(step_lon/2,6),
         'sc':SG['sc'],'pts':SG['pts'],'zone':zone,'ant':ant,'bld':bld}
P=json.dumps(payload)
html=r'''<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Simulation 4G & 5G par bande — hameau de Thodure</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"/>
<style>
 html,body{margin:0;height:100%;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 #map{position:absolute;inset:0}
 #ctrl{position:absolute;top:10px;left:10px;z-index:1000;background:#fff;border-radius:12px;
  box-shadow:0 2px 12px rgba(0,0,0,.25);padding:12px 14px;font-size:13px;color:#1a1a1a;width:250px}
 #ctrl h1{font-size:15px;margin:0 0 2px}.sub{color:#777;font-size:11px;margin:0 0 8px}
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
 <h1>Simulation 4G &amp; 5G</h1>
 <p class="sub">Hameau de Thodure · bâtiments réels (OSM) · modèle terrain IGN</p>
 <div class="lbl">Opérateur</div><div class="row" id="ops"></div>
 <div class="lbl">4G — bande</div><div class="row" id="sc4"></div>
 <div class="lbl">5G — bande</div><div class="row" id="sc5"></div>
 <div class="lbl">Niveau de signal</div>
 <div id="leg">
  <div><span class="sw" style="background:#1f9e75"></span> excellent (≥ −85 dBm)</div>
  <div><span class="sw" style="background:#7bc043"></span> bon (−85…−95)</div>
  <div><span class="sw" style="background:#e6a11a"></span> moyen (−95…−105)</div>
  <div><span class="sw" style="background:#e2662c"></span> faible (−105…−113)</div>
  <div><span class="sw" style="background:#cccccc"></span> pas de service</div>
 </div>
 <p class="muted" id="note"></p>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<script>
const P=__P__;
const OPS=P.ops||['Orange','SFR','Bouygues','Free'];
const LBL={'4G700':'700 (B28)','4G800':'800 (B20)','4G1800':'1800 (B3)','4G2100':'2100 (B1)','4G2600':'2600 (B7)','5G700':'700 (n28)','5G2100':'2100 (n1)','5G3500':'3500 (n78)'};
const RNG={'4G700':'longue portée','4G800':'longue portée','4G1800':'portée moyenne','4G2100':'portée moyenne','4G2600':'courte portée (~5 km)','5G700':'longue portée','5G2100':'portée moyenne (~6 km)','5G3500':'très courte portée (~2,5 km)'};
const SCI={};P.sc.forEach((s,i)=>SCI[s]=i);
let curOp=0, curSc='4G800';
const map=L.map('map');
const ign=L.tileLayer('https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/jpeg&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}',{maxZoom:20,maxNativeZoom:19,attribution:'© IGN'});
const plan=L.tileLayer('https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}',{maxZoom:20,maxNativeZoom:19,attribution:'© IGN'});
const osm=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:20,attribution:'© OSM'});
ign.addTo(map);L.control.layers({'Satellite IGN':ign,'Plan IGN':plan,'Plan OSM':osm},null,{position:'bottomleft'}).addTo(map);
map.setView([P.H[0],P.H[1]],16);
const cells=L.layerGroup().addTo(map);
const NS=P.sc.length;
function color(v){return v>=-85?'#1f9e75':v>=-95?'#7bc043':v>=-105?'#e6a11a':v>=-113?'#e2662c':null;}
function draw(){
 cells.clearLayers();const hl=P.hlat,hn=P.hlon,off=2+curOp*NS+SCI[curSc];
 P.pts.forEach(r=>{const v=r[off];const c=color(v);if(!c)return;
  L.rectangle([[r[0]-hl,r[1]-hn],[r[0]+hl,r[1]+hn]],{stroke:false,fillColor:c,fillOpacity:.5}).addTo(cells);});
 const tech=curSc[0]==='4'?'4G':'5G';
 document.getElementById('note').textContent=tech+' '+LBL[curSc]+' — '+RNG[curSc]+'.';
}
P.bld.forEach(ring=>L.polygon(ring,{color:'#222',weight:1,fill:true,fillColor:'#444',fillOpacity:.25}).addTo(map));
L.polygon(P.zone,{color:'#fff',weight:2,fill:false,dashArray:'4 4'}).addTo(map);
L.circleMarker([P.H[0],P.H[1]],{radius:6,color:'#fff',weight:2,fillColor:'#e02424',fillOpacity:1}).addTo(map).bindPopup('Maison');
P.ant.forEach(a=>L.circleMarker([a.lat,a.lon],{radius:5,color:'#111',weight:1,fillColor:a.g5?'#7A3CB8':'#1E6Fd6',fillOpacity:.9}).addTo(map).bindPopup('<b>'+a.commune+'</b> '+a.dist+'km '+a.dir+'<br>'+Object.entries(a.ops).map(([o,t])=>o+': '+t.join('/')).join('<br>')));
function mkchips(div,keys){keys.forEach(k=>{const b=document.createElement('span');b.className='chip'+(k===curSc?' on':'');b.textContent=LBL[k];
 b.onclick=()=>{curSc=k;document.querySelectorAll('#sc4 .chip,#sc5 .chip').forEach(c=>c.classList.remove('on'));b.classList.add('on');draw();};div.appendChild(b);});}
const opsDiv=document.getElementById('ops');
OPS.forEach((o,i)=>{const b=document.createElement('span');b.className='chip'+(i===curOp?' on':'');b.textContent=o;
 b.onclick=()=>{curOp=i;[...opsDiv.children].forEach(c=>c.classList.remove('on'));b.classList.add('on');draw();};opsDiv.appendChild(b);});
mkchips(document.getElementById('sc4'),P.sc.filter(s=>s[0]==='4'));
mkchips(document.getElementById('sc5'),P.sc.filter(s=>s[0]==='5'));
draw();
</script></body></html>'''
open('/Users/bourdatloic/TEST/simulation-4g-5g-hameau-thodure.html','w').write(html.replace('__P__',P))
print("written · scenarios",SG['sc'],"· pts",len(SG['pts']))
