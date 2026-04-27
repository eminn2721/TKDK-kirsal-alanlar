"""
Ankara Kent-Kır Sınıflaması - Voronoi Choropleth Haritası
Veri: KirsalAlan.xlsx (TKDK, 31 Aralık 2022)
Yöntem: Natural Earth Ankara il sınırı + Voronoi ilçe bölgeleri + mahalle noktaları
"""

import json
import math
import numpy as np
import pandas as pd
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, MultiPolygon, Point, shape
from shapely.ops import unary_union

# ── 1. VERİ YÜKLEME ─────────────────────────────────────────────────────────
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
    lambda r: r['mahalle']
    if pd.notna(r['mahalle']) and str(r['mahalle']).strip() not in ['', 'nan']
    else r['koy'], axis=1)
ankara = ankara.reset_index(drop=True)

# ── 2. ANKARA İL SINIRI (Natural Earth) ─────────────────────────────────────
with open('/tmp/ne_admin1.json', encoding='utf-8') as f:
    ne = json.load(f)

ankara_feat = next(
    f for f in ne['features']
    if f['properties'].get('admin') == 'Turkey'
    and 'Ankara' in str(f['properties'].get('name', ''))
)
ankara_poly = shape(ankara_feat['geometry'])
# Shapely koordinatları (lon, lat) → haritada (lat, lon)
bounds = ankara_poly.bounds  # (minx, miny, maxx, maxy) = (minlon, minlat, maxlon, maxlat)
print(f"Ankara sınırı: {bounds}")

# ── 3. İLÇE MERKEZLERİ (doğrulanmış koordinatlar) ──────────────────────────
# Değerler: (lat, lon) - coğrafi merkezler
ILCE_CENTROIDS = {
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

# ── 4. VERI ÖZETI ────────────────────────────────────────────────────────────
summary = ankara.groupby(['ilce', 'sinif']).size().unstack(fill_value=0)
for col in ['KIR', 'ORTA YOĞUN KENT', 'YOĞUN KENT']:
    if col not in summary.columns:
        summary[col] = 0
summary['toplam'] = summary.sum(axis=1)
summary['kir_oran'] = (summary['KIR'] / summary['toplam'] * 100).round(1)
summary['orta_oran'] = (summary['ORTA YOĞUN KENT'] / summary['toplam'] * 100).round(1)
summary['yogun_oran'] = (summary['YOĞUN KENT'] / summary['toplam'] * 100).round(1)
summary = summary.reset_index()
summary['lat'] = summary['ilce'].map(lambda x: ILCE_CENTROIDS.get(x, (39.93, 32.85))[0])
summary['lon'] = summary['ilce'].map(lambda x: ILCE_CENTROIDS.get(x, (39.93, 32.85))[1])

# Baskın sınıflama
def dominant(row):
    vals = {'KIR': row['KIR'], 'ORTA YOĞUN KENT': row['ORTA YOĞUN KENT'], 'YOĞUN KENT': row['YOĞUN KENT']}
    return max(vals, key=vals.get)
summary['dominant'] = summary.apply(dominant, axis=1)

# ── 5. VORONOİ HESAPLAMA ─────────────────────────────────────────────────────
ilce_list = [ilce for ilce in ILCE_CENTROIDS if ilce in summary['ilce'].values]
# (lon, lat) sırasına çevir (shapely/scipy için)
points = np.array([[ILCE_CENTROIDS[ilce][1], ILCE_CENTROIDS[ilce][0]] for ilce in ilce_list])

# Sınır dışına sonsuz noktalar ekle (Voronoi sınırlarının taşmaması için)
bx, by = bounds[0], bounds[1]
ex, ey = bounds[2], bounds[3]
margin = 3.0
far_points = np.array([
    [bx - margin, by - margin], [ex + margin, by - margin],
    [bx - margin, ey + margin], [ex + margin, ey + margin],
    [(bx + ex) / 2, by - margin], [(bx + ex) / 2, ey + margin],
    [bx - margin, (by + ey) / 2], [ex + margin, (by + ey) / 2],
])
all_points = np.vstack([points, far_points])
vor = Voronoi(all_points)

# Her ilçe için Voronoi bölgesi hesapla ve Ankara sınırına kırp
voronoi_regions = {}
for idx, ilce in enumerate(ilce_list):
    region_idx = vor.point_region[idx]
    region = vor.regions[region_idx]
    if -1 in region or not region:
        continue
    poly_coords = [vor.vertices[v] for v in region]
    try:
        poly = Polygon(poly_coords)
        clipped = poly.intersection(ankara_poly)
        if not clipped.is_empty:
            voronoi_regions[ilce] = clipped
    except Exception:
        pass

print(f"Voronoi bölge sayısı: {len(voronoi_regions)}")

# ── 6. GEOJSON OLUŞTUR ──────────────────────────────────────────────────────
COLOR = {
    'KIR': '#16a34a',
    'ORTA YOĞUN KENT': '#d97706',
    'YOĞUN KENT': '#dc2626',
}

def geom_to_coords(geom):
    """Shapely geometry → GeoJSON koordinat listesi (lon, lat)"""
    if geom.geom_type == 'Polygon':
        return [list(geom.exterior.coords)]
    elif geom.geom_type == 'MultiPolygon':
        result = []
        for p in geom.geoms:
            result.extend([list(p.exterior.coords)])
        return result
    return []

geojson_features = []
for ilce in ilce_list:
    if ilce not in voronoi_regions:
        continue
    row = summary[summary['ilce'] == ilce].iloc[0]
    geom = voronoi_regions[ilce]
    dom = row['dominant']
    color = COLOR[dom]

    geojson_features.append({
        'type': 'Feature',
        'properties': {
            'ilce': ilce,
            'dominant': dom,
            'color': color,
            'kir': int(row['KIR']),
            'orta': int(row['ORTA YOĞUN KENT']),
            'yogun': int(row['YOĞUN KENT']),
            'toplam': int(row['toplam']),
            'kir_oran': float(row['kir_oran']),
            'orta_oran': float(row['orta_oran']),
            'yogun_oran': float(row['yogun_oran']),
        },
        'geometry': json.loads(geom.__geo_interface__.__str__().replace("'", '"'))
        if False else geom.__geo_interface__,
    })

geojson_data = {'type': 'FeatureCollection', 'features': geojson_features}

# Ankara il sınırı GeoJSON
ankara_boundary = {
    'type': 'Feature',
    'properties': {},
    'geometry': ankara_poly.__geo_interface__,
}

# İlçe merkezleri (popup için)
centroid_features = []
for _, row in summary.iterrows():
    ilce = row['ilce']
    if ilce not in ILCE_CENTROIDS:
        continue
    lat, lon = ILCE_CENTROIDS[ilce]
    centroid_features.append({
        'type': 'Feature',
        'properties': {
            'ilce': ilce,
            'dominant': row['dominant'],
            'kir': int(row['KIR']),
            'orta': int(row['ORTA YOĞUN KENT']),
            'yogun': int(row['YOĞUN KENT']),
            'toplam': int(row['toplam']),
            'kir_oran': float(row['kir_oran']),
            'orta_oran': float(row['orta_oran']),
            'yogun_oran': float(row['yogun_oran']),
        },
        'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
    })

summary_json = summary.to_dict(orient='records')

print("İlçe bazlı özet (KIR% sıralaması):")
print(summary[['ilce','KIR','ORTA YOĞUN KENT','YOĞUN KENT','toplam','kir_oran','dominant']]
      .sort_values('kir_oran', ascending=False).to_string(index=False))

# ── 7. HTML HARITA ──────────────────────────────────────────────────────────
geojson_js = json.dumps(geojson_data, ensure_ascii=False)
boundary_js = json.dumps(ankara_boundary, ensure_ascii=False)
centroids_js = json.dumps({'type': 'FeatureCollection', 'features': centroid_features}, ensure_ascii=False)
summary_js = json.dumps(summary_json, ensure_ascii=False)

html = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ankara Kent-Kır Sınıflaması Haritası</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f172a; color: #e2e8f0; height: 100vh; display: flex; flex-direction: column; }

#header { background: linear-gradient(135deg, #1e293b 0%, #0f3460 100%); padding: 10px 20px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 10px rgba(0,0,0,0.5); z-index: 1000; flex-shrink: 0; }
#header h1 { font-size: 1rem; font-weight: 700; color: #f1f5f9; }
#header .subtitle { font-size: 0.72rem; color: #94a3b8; margin-top: 2px; }

#controls { background: #1e293b; padding: 7px 20px; display: flex; gap: 8px; align-items: center; border-bottom: 1px solid #334155; flex-shrink: 0; flex-wrap: wrap; }
.filter-btn { padding: 4px 14px; border: 2px solid transparent; border-radius: 20px; cursor: pointer; font-size: 0.78rem; font-weight: 600; transition: all 0.2s; opacity: 0.45; background: transparent; color: #e2e8f0; }
.filter-btn.active { opacity: 1; transform: scale(1.05); }
.filter-btn.kir { border-color: #16a34a; color: #4ade80; }
.filter-btn.kir.active { background: #16a34a; color: white; }
.filter-btn.orta { border-color: #d97706; color: #fbbf24; }
.filter-btn.orta.active { background: #d97706; color: white; }
.filter-btn.yogun { border-color: #dc2626; color: #f87171; }
.filter-btn.yogun.active { background: #dc2626; color: white; }
.filter-btn.all { border-color: #475569; color: #94a3b8; opacity: 1; }
.filter-btn.all.active { background: #475569; color: white; }
.view-toggle { margin-left: auto; display: flex; gap: 5px; }
.view-btn { padding: 4px 12px; border: 1px solid #334155; border-radius: 6px; cursor: pointer; font-size: 0.75rem; background: transparent; color: #94a3b8; transition: all 0.2s; }
.view-btn.active { background: #0f3460; color: #e2e8f0; border-color: #3b82f6; }

#map { flex: 1; }

.info-panel { position: absolute; z-index: 1000; background: rgba(15,23,42,0.95); border: 1px solid #1e3a5f; border-radius: 10px; padding: 14px 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.6); backdrop-filter: blur(4px); }
#legend { bottom: 28px; right: 10px; min-width: 190px; }
#legend h4 { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
.legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 7px; font-size: 0.82rem; }
.legend-swatch { width: 16px; height: 16px; border-radius: 3px; flex-shrink: 0; }
.legend-count { margin-left: auto; color: #475569; font-size: 0.75rem; font-weight: 600; }
.legend-note { font-size: 0.7rem; color: #475569; margin-top: 10px; padding-top: 8px; border-top: 1px solid #1e3a5f; line-height: 1.5; }

#stats { top: 110px; left: 10px; min-width: 175px; }
#stats h4 { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
.stat-row { margin-bottom: 9px; }
.stat-header { display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 3px; }
.stat-label { color: #94a3b8; }
.stat-bar-bg { background: #1e293b; border-radius: 4px; height: 7px; overflow: hidden; }
.stat-bar { height: 100%; border-radius: 4px; }
#stats hr { border: none; border-top: 1px solid #1e3a5f; margin: 10px 0; }
#stats .meta { font-size: 0.7rem; color: #475569; }

.district-tooltip { font-family: 'Segoe UI', Arial; }
</style>
</head>
<body>

<div id="header">
  <div>
    <h1>Ankara İli — Kent-Kır Sınıflaması Haritası</h1>
    <div class="subtitle">TKDK · 31 Aralık 2022 · 1.432 Yerleşim Birimi · 25 İlçe</div>
  </div>
</div>

<div id="controls">
  <button class="filter-btn all active" id="f-all" onclick="setFilter('all')">Tümü</button>
  <button class="filter-btn kir" id="f-kir" onclick="setFilter('kir')">Kır — 956</button>
  <button class="filter-btn orta" id="f-orta" onclick="setFilter('orta')">Orta Yoğun Kent — 106</button>
  <button class="filter-btn yogun" id="f-yogun" onclick="setFilter('yogun')">Yoğun Kent — 370</button>
  <div class="view-toggle">
    <button class="view-btn active" id="v-choropleth" onclick="setView('choropleth')">İlçe Haritası</button>
    <button class="view-btn" id="v-bubbles" onclick="setView('bubbles')">Baloncuk</button>
  </div>
</div>

<div id="map"></div>

<div class="info-panel" id="legend">
  <h4>Sınıflama</h4>
  <div class="legend-item"><div class="legend-swatch" style="background:#16a34a"></div>Kır<span class="legend-count">956</span></div>
  <div class="legend-item"><div class="legend-swatch" style="background:#d97706"></div>Orta Yoğun Kent<span class="legend-count">106</span></div>
  <div class="legend-item"><div class="legend-swatch" style="background:#dc2626"></div>Yoğun Kent<span class="legend-count">370</span></div>
  <div class="legend-note">Her ilçe <b>baskın sınıflamaya</b> göre renklendirilmiştir.<br>Opaklık = Kır oranı.</div>
</div>

<div class="info-panel" id="stats">
  <h4>Ankara Özeti</h4>
  <div class="stat-row">
    <div class="stat-header"><span class="stat-label" style="color:#4ade80">Kır</span><span style="color:#4ade80;font-weight:700">%66.8</span></div>
    <div class="stat-bar-bg"><div class="stat-bar" style="width:66.8%;background:#16a34a"></div></div>
  </div>
  <div class="stat-row">
    <div class="stat-header"><span class="stat-label" style="color:#fbbf24">Orta Yoğun Kent</span><span style="color:#fbbf24;font-weight:700">%7.4</span></div>
    <div class="stat-bar-bg"><div class="stat-bar" style="width:7.4%;background:#d97706"></div></div>
  </div>
  <div class="stat-row">
    <div class="stat-header"><span class="stat-label" style="color:#f87171">Yoğun Kent</span><span style="color:#f87171;font-weight:700">%25.8</span></div>
    <div class="stat-bar-bg"><div class="stat-bar" style="width:25.8%;background:#dc2626"></div></div>
  </div>
  <hr>
  <div class="meta">Hibe uygun: KIR sınıfı alanlar</div>
</div>

<script>
const GEOJSON = """ + geojson_js + """;
const BOUNDARY = """ + boundary_js + """;
const CENTROIDS = """ + centroids_js + """;
const SUMMARY = """ + summary_js + """;

const COLOR = { 'KIR': '#16a34a', 'ORTA YOĞUN KENT': '#d97706', 'YOĞUN KENT': '#dc2626' };

const map = L.map('map', {
  center: [39.85, 32.5],
  zoom: 8,
  zoomControl: true,
  preferCanvas: true
});

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; OpenStreetMap &copy; CARTO',
  subdomains: 'abcd', maxZoom: 19
}).addTo(map);

// ── Ankara il sınırı ──
const boundaryLayer = L.geoJSON(BOUNDARY, {
  style: { color: '#60a5fa', weight: 2.5, fill: false, dashArray: '5 4', opacity: 0.8 }
}).addTo(map);

// ── Voronoi choropleth katmanı ──
let choroplethLayer = null;
let currentFilter = 'all';
let currentView = 'choropleth';

function buildChoropleth(filter) {
  if (choroplethLayer) map.removeLayer(choroplethLayer);

  choroplethLayer = L.geoJSON(GEOJSON, {
    style: function(feature) {
      const p = feature.properties;
      const dom = p.dominant;
      const col = COLOR[dom];
      let visible = true;
      if (filter === 'kir' && dom !== 'KIR') visible = false;
      if (filter === 'orta' && dom !== 'ORTA YOĞUN KENT') visible = false;
      if (filter === 'yogun' && dom !== 'YOĞUN KENT') visible = false;

      // Opaklık kır oranına göre
      const opacity = visible ? Math.max(0.25, p.kir_oran / 100 * 0.75 + 0.2) : 0.06;
      return {
        fillColor: visible ? col : '#334155',
        fillOpacity: opacity,
        color: '#1e293b',
        weight: 1.5,
      };
    },
    onEachFeature: function(feature, layer) {
      const p = feature.properties;
      const col = COLOR[p.dominant];

      layer.bindTooltip(`<b style="color:${col}">${p.ilce}</b>`, {
        className: 'district-tooltip',
        sticky: true
      });

      layer.bindPopup(`
        <div style="font-family:Segoe UI,Arial;min-width:230px;padding:4px">
          <div style="font-size:1.05rem;font-weight:700;margin-bottom:8px;border-bottom:2px solid ${col};padding-bottom:6px">${p.ilce}</div>
          <table style="width:100%;font-size:0.83rem;border-collapse:collapse">
            <tr>
              <td style="padding:4px 6px 4px 0"><span style="display:inline-block;width:10px;height:10px;background:#16a34a;border-radius:2px;margin-right:5px"></span>Kır</td>
              <td style="text-align:right;font-weight:700;color:#4ade80">${p.kir}</td>
              <td style="text-align:right;color:#64748b;padding-left:8px">%${p.kir_oran}</td>
            </tr>
            <tr>
              <td style="padding:4px 6px 4px 0"><span style="display:inline-block;width:10px;height:10px;background:#d97706;border-radius:2px;margin-right:5px"></span>Orta Yoğun</td>
              <td style="text-align:right;font-weight:700;color:#fbbf24">${p.orta}</td>
              <td style="text-align:right;color:#64748b;padding-left:8px">%${p.orta_oran}</td>
            </tr>
            <tr>
              <td style="padding:4px 6px 4px 0"><span style="display:inline-block;width:10px;height:10px;background:#dc2626;border-radius:2px;margin-right:5px"></span>Yoğun Kent</td>
              <td style="text-align:right;font-weight:700;color:#f87171">${p.yogun}</td>
              <td style="text-align:right;color:#64748b;padding-left:8px">%${p.yogun_oran}</td>
            </tr>
            <tr style="border-top:1px solid #334155">
              <td style="padding:5px 0 0;font-weight:600">Toplam</td>
              <td style="text-align:right;font-weight:700;padding-top:5px">${p.toplam}</td>
              <td></td>
            </tr>
          </table>
          ${p.dominant === 'KIR' ? '<div style="margin-top:8px;padding:5px 8px;background:#14532d;border-radius:6px;font-size:0.78rem;color:#4ade80">✓ TKDK Hibe Desteğine Uygun İlçe</div>' : ''}
        </div>
      `);

      layer.on({ mouseover: e => e.target.setStyle({ weight: 3, color: '#93c5fd' }) });
      layer.on({ mouseout: e => choroplethLayer.resetStyle(e.target) });
    }
  });

  if (currentView === 'choropleth') map.addLayer(choroplethLayer);
}

// ── Baloncuk katmanı ──
let bubbleLayer = null;
function buildBubbles(filter) {
  if (bubbleLayer) map.removeLayer(bubbleLayer);
  bubbleLayer = L.layerGroup();

  SUMMARY.forEach(s => {
    const lat = s.lat, lon = s.lon;
    if (!lat || !lon) return;
    const dom = s.dominant;
    const col = COLOR[dom];
    const total = s.toplam;
    const r = Math.sqrt(total) * 2.8;

    let visible = true;
    if (filter === 'kir' && dom !== 'KIR') visible = false;
    if (filter === 'orta' && dom !== 'ORTA YOĞUN KENT') visible = false;
    if (filter === 'yogun' && dom !== 'YOĞUN KENT') visible = false;

    const circle = L.circleMarker([lat, lon], {
      radius: Math.min(r, 38),
      fillColor: visible ? col : '#334155',
      color: 'rgba(255,255,255,0.3)',
      weight: 1.5,
      fillOpacity: visible ? 0.75 : 0.15,
    });

    const kir = s['KIR'] || 0;
    const orta = s['ORTA YOĞUN KENT'] || 0;
    const yogun = s['YOĞUN KENT'] || 0;
    circle.bindPopup(`
      <div style="font-family:Segoe UI,Arial;min-width:220px;padding:4px">
        <div style="font-size:1.05rem;font-weight:700;margin-bottom:8px;border-bottom:2px solid ${col};padding-bottom:6px">${s.ilce}</div>
        <table style="width:100%;font-size:0.83rem">
          <tr><td><span style="color:#4ade80">Kır</span></td><td style="text-align:right;font-weight:700">${kir}</td><td style="text-align:right;color:#64748b">%${s.kir_oran}</td></tr>
          <tr><td><span style="color:#fbbf24">Orta Yoğun</span></td><td style="text-align:right;font-weight:700">${orta}</td><td style="text-align:right;color:#64748b">%${s.orta_oran}</td></tr>
          <tr><td><span style="color:#f87171">Yoğun Kent</span></td><td style="text-align:right;font-weight:700">${yogun}</td><td style="text-align:right;color:#64748b">%${s.yogun_oran}</td></tr>
          <tr style="border-top:1px solid #334155"><td style="font-weight:600;padding-top:4px">Toplam</td><td style="text-align:right;font-weight:700;padding-top:4px" colspan="2">${total}</td></tr>
        </table>
      </div>
    `);

    // İlçe adı etiketi
    const label = L.marker([lat, lon], {
      icon: L.divIcon({
        html: `<div style="font-size:9px;font-weight:700;color:white;text-shadow:0 1px 3px rgba(0,0,0,1);white-space:nowrap;pointer-events:none;text-align:center">${s.ilce}</div>`,
        className: '',
        iconSize: [120, 14],
        iconAnchor: [60, -Math.min(r, 38) - 3]
      })
    });

    bubbleLayer.addLayer(circle);
    bubbleLayer.addLayer(label);
  });

  if (currentView === 'bubbles') map.addLayer(bubbleLayer);
}

// ── Görünüm ve filtre kontrolleri ──
function setFilter(filter) {
  currentFilter = filter;
  ['all','kir','orta','yogun'].forEach(f => {
    document.getElementById('f-' + f).classList.toggle('active', f === filter);
  });
  buildChoropleth(filter);
  buildBubbles(filter);
}

function setView(view) {
  currentView = view;
  document.getElementById('v-choropleth').classList.toggle('active', view === 'choropleth');
  document.getElementById('v-bubbles').classList.toggle('active', view === 'bubbles');
  if (view === 'choropleth') {
    if (bubbleLayer) map.removeLayer(bubbleLayer);
    if (choroplethLayer) map.addLayer(choroplethLayer);
  } else {
    if (choroplethLayer) map.removeLayer(choroplethLayer);
    if (bubbleLayer) map.addLayer(bubbleLayer);
  }
}

// İlk yükleme
buildChoropleth('all');
buildBubbles('all');
</script>
</body>
</html>"""

with open('ankara_harita.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\nDosya oluşturuldu: ankara_harita.html ({len(html)//1024} KB)")
