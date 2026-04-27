import pandas as pd
import numpy as np
import json

# --- Veri yükleme ---
df = pd.read_excel('KirsalAlan.xlsx', header=3)
cols = df.iloc[0].tolist()
df.columns = cols
df = df.iloc[1:].reset_index(drop=True)

ankara = df[df['İL ADI'] == 'ANKARA'].copy()
ankara = ankara[['İLÇE ADI', 'MAHALLE ADI', 'KÖY ADI',
                  'KENT-KIR SINIFLAMASI (3)', 'BELEDİYE/KÖY',
                  'YERLEŞİM BİRİMİ NİTELİĞİ']].copy()
ankara.columns = ['ilce', 'mahalle', 'koy', 'sinif', 'tip', 'nitelik']
ankara['yer_adi'] = ankara.apply(
    lambda r: r['mahalle'] if pd.notna(r['mahalle']) and str(r['mahalle']).strip() not in ['', 'nan']
    else r['koy'], axis=1)
ankara = ankara.reset_index(drop=True)

# --- İlçe merkez koordinatları (gerçek coğrafi merkezler) ---
ILCE_COORDS = {
    'AKYURT':         (40.1378, 33.0842, 0.06),
    'ALTINDAĞ':       (39.9567, 32.8800, 0.04),
    'AYAŞ':           (40.0219, 32.3467, 0.12),
    'BALA':           (39.5616, 33.1178, 0.20),
    'BEYPAZARI':      (40.1683, 31.9200, 0.18),
    'ÇAMLIDERE':      (40.5004, 32.5011, 0.18),
    'ÇANKAYA':        (39.8800, 32.8593, 0.06),
    'ÇUBUK':          (40.2388, 33.0394, 0.12),
    'ELMADAĞ':        (40.0125, 33.2278, 0.10),
    'ETİMESGUT':      (39.9492, 32.6738, 0.05),
    'EVREN':          (39.0258, 33.5236, 0.12),
    'GÖLBAŞI':        (39.7919, 32.8048, 0.10),
    'GÜDÜL':          (40.2167, 32.2417, 0.12),
    'HAYMANA':        (39.4317, 32.4983, 0.20),
    'KAHRAMANKAZAN':  (40.2247, 32.6883, 0.10),
    'KALECİK':        (40.2847, 33.4164, 0.14),
    'KEÇİÖREN':       (40.0061, 32.8686, 0.04),
    'KIZILCAHAMAM':   (40.4672, 32.6511, 0.18),
    'MAMAK':          (39.9547, 33.0219, 0.05),
    'NALLIHAN':       (40.1847, 31.3544, 0.18),
    'POLATLI':        (39.5839, 32.1467, 0.18),
    'PURSAKLAR':      (40.0400, 32.9061, 0.04),
    'SİNCAN':         (39.9750, 32.5806, 0.05),
    'ŞEREFLİKOÇHİSAR':(38.9433, 33.5361, 0.20),
    'YENİMAHALLE':    (39.9711, 32.7206, 0.05),
}

# Tekrarlanabilir dağılım için seed
rng = np.random.default_rng(42)

records = []
for ilce, grp in ankara.groupby('ilce'):
    if ilce not in ILCE_COORDS:
        continue
    lat0, lon0, spread = ILCE_COORDS[ilce]
    n = len(grp)
    # Düzgün ızgara + küçük jitter
    side = int(np.ceil(np.sqrt(n)))
    xs = np.linspace(-spread, spread, side)
    ys = np.linspace(-spread, spread, side)
    grid = [(x, y) for x in xs for y in ys][:n]
    jitter_lat = rng.uniform(-spread * 0.15, spread * 0.15, n)
    jitter_lon = rng.uniform(-spread * 0.15, spread * 0.15, n)
    for i, (_, row) in enumerate(grp.iterrows()):
        dlat, dlon = grid[i]
        records.append({
            'ilce': row['ilce'],
            'yer': str(row['yer_adi']),
            'sinif': row['sinif'],
            'tip': row['tip'],
            'nitelik': row['nitelik'],
            'lat': round(lat0 + dlat + jitter_lat[i], 6),
            'lon': round(lon0 + dlon + jitter_lon[i], 6),
        })

points = pd.DataFrame(records)

# --- İlçe özet istatistikleri ---
summary = ankara.groupby(['ilce', 'sinif']).size().unstack(fill_value=0)
for col in ['KIR', 'ORTA YOĞUN KENT', 'YOĞUN KENT']:
    if col not in summary.columns:
        summary[col] = 0
summary['toplam'] = summary.sum(axis=1)
summary['kir_oran'] = (summary['KIR'] / summary['toplam'] * 100).round(1)
summary = summary.reset_index()

# İlçe merkez koordinatları özete ekle
summary['lat'] = summary['ilce'].map(lambda x: ILCE_COORDS.get(x, (39.93, 32.85, 0))[0])
summary['lon'] = summary['ilce'].map(lambda x: ILCE_COORDS.get(x, (39.93, 32.85, 0))[1])

# JSON'a çevir
points_json = points.to_dict(orient='records')
summary_json = summary.to_dict(orient='records')

# --- HTML Harita ---
html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ankara Kent-Kır Sınıflaması Haritası</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #eee; height: 100vh; display: flex; flex-direction: column; }}
  #header {{ background: linear-gradient(135deg, #16213e 0%, #0f3460 100%); padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 10px rgba(0,0,0,0.5); z-index: 1000; }}
  #header h1 {{ font-size: 1.1rem; font-weight: 700; color: #e2e8f0; letter-spacing: 0.5px; }}
  #header .subtitle {{ font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }}
  #controls {{ background: #16213e; padding: 8px 20px; display: flex; gap: 12px; align-items: center; border-bottom: 1px solid #0f3460; flex-wrap: wrap; }}
  .filter-btn {{ padding: 5px 14px; border: none; border-radius: 20px; cursor: pointer; font-size: 0.8rem; font-weight: 600; transition: all 0.2s; opacity: 0.5; }}
  .filter-btn.active {{ opacity: 1; transform: scale(1.05); box-shadow: 0 2px 8px rgba(0,0,0,0.4); }}
  .filter-btn.kir {{ background: #16a34a; color: white; }}
  .filter-btn.orta {{ background: #d97706; color: white; }}
  .filter-btn.yogun {{ background: #dc2626; color: white; }}
  .filter-btn.all {{ background: #475569; color: white; opacity: 1; }}
  #view-toggle {{ margin-left: auto; display: flex; gap: 6px; }}
  .view-btn {{ padding: 5px 12px; border: 1px solid #334155; border-radius: 6px; cursor: pointer; font-size: 0.78rem; background: transparent; color: #94a3b8; transition: all 0.2s; }}
  .view-btn.active {{ background: #0f3460; color: #e2e8f0; border-color: #3b82f6; }}
  #map {{ flex: 1; }}
  #legend {{ position: absolute; bottom: 30px; right: 10px; z-index: 1000; background: rgba(22, 33, 62, 0.95); border: 1px solid #0f3460; border-radius: 10px; padding: 14px 18px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); min-width: 200px; }}
  #legend h4 {{ font-size: 0.82rem; color: #94a3b8; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }}
  .legend-item {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 0.85rem; }}
  .legend-dot {{ width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; border: 2px solid rgba(255,255,255,0.3); }}
  .legend-count {{ margin-left: auto; color: #64748b; font-size: 0.78rem; }}
  #stats {{ position: absolute; top: 120px; left: 10px; z-index: 1000; background: rgba(22, 33, 62, 0.95); border: 1px solid #0f3460; border-radius: 10px; padding: 14px 18px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); min-width: 160px; }}
  #stats h4 {{ font-size: 0.78rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }}
  .stat-row {{ margin-bottom: 8px; }}
  .stat-label {{ font-size: 0.75rem; color: #94a3b8; }}
  .stat-bar-bg {{ background: #0f3460; border-radius: 4px; height: 8px; margin-top: 3px; overflow: hidden; }}
  .stat-bar {{ height: 100%; border-radius: 4px; transition: width 0.4s; }}
  .stat-val {{ font-size: 0.78rem; color: #e2e8f0; float: right; }}
</style>
</head>
<body>
<div id="header">
  <div>
    <h1>Ankara İli Kent-Kır Sınıflaması Haritası</h1>
    <div class="subtitle">TKDK · 31 Aralık 2022 · 1,432 Yerleşim Birimi</div>
  </div>
</div>
<div id="controls">
  <button class="filter-btn all active" onclick="filterMap('TÜM')">Tümü (1432)</button>
  <button class="filter-btn kir" onclick="filterMap('KIR')">🟢 Kır (956)</button>
  <button class="filter-btn orta" onclick="filterMap('ORTA YOĞUN KENT')">🟡 Orta Yoğun Kent (106)</button>
  <button class="filter-btn yogun" onclick="filterMap('YOĞUN KENT')">🔴 Yoğun Kent (370)</button>
  <div id="view-toggle">
    <button class="view-btn active" id="btn-points" onclick="setView('points')">Noktasal</button>
    <button class="view-btn" id="btn-district" onclick="setView('district')">İlçe Özeti</button>
  </div>
</div>
<div id="map"></div>

<div id="legend">
  <h4>Sınıflama</h4>
  <div class="legend-item"><div class="legend-dot" style="background:#16a34a"></div> Kır <span class="legend-count">956</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:#d97706"></div> Orta Yoğun Kent <span class="legend-count">106</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:#dc2626"></div> Yoğun Kent <span class="legend-count">370</span></div>
  <hr style="border-color:#1e3a5f; margin:10px 0;">
  <div style="font-size:0.72rem; color:#64748b;">Hibe desteğine uygun:<br><span style="color:#16a34a; font-weight:600;">KIR</span> sınıfındaki alanlar</div>
</div>

<div id="stats">
  <h4>Ankara Özeti</h4>
  <div class="stat-row">
    <span class="stat-val" style="color:#16a34a">66.8%</span>
    <div class="stat-label">Kır</div>
    <div class="stat-bar-bg"><div class="stat-bar" style="width:66.8%;background:#16a34a"></div></div>
  </div>
  <div class="stat-row">
    <span class="stat-val" style="color:#d97706">7.4%</span>
    <div class="stat-label">Orta Yoğun Kent</div>
    <div class="stat-bar-bg"><div class="stat-bar" style="width:7.4%;background:#d97706"></div></div>
  </div>
  <div class="stat-row">
    <span class="stat-val" style="color:#dc2626">25.8%</span>
    <div class="stat-label">Yoğun Kent</div>
    <div class="stat-bar-bg"><div class="stat-bar" style="width:25.8%;background:#dc2626"></div></div>
  </div>
  <hr style="border-color:#1e3a5f; margin:10px 0;">
  <div style="font-size:0.72rem; color:#64748b;">25 İlçe</div>
</div>

<script>
const POINTS = {json.dumps(points_json, ensure_ascii=False)};
const SUMMARY = {json.dumps(summary_json, ensure_ascii=False)};

const COLOR = {{
  'KIR': '#16a34a',
  'ORTA YOĞUN KENT': '#d97706',
  'YOĞUN KENT': '#dc2626'
}};

const map = L.map('map', {{
  center: [39.93, 32.85],
  zoom: 9,
  zoomControl: true,
  preferCanvas: true
}});

L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '&copy; OpenStreetMap &copy; CARTO',
  subdomains: 'abcd',
  maxZoom: 19
}}).addTo(map);

// --- Noktasal katman ---
let clusterGroup = L.markerClusterGroup({{
  maxClusterRadius: 40,
  iconCreateFunction: function(cluster) {{
    const children = cluster.getAllChildMarkers();
    const counts = {{'KIR':0,'ORTA YOĞUN KENT':0,'YOĞUN KENT':0}};
    children.forEach(m => counts[m.options.sinif] = (counts[m.options.sinif]||0)+1);
    const dominant = Object.keys(counts).reduce((a,b) => counts[a]>counts[b]?a:b);
    const col = COLOR[dominant];
    const n = cluster.getChildCount();
    const size = n > 100 ? 44 : n > 30 ? 36 : 28;
    return L.divIcon({{
      html: `<div style="background:${{col}};width:${{size}}px;height:${{size}}px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:${{size>36?13:11}}px;border:2px solid rgba(255,255,255,0.4);box-shadow:0 2px 6px rgba(0,0,0,0.5)">${{n}}</div>`,
      className: '',
      iconSize: [size, size],
      iconAnchor: [size/2, size/2]
    }});
  }}
}});

const allMarkers = [];
POINTS.forEach(p => {{
  const col = COLOR[p.sinif] || '#888';
  const marker = L.circleMarker([p.lat, p.lon], {{
    radius: 6,
    fillColor: col,
    color: 'rgba(255,255,255,0.5)',
    weight: 1,
    fillOpacity: 0.85,
    sinif: p.sinif
  }});
  marker.bindPopup(`
    <div style="font-family:Segoe UI,Arial;min-width:180px">
      <div style="font-weight:700;font-size:1rem;margin-bottom:4px">${{p.yer}}</div>
      <div style="color:#666;font-size:0.85rem;margin-bottom:8px">📍 ${{p.ilce}} İlçesi</div>
      <div style="background:${{col}};color:white;padding:4px 10px;border-radius:12px;font-size:0.82rem;font-weight:600;display:inline-block">${{p.sinif}}</div>
      <div style="margin-top:8px;font-size:0.78rem;color:#888">${{p.tip}} · ${{p.nitelik}}</div>
      ${{p.sinif==='KIR' ? '<div style="margin-top:6px;font-size:0.78rem;color:#16a34a;font-weight:600">✓ TKDK Hibe Desteğine Uygun</div>' : ''}}
    </div>
  `);
  clusterGroup.addLayer(marker);
  allMarkers.push(marker);
}});
map.addLayer(clusterGroup);

// --- İlçe özet katmanı ---
let districtLayer = L.layerGroup();
SUMMARY.forEach(s => {{
  const kirOran = s['kir_oran'];
  const toplam = s['toplam'];
  const kir = s['KIR'] || 0;
  const orta = s['ORTA YOĞUN KENT'] || 0;
  const yogun = s['YOĞUN KENT'] || 0;

  // Pasta benzeri renk seçimi - çoğunluğa göre
  let col, r;
  if (kir >= orta && kir >= yogun) {{ col = '#16a34a'; r = 18 + kir/20; }}
  else if (orta >= yogun) {{ col = '#d97706'; r = 16 + orta/5; }}
  else {{ col = '#dc2626'; r = 16 + yogun/20; }}
  r = Math.min(r, 45);

  const circle = L.circleMarker([s.lat, s.lon], {{
    radius: r,
    fillColor: col,
    color: 'white',
    weight: 2,
    fillOpacity: 0.75
  }});

  circle.bindTooltip(`<b>${{s.ilce}}</b>`, {{permanent: false}});
  circle.bindPopup(`
    <div style="font-family:Segoe UI,Arial;min-width:220px">
      <div style="font-weight:700;font-size:1.05rem;margin-bottom:8px">📍 ${{s.ilce}}</div>
      <table style="width:100%;font-size:0.85rem;border-collapse:collapse">
        <tr><td style="padding:3px 0;color:#16a34a">🟢 Kır</td><td style="text-align:right;font-weight:600">${{kir}}</td><td style="text-align:right;color:#888">${{kirOran}}%</td></tr>
        <tr><td style="padding:3px 0;color:#d97706">🟡 Orta Yoğun Kent</td><td style="text-align:right;font-weight:600">${{orta}}</td><td style="text-align:right;color:#888">${{(orta/toplam*100).toFixed(1)}}%</td></tr>
        <tr><td style="padding:3px 0;color:#dc2626">🔴 Yoğun Kent</td><td style="text-align:right;font-weight:600">${{yogun}}</td><td style="text-align:right;color:#888">${{(yogun/toplam*100).toFixed(1)}}%</td></tr>
        <tr style="border-top:1px solid #eee"><td style="padding-top:5px;font-weight:600">Toplam</td><td style="text-align:right;font-weight:600;padding-top:5px">${{toplam}}</td><td></td></tr>
      </table>
    </div>
  `);
  districtLayer.addLayer(circle);

  // İlçe adı etiketi
  L.marker([s.lat, s.lon], {{
    icon: L.divIcon({{
      html: `<div style="font-size:9px;font-weight:700;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.9);white-space:nowrap;pointer-events:none">${{s.ilce}}</div>`,
      className: '',
      iconSize: [100, 16],
      iconAnchor: [50, -r-2]
    }})
  }}).addTo(districtLayer);
}});

// --- Görünüm kontrolü ---
let currentView = 'points';
let currentFilter = 'TÜM';

function setView(view) {{
  currentView = view;
  document.getElementById('btn-points').classList.toggle('active', view==='points');
  document.getElementById('btn-district').classList.toggle('active', view==='district');
  if (view === 'points') {{
    map.removeLayer(districtLayer);
    map.addLayer(clusterGroup);
  }} else {{
    map.removeLayer(clusterGroup);
    map.addLayer(districtLayer);
  }}
}}

function filterMap(sinif) {{
  currentFilter = sinif;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');

  clusterGroup.clearLayers();
  allMarkers.forEach(m => {{
    if (sinif === 'TÜM' || m.options.sinif === sinif) {{
      clusterGroup.addLayer(m);
    }}
  }});
}}
</script>
</body>
</html>
"""

with open('ankara_harita.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Harita oluşturuldu: ankara_harita.html")
print(f"Toplam nokta: {len(points)}")
print(f"\nİlçe bazlı KIR yüzdesi:")
print(summary[['ilce','KIR','ORTA YOĞUN KENT','YOĞUN KENT','toplam','kir_oran']].sort_values('kir_oran', ascending=False).to_string(index=False))