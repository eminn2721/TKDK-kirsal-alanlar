import json
import pandas as pd
import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import shape, Polygon
from shapely.ops import unary_union

# ── Veri ──────────────────────────────────────────────────────────────────
df = pd.read_excel('ankara_kir_alanlar.xlsx')
df['YER'] = df.apply(
    lambda r: r['MAHALLE ADI'] if pd.notna(r['MAHALLE ADI']) and str(r['MAHALLE ADI']).strip() not in ['','nan']
    else r['KÖY ADI'], axis=1)

by_ilce = df.groupby('İLÇE ADI')['YER'].apply(list).to_dict()
counts  = df.groupby('İLÇE ADI').size().sort_values(ascending=False).to_dict()

# ── Ankara il sınırı ──────────────────────────────────────────────────────
with open('/tmp/ne_admin1.json', encoding='utf-8') as f:
    ne = json.load(f)
ankara_feat = next(
    ft for ft in ne['features']
    if ft['properties'].get('admin') == 'Turkey'
    and 'Ankara' in str(ft['properties'].get('name',''))
)
ankara_poly = shape(ankara_feat['geometry'])

# ── İlçe merkezleri ──────────────────────────────────────────────────────
CENTROIDS = {
    'AKYURT':          (40.1338, 33.0895),
    'ALTINDAĞ':        (39.9532, 32.8782),
    'AYAŞ':            (40.0173, 32.3470),
    'BALA':            (39.5530, 33.1224),
    'BEYPAZARI':       (40.1690, 31.9212),
    'ÇAMLIDERE':       (40.4988, 32.4952),
    'ÇANKAYA':         (39.8731, 32.8517),
    'ÇUBUK':           (40.2395, 33.0388),
    'ELMADAĞ':         (40.0139, 33.2293),
    'ETİMESGUT':       (39.9454, 32.6706),
    'EVREN':           (39.0268, 33.5250),
    'GÖLBAŞI':         (39.7919, 32.8057),
    'GÜDÜL':           (40.2167, 32.2423),
    'HAYMANA':         (39.4314, 32.4993),
    'KAHRAMANKAZAN':   (40.2237, 32.6873),
    'KALECİK':         (40.2836, 33.4157),
    'KEÇİÖREN':        (40.0047, 32.8697),
    'KIZILCAHAMAM':    (40.4664, 32.6516),
    'MAMAK':           (39.9572, 33.0234),
    'NALLIHAN':        (40.1847, 31.3547),
    'POLATLI':         (39.5842, 32.1479),
    'PURSAKLAR':       (40.0378, 32.8989),
    'SİNCAN':          (39.9721, 32.5818),
    'ŞEREFLİKOÇHİSAR': (38.9427, 33.5361),
    'YENİMAHALLE':     (39.9653, 32.7153),
}

# ── Voronoi ──────────────────────────────────────────────────────────────
ilce_list = list(CENTROIDS.keys())
pts  = np.array([[CENTROIDS[i][1], CENTROIDS[i][0]] for i in ilce_list])
b    = ankara_poly.bounds
mg   = 3.0
far  = np.array([[b[0]-mg,b[1]-mg],[b[2]+mg,b[1]-mg],[b[0]-mg,b[3]+mg],[b[2]+mg,b[3]+mg],
                  [(b[0]+b[2])/2,b[1]-mg],[(b[0]+b[2])/2,b[3]+mg],
                  [b[0]-mg,(b[1]+b[3])/2],[b[2]+mg,(b[1]+b[3])/2]])
vor  = Voronoi(np.vstack([pts, far]))

regions = {}
for idx, ilce in enumerate(ilce_list):
    reg = vor.regions[vor.point_region[idx]]
    if -1 in reg or not reg: continue
    try:
        poly = Polygon([vor.vertices[v] for v in reg]).intersection(ankara_poly)
        if not poly.is_empty:
            regions[ilce] = poly
    except Exception:
        pass

# ── GeoJSON ───────────────────────────────────────────────────────────────
max_count = max(counts.values())

features = []
for ilce, poly in regions.items():
    n = counts.get(ilce, 0)
    features.append({
        'type': 'Feature',
        'properties': {
            'ilce': ilce,
            'count': n,
            'intensity': round(n / max_count, 4),
            'settlements': sorted(by_ilce.get(ilce, [])),
            'lat': CENTROIDS[ilce][0],
            'lon': CENTROIDS[ilce][1],
        },
        'geometry': poly.__geo_interface__,
    })

geojson_js  = json.dumps({'type':'FeatureCollection','features':features}, ensure_ascii=False)
boundary_js = json.dumps(ankara_poly.__geo_interface__, ensure_ascii=False)

# ── Bar chart verisi (sıralı) ─────────────────────────────────────────────
sorted_ilce  = sorted(counts.keys(), key=lambda x: counts[x], reverse=True)
bar_labels   = json.dumps(sorted_ilce, ensure_ascii=False)
bar_values   = json.dumps([counts[i] for i in sorted_ilce])

# ── HTML ──────────────────────────────────────────────────────────────────
html = """\
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ankara Kırsal Alan Haritası — TKDK</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{
  --bg:#07090f; --surface:#0f1623; --surface2:#151e2e; --border:#1e3048;
  --green:#22c55e; --green-dim:#16a34a; --green-dark:#14532d; --green-pale:#bbf7d0;
  --text:#e2e8f0; --muted:#64748b; --accent:#38bdf8;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* HEADER */
#hdr{
  background:linear-gradient(90deg,#071a2f 0%,#0f2d1a 100%);
  border-bottom:1px solid var(--border);
  padding:10px 24px;display:flex;align-items:center;gap:32px;flex-shrink:0;
  box-shadow:0 2px 20px rgba(0,0,0,.6);
}
#hdr h1{font-size:.95rem;font-weight:700;color:#f0fdf4;letter-spacing:.3px}
#hdr .sub{font-size:.7rem;color:var(--muted);margin-top:1px}
.kpi{display:flex;flex-direction:column;align-items:center;padding:0 20px;border-left:1px solid var(--border)}
.kpi .val{font-size:1.4rem;font-weight:800;color:var(--green);line-height:1}
.kpi .lbl{font-size:.65rem;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:.5px}
#search-wrap{margin-left:auto;position:relative}
#search-wrap input{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:6px 12px 6px 32px;color:var(--text);font-size:.8rem;width:200px;outline:none;transition:border .2s}
#search-wrap input:focus{border-color:var(--green-dim)}
#search-wrap::before{content:'⌕';position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:1rem;pointer-events:none}

/* BODY */
#body{display:flex;flex:1;overflow:hidden}

/* SIDEBAR */
#sidebar{
  width:340px;flex-shrink:0;
  background:var(--surface);border-right:1px solid var(--border);
  display:flex;flex-direction:column;overflow:hidden;
}
#chart-wrap{padding:14px;border-bottom:1px solid var(--border);flex-shrink:0}
#chart-wrap h3{font-size:.7rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:10px}
#barChart{max-height:220px}
#list-header{padding:10px 14px 8px;border-bottom:1px solid var(--border);flex-shrink:0}
#list-header h3{font-size:.7rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted)}
#list-header .count{font-size:.72rem;color:var(--green);font-weight:600;margin-top:2px}
#list{flex:1;overflow-y:auto;padding:8px 0}
#list::-webkit-scrollbar{width:4px}
#list::-webkit-scrollbar-track{background:transparent}
#list::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.ilce-group{}
.ilce-hdr{
  padding:7px 14px;font-size:.72rem;font-weight:700;color:var(--green);
  display:flex;align-items:center;justify-content:space-between;
  cursor:pointer;user-select:none;transition:background .15s;
  position:sticky;top:0;background:var(--surface);z-index:1;
}
.ilce-hdr:hover{background:var(--surface2)}
.ilce-hdr .badge{background:var(--green-dark);color:var(--green-pale);font-size:.65rem;padding:1px 7px;border-radius:10px}
.ilce-hdr .arrow{font-size:.7rem;color:var(--muted);transition:transform .2s}
.ilce-hdr.open .arrow{transform:rotate(90deg)}
.mah-list{display:none;padding:0 0 4px 0}
.ilce-hdr.open + .mah-list{display:block}
.mah-item{
  padding:5px 14px 5px 24px;font-size:.77rem;color:#94a3b8;
  cursor:pointer;transition:all .15s;border-left:2px solid transparent;margin-left:14px;
}
.mah-item:hover{color:#f0fdf4;background:var(--surface2);border-left-color:var(--green)}
.mah-item.highlight{color:var(--green);background:rgba(34,197,94,.07);border-left-color:var(--green)}
.hidden{display:none!important}

/* MAP */
#map{flex:1}
.leaflet-popup-content-wrapper{background:rgba(10,15,30,.97);color:var(--text);border:1px solid var(--border);border-radius:10px;box-shadow:0 8px 32px rgba(0,0,0,.7)}
.leaflet-popup-tip{background:rgba(10,15,30,.97)}
.leaflet-popup-content{margin:14px 16px}
.popup-title{font-size:1rem;font-weight:700;color:#f0fdf4;border-bottom:2px solid var(--green);padding-bottom:7px;margin-bottom:10px}
.popup-count{font-size:1.8rem;font-weight:800;color:var(--green);line-height:1}
.popup-label{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
.popup-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:10px;max-height:160px;overflow-y:auto}
.popup-mah{font-size:.74rem;color:#94a3b8;padding:3px 6px;background:var(--surface2);border-radius:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.popup-note{font-size:.68rem;color:var(--muted);margin-top:8px;padding-top:6px;border-top:1px solid var(--border);color:var(--green);font-weight:600}
</style>
</head>
<body>

<div id="hdr">
  <div>
    <h1>Ankara İli — Kırsal Alan Haritası</h1>
    <div class="sub">TKDK Kent-Kır Sınıflaması · 31 Aralık 2022 · Hibe Desteğine Uygun Alanlar</div>
  </div>
  <div class="kpi"><div class="val">956</div><div class="lbl">Kırsal Yerleşim</div></div>
  <div class="kpi"><div class="val">25</div><div class="lbl">İlçe</div></div>
  <div class="kpi"><div class="val">105</div><div class="lbl">En Fazla (Kızılcahamam)</div></div>
  <div id="search-wrap"><input type="text" id="search" placeholder="Mahalle / köy ara…" oninput="onSearch(this.value)"></div>
</div>

<div id="body">
  <div id="sidebar">
    <div id="chart-wrap">
      <h3>İlçe Bazlı Kırsal Yerleşim Sayısı</h3>
      <canvas id="barChart"></canvas>
    </div>
    <div id="list-header">
      <h3>Yerleşim Birimleri</h3>
      <div class="count" id="list-count">956 yerleşim · 25 ilçe</div>
    </div>
    <div id="list"></div>
  </div>
  <div id="map"></div>
</div>

<script>
const GEO      = """ + geojson_js + """;
const BOUNDARY = """ + boundary_js + """;
const BAR_LABELS = """ + bar_labels + """;
const BAR_VALUES = """ + bar_values + """;

// ── Renk ──────────────────────────────────────────────────────────────────
function intensityColor(t, alpha){
  // t: 0..1  →  koyu yeşilden açık yeşile (ters: çok alan = koyu)
  const r = Math.round(5  + t*(187-5));
  const g = Math.round(83 + t*(247-83));
  const b = Math.round(43 + t*(176-43));
  return alpha != null ? `rgba(${r},${g},${b},${alpha})` : `rgb(${r},${g},${b})`;
}

// ── Bar Chart ─────────────────────────────────────────────────────────────
const ctx = document.getElementById('barChart').getContext('2d');
new Chart(ctx, {
  type: 'bar',
  data: {
    labels: BAR_LABELS,
    datasets:[{
      data: BAR_VALUES,
      backgroundColor: BAR_VALUES.map(v => intensityColor(v/105, 0.85)),
      borderColor: BAR_VALUES.map(v => intensityColor(v/105, 1)),
      borderWidth: 1,
      borderRadius: 3,
    }]
  },
  options:{
    indexAxis:'y',
    responsive:true,
    maintainAspectRatio:false,
    plugins:{legend:{display:false},tooltip:{
      callbacks:{label: ctx => ' '+ctx.raw+' kırsal mahalle/köy'}
    }},
    scales:{
      x:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#64748b',font:{size:10}}},
      y:{grid:{display:false},ticks:{color:'#94a3b8',font:{size:9}}}
    }
  }
});

// ── Sidebar listesi ───────────────────────────────────────────────────────
const listEl = document.getElementById('list');

function buildList(filterText){
  listEl.innerHTML = '';
  let totalVisible = 0;
  let ilceVisible = 0;

  GEO.features
    .slice().sort((a,b) => b.properties.count - a.properties.count)
    .forEach(feat => {
      const p = feat.properties;
      const settlements = p.settlements;
      const filtered = filterText
        ? settlements.filter(s => s.toLowerCase().includes(filterText.toLowerCase()))
        : settlements;
      if(!filtered.length) return;

      totalVisible += filtered.length;
      ilceVisible++;

      const grp = document.createElement('div');
      grp.className = 'ilce-group';

      const hdr = document.createElement('div');
      hdr.className = 'ilce-hdr';
      hdr.dataset.ilce = p.ilce;
      hdr.innerHTML = `<span>${p.ilce}</span><span class="badge">${filtered.length}</span><span class="arrow">›</span>`;
      if(filterText) hdr.classList.add('open');
      hdr.onclick = () => {
        hdr.classList.toggle('open');
        flyToDistrict(p.ilce);
      };

      const mahDiv = document.createElement('div');
      mahDiv.className = 'mah-list';
      filtered.forEach(m => {
        const item = document.createElement('div');
        item.className = 'mah-item';
        item.textContent = m;
        item.dataset.ilce = p.ilce;
        item.onclick = () => flyToDistrict(p.ilce);
        mahDiv.appendChild(item);
      });

      grp.appendChild(hdr);
      grp.appendChild(mahDiv);
      listEl.appendChild(grp);
    });

  document.getElementById('list-count').textContent =
    `${totalVisible} yerleşim · ${ilceVisible} ilçe`;
}
buildList('');

function onSearch(val){
  buildList(val.trim());
}

// ── Leaflet Haritası ─────────────────────────────────────────────────────
const map = L.map('map',{center:[39.75,32.5],zoom:8,zoomControl:true,preferCanvas:true});

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{
  attribution:'© OpenStreetMap © CARTO', subdomains:'abcd', maxZoom:19
}).addTo(map);

// Ankara il sınırı
L.geoJSON({type:'Feature',properties:{},geometry:BOUNDARY},{
  style:{color:'#38bdf8',weight:2,fill:false,dashArray:'6 4',opacity:.7}
}).addTo(map);

// Choropleth katmanı
let activeLayer = null;
const districtLayers = {};

const choropleth = L.geoJSON(GEO,{
  style: feat => {
    const t = feat.properties.intensity;
    return {
      fillColor: intensityColor(t, null),
      fillOpacity: 0.55 + t*0.30,
      color: '#0a0f1e',
      weight: 1.5,
    };
  },
  onEachFeature: (feat, layer) => {
    const p = feat.properties;
    districtLayers[p.ilce] = layer;

    const mahRows = p.settlements.slice(0,20)
      .map(m => `<div class="popup-mah">${m}</div>`).join('');
    const extra = p.settlements.length > 20 ? `<div class="popup-note">+${p.settlements.length-20} yerleşim daha…</div>` : '';

    layer.bindPopup(`
      <div class="popup-title">📍 ${p.ilce}</div>
      <div class="popup-count">${p.count}</div>
      <div class="popup-label">Kırsal Yerleşim Birimi</div>
      <div class="popup-grid">${mahRows}</div>
      ${extra}
      <div class="popup-note" style="margin-top:8px">✓ TKDK Hibe Desteğine Uygun</div>
    `, {maxWidth:340});

    layer.on('mouseover', e => {
      if(activeLayer !== layer)
        layer.setStyle({fillOpacity:Math.min(0.9, 0.55+p.intensity*0.30+0.2), weight:2.5, color:'#22c55e'});
    });
    layer.on('mouseout', e => {
      if(activeLayer !== layer)
        choropleth.resetStyle(layer);
    });
    layer.on('click', () => {
      if(activeLayer && activeLayer !== layer) choropleth.resetStyle(activeLayer);
      activeLayer = layer;
      layer.setStyle({fillOpacity:0.9, weight:3, color:'#86efac'});
      highlightSidebar(p.ilce);
    });
  }
}).addTo(map);

// İlçe etiketleri
GEO.features.forEach(feat => {
  const p = feat.properties;
  L.marker([p.lat, p.lon],{
    icon: L.divIcon({
      html:`<div style="font-size:9px;font-weight:700;color:rgba(255,255,255,.85);text-shadow:0 1px 3px rgba(0,0,0,.9);pointer-events:none;white-space:nowrap;text-align:center">${p.ilce}</div>`,
      className:'', iconSize:[120,14], iconAnchor:[60,7]
    }), interactive:false
  }).addTo(map);
});

// ── Etkileşim ─────────────────────────────────────────────────────────────
function flyToDistrict(ilce){
  const layer = districtLayers[ilce];
  if(!layer) return;
  if(activeLayer && activeLayer !== layer) choropleth.resetStyle(activeLayer);
  activeLayer = layer;
  layer.setStyle({fillOpacity:0.9, weight:3, color:'#86efac'});
  map.flyToBounds(layer.getBounds(), {padding:[40,40], duration:.8});
  layer.openPopup();
}

function highlightSidebar(ilce){
  document.querySelectorAll('.ilce-hdr').forEach(h => {
    const isTarget = h.dataset.ilce === ilce;
    if(isTarget){
      h.classList.add('open');
      h.scrollIntoView({behavior:'smooth', block:'nearest'});
    }
  });
  document.querySelectorAll('.mah-item').forEach(el => {
    el.classList.toggle('highlight', el.dataset.ilce === ilce);
  });
}
</script>
</body>
</html>
"""

with open('ankara_kir_dashboard.html','w',encoding='utf-8') as f:
    f.write(html)

kb = len(html)//1024
print(f"Oluşturuldu: ankara_kir_dashboard.html  ({kb} KB)")
print(f"İlçe polygon sayısı: {len(features)}")
