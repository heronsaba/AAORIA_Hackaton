import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap, GroupedLayerControl
import streamlit.components.v1 as components
import base64
from matplotlib.path import Path
import sys

# ─── PREVENÇÃO DE ERRO DE RECURSIVIDADE DO FOLIUM/JINJA2 ──────────────────────
# Isso é vital para mapas muito complexos não quebrarem o servidor Python
sys.setrecursionlimit(10000)

# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AAORIA Hackathon – Digital Landscape",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS UNIFICADO E BRUTALISTA PARA MOBILE TELA CHEIA ──────────────────────────
# Este bloco mata todas as margens do Streamlit e força o layout perfeito
st.markdown('''<style>
    /* 1. MATA O LAYOUT FLEXBOX PADRÃO DO STREAMLIT */
    html, body, [data-testid="stApp"], [data-testid="stMainWindow"], .main {
        height: 100dvh !important;
        width: 100vw !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important; /* Trava o scroll da página, deixa só o mapa rolar */
    }

    .block-container {
        padding: 0 !important; margin: 0 !important; max-width: 100vw !important;
        height: 100dvh !important;
    }

    /* Esconde elementos nativos */
    header[data-testid="stHeader"], footer, #MainMenu {
        display: none !important;
    }

    /* 2. SEU HEADER AZUL - CORREÇÃO DE TEXTO PARA MOBILE */
    .aaoria-header {
        background: linear-gradient(90deg, #0b1442 0%, #1a3a6e 100%);
        height: 44px; padding: 0 20px; display: flex; align-items: center; gap: 12px;
        position: fixed; top: 0; left: 0; width: 100vw; z-index: 999999;
        box-sizing: border-box;
    }
    .aaoria-header .htitle {
        color:#fff; font-size:15px; font-weight:600; font-family:sans-serif;
        white-space: nowrap; /* Impede o texto de quebrar linha bagunçadamente */
        overflow: hidden; /* Esconde o excesso se não couber */
        text-overflow: ellipsis; /* Adiciona "..." se o texto for cortado */
        flex: 1; /* Permite que este elemento cresça/encolha no container flex */
        min-width: 0; /* Necessário para flex-shrink funcionar com ellipsis */
    }
    .aaoria-header .hbadge {
        background:rgba(255,255,255,0.15); color:#a8d4ff;
        font-size:11px; padding:2px 9px; border-radius:10px; font-family:sans-serif;
        flex-shrink: 0; /* Não deixa o badge encolher, prioriza seu texto */
    }

    /* 3. A MÁGICA DO IFRAME PARA CELULAR TELA CHEIA */
    /* Destrava a div invisível que o Streamlit coloca em volta do Markdown */
    div[data-testid="stMarkdownContainer"] {
        width: 100vw !important;
    }

    /* Trava o iframe com class exatamente no limite da tela, abaixo do header */
    .map-responsive-iframe {
        position: fixed !important;
        top: 44px !important; /* Exatamente a altura do seu header */
        left: 0 !important;
        width: 100vw !important;
        height: calc(100dvh - 44px) !important; /* Respeita a barra de navegação do mobile */
        border: none !important;
        z-index: 999;
        -webkit-overflow-scrolling: touch !important; /* Vital para scroll fluído no iOS Safari */
    }
</style>''', unsafe_allow_html=True)

st.markdown('''
    <div class="aaoria-header">
        <span class="htitle">AAORIA Hackathon – Challenge 3: Atlantic Digital Landscape Mapping</span>
        <span class="hbadge">Brazil Focus · 2026</span>
    </div>
''', unsafe_allow_html=True)

# ─── POLÍGONO ─────────────────────────────────────────────────────────────────
brazil_coastal_poly = [
    (-51.8, 7.0), (20.0, 7.0), (20.0, -35.0), (-53.8, -35.0),
    (-53.8, -34.0), (-51.0, -30.0), (-49.0, -27.5), (-48.0, -25.0),
    (-47.0, -24.0), (-44.0, -23.0), (-41.0, -20.0), (-39.5, -16.0),
    (-39.0, -13.0), (-36.0, -9.0), (-35.5, -6.0), (-39.5, -3.5),
    (-44.5, -2.0), (-48.5, -0.5), (-51.8, 4.5), (-51.8, 7.0)
]
coastal_path = Path(brazil_coastal_poly)

# ─── BUOY SVG ─────────────────────────────────────────────────────────────────
BUOY_SVG = """<svg xmlns='http://www.w3.org/2000/svg' width='32' height='44' viewBox='0 0 32 44'>
  <line x1='16' y1='0' x2='16' y2='10' stroke='#c8e6c9' stroke-width='1.8' stroke-linecap='round'/>
  <circle cx='16' cy='2' r='2.5' fill='#ffeb3b' stroke='#f9a825' stroke-width='1'/>
  <rect x='7' y='10' width='18' height='20' rx='5' ry='5' fill='#2e7d32' stroke='#c8e6c9' stroke-width='1.5'/>
  <rect x='7' y='17' width='18' height='6' fill='#1b5e20'/>
  <ellipse cx='16' cy='30' rx='10' ry='4' fill='#388e3c' stroke='#c8e6c9' stroke-width='1.2'/>
  <path d='M11 30 Q16 44 21 30 Z' fill='#1b5e20' stroke='#c8e6c9' stroke-width='1'/>
  <path d='M10 21 Q12 19 14 21 Q16 23 18 21 Q20 19 22 21' fill='none' stroke='#a5d6a7' stroke-width='1.2' stroke-linecap='round'/>
</svg>"""

# ─── CARGA DE DADOS (cached) ──────────────────────────────────────────────────
@st.cache_data(show_spinner="Carregando dados...")
def load_data():
    # ── Argo ──
    try:
        argo_df = pd.read_csv('dados_argo_brasil_2025_completo.csv')
    except FileNotFoundError:
        st.error("Arquivo 'dados_argo_brasil_2025_completo.csv' não encontrado.")
        st.stop()

    # Última posição por boia
    argo_latest = (argo_df
                   .drop_duplicates(subset=['PLATFORM_NUMBER'], keep='last')
                   .dropna(subset=['LATITUDE', 'LONGITUDE'])
                   .copy())

    # Trail: subsample para no máximo 3000 pontos totais (era tudo)
    argo_full = argo_df.dropna(subset=['LATITUDE', 'LONGITUDE']).copy()
    time_col = next((c for c in ['JULD','DATE','TIME','date','time','timestamp','TIMESTAMP']
                     if c in argo_full.columns), None)
    if time_col:
        argo_full = argo_full.sort_values(time_col)
    if len(argo_full) > 3000:
        argo_full = argo_full.iloc[::max(1, len(argo_full)//3000)].copy()

    # ── ANP ──
    try:
        anp_df = pd.read_csv('gap_anp_offshore.csv').copy()
    except FileNotFoundError:
        st.error("Arquivo 'gap_anp_offshore.csv' não encontrado.")
        st.stop()

    anp_df = anp_df[
        coastal_path.contains_points(anp_df[['LONGITUDE','LATITUDE']].values)
    ].copy()
    anp_df['Name'] = anp_df['description'].apply(
        lambda d: 'ANP Platform' if pd.isna(d) else str(d).split('|')[0].strip()
    )
    # Subsample ANP markers para max 300 (heatmap usa todos, markers são lentos)
    anp_markers = anp_df.sample(min(300, len(anp_df)), random_state=42) if len(anp_df) > 300 else anp_df

    # ── SIMCosta ──
    try:
        sim_df = pd.read_csv('gap_simcosta_atualizado.csv').dropna(subset=['LATITUDE','LONGITUDE']).copy()
        if 'Name' not in sim_df.columns:
            sim_df['Name'] = [f'SIMCosta-{i+1:02d}' for i in range(len(sim_df))]
    except FileNotFoundError:
        sim_df = pd.DataFrame({
            'LATITUDE':  [-23.5,-13.0,-3.7,-8.1,-20.3,-29.5,-1.4,-5.8,-15.9,-25.2],
            'LONGITUDE': [-43.2,-38.5,-38.5,-34.9,-40.1,-48.7,-48.5,-35.2,-39.0,-44.5],
            'Name': [f'SIMCosta-{i+1:02d}' for i in range(10)],
        })

    # ── Projeto Azul ──
    try:
        azul_df = pd.read_csv('gap_projeto_azul_area.csv').dropna(subset=['LATITUDE','LONGITUDE']).copy()
    except FileNotFoundError:
        azul_df = pd.DataFrame()

    return argo_latest, argo_full, anp_df, anp_markers, sim_df, azul_df, time_col

try:
    argo_latest, argo_full, anp_df, anp_markers, sim_df, azul_df, time_col = load_data()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# ─── PROJETO AZUL: nuvem (100 pts, era 300) ───────────────────────────────────
def make_azul_cloud(lat, lon, radius_km, seed=0):
    rng = np.random.default_rng(seed)
    k = 111.0
    s_lat = (radius_km * 0.42) / k
    s_lon = (radius_km * 0.42) / (k * np.cos(np.radians(lat)))
    angle = rng.uniform(0, np.pi)
    stretch = rng.uniform(0.45, 0.75)
    rl = rng.normal(0, s_lat, 100)   # reduzido de 300 → 100
    rn = rng.normal(0, s_lon * stretch, 100)
    fl = rl * np.cos(angle) - rn * np.sin(angle)
    fn = rl * np.sin(angle) + rn * np.cos(angle)
    w = np.clip(np.exp(-(fl**2 / s_lat**2 + fn**2 / (s_lon*stretch)**2) * 1.2), 0.08, 1.0)
    return [[lat + fl[i], lon + fn[i], float(w[i])] for i in range(100)]

# ─── BUILD MAP (cached como HTML string) ──────────────────────────────────────
# NOTA: Os prefixos '_' foram removidos para que o Streamlit valide o cache corretamente
@st.cache_data(show_spinner="Construindo mapa...")
def build_map_html(argo_latest_hash, argo_full_hash, anp_hash, sim_hash, azul_hash):
    m = folium.Map(
        location=[-15.0, -40.0], zoom_start=4, min_zoom=3,
        max_bounds=True, prefer_canvas=True, scrollWheelZoom=True,
    )
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='Esri Satellite', overlay=False, control=False,
    ).add_to(m)

    fg_argo = folium.FeatureGroup(name='Argo Floats, Trails & Routes', show=False)
    fg_sim  = folium.FeatureGroup(name='SIMCosta Coverage & Stations', show=False)
    fg_anp  = folium.FeatureGroup(name='ANP Offshores', show=False)
    fg_azul = folium.FeatureGroup(name='Projeto Azul', show=False)

    # ── 1. ARGO ───────────────────────────────────────────────────────────────
    raw = argo_latest[['LATITUDE','LONGITUDE','PLATFORM_NUMBER']].dropna().copy()
    if len(raw) > 0:
        raw['grid_lat'] = (raw['LATITUDE']  / 1.5).round(0)
        raw['grid_lon'] = (raw['LONGITUDE'] / 1.5).round(0)
        density = raw.groupby(['grid_lat','grid_lon']).transform('count')['LATITUDE']
        max_d = max(float(density.max()), 1.0)
        weights = (density / max_d).clip(lower=0.15).values
        pts_w = [[float(r['LATITUDE']), float(r['LONGITUDE']), float(w)]
                 for (_, r), w in zip(raw.iterrows(), weights)]
        HeatMap(pts_w, min_opacity=0.2, radius=20, blur=15,
                gradient={0.0:'blue', 0.35:'cyan', 0.7:'lime', 1.0:'yellow'}
                ).add_to(fg_argo)

        for _, row in raw.iterrows():
            folium.CircleMarker(
                location=[row['LATITUDE'], row['LONGITUDE']],
                radius=8, color='transparent', fill=True, fill_color='transparent',
                tooltip=(f"<div style='font-size:12px;font-family:sans-serif;'>"
                         f"<b>Argo Float (Platform {row['PLATFORM_NUMBER']})</b>"
                         f"<br>Type: Profiling Float"
                         f"<br>Data: Temperature, Salinity, Pressure</div>")
            ).add_to(fg_argo)

    # Trail heatmap (forçado para float nativo para performance do Jinja2)
    trail_pts = argo_full[['LATITUDE','LONGITUDE']].dropna().astype(float).values.tolist()
    if trail_pts:
        HeatMap(trail_pts, min_opacity=0.4, radius=12, blur=10,
                gradient={0.4:'#003366', 0.7:'#0077cc', 1.0:'#00ccff'}
                ).add_to(fg_argo)

    top20 = (argo_full.groupby('PLATFORM_NUMBER')
             .size().nlargest(20).index.tolist())
    for pid in top20:
        sub = argo_full[argo_full['PLATFORM_NUMBER'] == pid]
        if time_col:
            sub = sub.sort_values(time_col)
        traj = sub[['LATITUDE','LONGITUDE']].dropna().values
        if len(traj) > 50:
            idx = np.linspace(0, len(traj)-1, 50, dtype=int)
            traj = traj[idx]
        traj = traj.tolist()
        if len(traj) < 2:
            continue
        folium.PolyLine(traj, color='#4dd0e1', weight=1.2, opacity=0.55,
                        tooltip=f'Platform {pid}').add_to(fg_argo)
        folium.CircleMarker(location=traj[-1], radius=4,
                            color='#ffffff', fill=True, fill_color='#29b6f6',
                            fill_opacity=0.95, weight=1,
                            tooltip=f'<b>Platform {pid}</b> – last fix'
                            ).add_to(fg_argo)

    fg_argo.add_to(m)

    # ── 2. SIMCOSTA ───────────────────────────────────────────────────────────
    sim_pts = sim_df[['LATITUDE','LONGITUDE']].dropna().astype(float).values.tolist()
    if sim_pts:
        HeatMap(sim_pts, min_opacity=0.5, radius=18, blur=14,
                gradient={0.4:'#1b5e20', 0.7:'#43a047', 1.0:'#b9f6ca'}
                ).add_to(fg_sim)

    for _, row in sim_df.iterrows():
        tooltip_html = (
            f"<div style='font-family:sans-serif;font-size:13px;line-height:1.6;"
            f"background:#0d1f0d;color:#c8e6c9;padding:8px 11px;border-radius:6px;"
            f"border:1px solid #2e7d32;min-width:210px;'>"
            f"<b style='color:#69f0ae;font-size:14px'>{row['Name']}</b><br>"
            f"SIMCosta Monitoring Station<br>"
            f"<span style='display:inline-block;margin-top:5px;background:#4a2c00;"
            f"color:#ffcc80;font-size:11px;font-weight:600;padding:2px 8px;"
            f"border-radius:4px;border:1px solid #ff8f00;'>⚠ On ODIS — data not up to date</span><br>"
            f"<span style='color:#607d8b;font-size:11px'>{row['LATITUDE']:.4f}, {row['LONGITUDE']:.4f}</span>"
            f"</div>"
        )
        folium.Marker(
            location=[row['LATITUDE'], row['LONGITUDE']],
            icon=folium.DivIcon(
                html=f'<div style="width:32px;height:44px;filter:drop-shadow(0 2px 6px rgba(0,0,0,.8))">{BUOY_SVG}</div>',
                icon_size=(32, 44), icon_anchor=(16, 44),
            ),
            tooltip=folium.Tooltip(tooltip_html, sticky=False),
        ).add_to(fg_sim)

    fg_sim.add_to(m)

    # ── 3. ANP OFFSHORE ───────────────────────────────────────────────────────
    pts_list = anp_df[['LATITUDE','LONGITUDE']].dropna().astype(float).values.tolist()
    if pts_list:
        HeatMap(pts_list, min_opacity=0.5, radius=16, blur=12,
                gradient={0.4:'orange', 0.7:'#ff4500', 1.0:'red'}
                ).add_to(fg_anp)

    for _, row in anp_markers.iterrows():
        folium.CircleMarker(
            location=[row['LATITUDE'], row['LONGITUDE']],
            radius=10, color='transparent', fill=True, fill_color='transparent',
            tooltip=(f"<div style='font-size:12px;font-family:sans-serif;'>"
                     f"<b>{row['Name']}</b><br>Type: ANP Offshore Platform"
                     f"<br>Data: MetOcean & Meteorological</div>")
        ).add_to(fg_anp)

    fg_anp.add_to(m)

    # ── 4. PROJETO AZUL ───────────────────────────────────────────────────────
    if not azul_df.empty:
        cloud = []
        for idx, row in azul_df.iterrows():
            rad_km = row.get('radius_km', 60)
            folium.Circle(
                location=[row['LATITUDE'], row['LONGITUDE']],
                radius=rad_km * 1000, color='transparent', fill=True, fill_color='transparent',
                tooltip="<div style='font-size:12px;font-family:sans-serif;'><b>Projeto Azul Area</b><br>Type: Glider / Modeling<br>Data: T, S, DO, Chl-a</div>"
            ).add_to(fg_azul)
            cloud.extend(make_azul_cloud(row['LATITUDE'], row['LONGITUDE'],
                                          radius_km=rad_km, seed=int(idx)))
        if cloud:
            HeatMap(cloud, min_opacity=0.55, radius=16, blur=12,
                    gradient={0.4:'#4a2000', 0.7:'#cc6600', 1.0:'#ffcc00'}
                    ).add_to(fg_azul)
        fg_azul.add_to(m)

    # ── Layer control ──────────────────────────────────────────────────────────
    GroupedLayerControl(
        groups={
            'ODIS Data': [fg_argo],
            'ODIS Data - Needs Attention': [fg_sim],
            'Dark Data': [fg_anp, fg_azul]
        },
        exclusive_groups=False, collapsed=True, position='topleft'
    ).add_to(m)

    # ── Legenda ───────────────────────────────────────────────────────────────
    legend_html = '''
    <div style="position:fixed;bottom:30px;left:16px;
        background:rgba(8,15,40,0.92);border:1px solid rgba(255,255,255,0.13);
        border-radius:10px;padding:14px 16px;z-index:9999;min-width:195px;
        font-family:sans-serif;color:#dce3f0;box-shadow:0 4px 20px rgba(0,0,0,.6);">
        <div style="font-size:10px;font-weight:700;letter-spacing:1px;color:#90b8d4;margin-bottom:7px;text-transform:uppercase;">Heatmap Intensity</div>
        <div style="height:11px;border-radius:3px;overflow:hidden;margin-bottom:3px;background:linear-gradient(to right,blue,cyan,yellow);"></div>
        <div style="display:flex;justify-content:space-between;font-size:9px;color:#7a90a4;margin-bottom:11px;">
            <span>Low</span><span>Medium</span><span>High</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;">
            <div style="font-size:9px;font-weight:700;color:#556680;text-transform:uppercase;letter-spacing:.8px;border-bottom:1px solid rgba(255,255,255,.07);padding-bottom:3px;">Layers</div>
            <div style="display:flex;align-items:center;gap:8px;font-size:12px;"><div style="width:30px;height:5px;border-radius:2px;flex-shrink:0;background:linear-gradient(to right,blue,cyan,yellow);"></div>Argo Floats</div>
            <div style="display:flex;align-items:center;gap:8px;font-size:12px;"><div style="width:30px;height:5px;border-radius:2px;flex-shrink:0;background:linear-gradient(to right,#003366,#0077cc,#00ccff);"></div>Argo Trails</div>
            <div style="display:flex;align-items:center;gap:8px;font-size:12px;"><div style="width:30px;height:5px;border-radius:2px;flex-shrink:0;background:linear-gradient(to right,#1b5e20,#43a047,#b9f6ca);"></div>SIMCosta</div>
            <div style="display:flex;align-items:center;gap:8px;font-size:12px;"><div style="width:30px;height:5px;border-radius:2px;flex-shrink:0;background:linear-gradient(to right,orange,#ff4500,red);"></div>ANP Offshore</div>
            <div style="display:flex;align-items:center;gap:8px;font-size:12px;"><div style="width:30px;height:5px;border-radius:2px;flex-shrink:0;background:linear-gradient(to right,#4a2000,#cc6600,#ffcc00);"></div>Projeto Azul</div>
        </div>
    </div>'''
    m.get_root().html.add_child(folium.Element(legend_html))

    # NOTA: Retornamos o HTML bruto sem o iframe que o folium costuma injetar
    return m.get_root().render()

# ─── HASHES para invalidar cache ──────────────────────────────────────────────
def df_hash(df):
    if df.empty:
        return "empty"
    return f"{len(df)}_{df.iloc[0,0]}_{df.iloc[-1,0]}"

map_html = build_map_html(
    df_hash(argo_latest), df_hash(argo_full),
    df_hash(anp_df), df_hash(sim_df), df_hash(azul_df)
)

# ─── RENDER NATIVO: Responsividade Absoluta no Mobile ───────────────────────
import streamlit.components.v1 as components
import base64

# O encode para base64 continua aqui, é vital para evitar round-trips Python↔JS
b64 = base64.b64encode(map_html.encode("utf-8")).decode("utf-8")

# Usamos components.html e aplicamos a class que definimos no CSS acima
# O 'height=1000' é apenas um placeholder, o CSS no topo vai esmagá-lo
components.html(map_html, height=1000, scrolling=False)
