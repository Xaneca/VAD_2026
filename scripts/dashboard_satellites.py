import dash
from dash import dcc, html, Input, Output, State, dash_table, callback
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from urllib.request import urlopen

from sgp4.api import Satrec, jday, SatrecArray

# ============================================================
# CARREGAR DADOS
# ============================================================
path = '.'
tle = pd.read_csv(f'{path}/DATASETS_SATTELITES/merged_dataset_tle.csv')

dash.register_page(__name__, name='Satellites', path='/')

# ============================================================
# PREPARAR DADOS 3D (Versão SGP4 ECI para ECEF)
# ============================================================
def prepare_3d_data(df):
    print("Valor inicial de objetos:", len(df))

    df = df.dropna(subset=['TLE_LINE1', 'TLE_LINE2']).copy()
    print(f"Após remover os que não têm TLE: {len(df)}")

    tempo_atual = datetime.utcnow()
    df['SNAPSHOT_TIME'] = tempo_atual
    jd, fr = jday(tempo_atual.year, tempo_atual.month, tempo_atual.day,
                  tempo_atual.hour, tempo_atual.minute, tempo_atual.second)
    x_list, y_list, z_list = [], [], []
    vel_list, alt_list = [], []
    for index, row in df.iterrows():
        try:
            sat = Satrec.twoline2rv(row['TLE_LINE1'], row['TLE_LINE2'])
            e, r, v = sat.sgp4(jd, fr)
            if e == 0:
                x_list.append(r[0]); y_list.append(r[1]); z_list.append(r[2])
                vel_list.append(np.sqrt(v[0]**2 + v[1]**2 + v[2]**2))
                alt_list.append(np.sqrt(r[0]**2 + r[1]**2 + r[2]**2) - 6371.0)
            else:
                x_list.append(np.nan); y_list.append(np.nan); z_list.append(np.nan)
                vel_list.append(np.nan); alt_list.append(np.nan)
        except:
            x_list.append(np.nan); y_list.append(np.nan); z_list.append(np.nan)
            vel_list.append(np.nan); alt_list.append(np.nan)
    df['X_ECI'] = x_list; df['Y_ECI'] = y_list; df['Z_ECI'] = z_list
    df['VELOCITY'] = vel_list; df['ALTITUDE'] = alt_list
    df = df.dropna(subset=['X_ECI', 'Y_ECI', 'Z_ECI'])
    print(f"Após remover os que deram erro SGP4 (ex: já caíram): {len(df)}")

    def calculate_gmst(date_utc):
        jd_now = pd.Timestamp(date_utc).to_julian_date()
        d = jd_now - 2451545.0
        gmst = 280.46061837 + 360.98564736629 * d
        return np.radians(gmst % 360)

    theta = calculate_gmst(tempo_atual)
    df['X'] = df['X_ECI'] * np.cos(theta) + df['Y_ECI'] * np.sin(theta)
    df['Y'] = -df['X_ECI'] * np.sin(theta) + df['Y_ECI'] * np.cos(theta)
    df['Z'] = df['Z_ECI']

    if 'PERIOD' in df.columns:
        df['ORBIT_TYPE'] = pd.cut(df['PERIOD'], bins=[0, 128, 600, 1500, 99999],
                                   labels=['LEO', 'MEO', 'GEO', 'HEO']).astype(str)
    type_mapping = {
        'SATELLITE': 'Satellite', 'ROCKET BODY': 'Rocket Body',
        'DEBRIS': 'Debris', 'SPACE STATION': 'Space Station',
        'COMPONENT': 'Component', 'IN ANALYSIS': 'In Analysis', 'UNKNOWN': 'Unknown'
    }
    if 'OBJECT_TYPE' in df.columns:
        df['OBJECT_TYPE'] = df['OBJECT_TYPE'].str.upper().map(type_mapping).fillna('Satellite')
    else:
        df['OBJECT_TYPE'] = 'Satellite'
    name_upper = df['NAME'].str.upper()
    mask_refine = df['OBJECT_TYPE'].isin(['Satellite', 'Unknown'])
    df.loc[mask_refine & name_upper.str.contains('ISS|STATION|TIANGONG'), 'OBJECT_TYPE'] = 'Space Station'
    df.loc[mask_refine & name_upper.str.contains(r'R/B|ROCKET|STAGE'), 'OBJECT_TYPE'] = 'Rocket Body'
    df.loc[mask_refine & name_upper.str.contains('DEB|DEBRIS'), 'OBJECT_TYPE'] = 'Debris'
    name_upper = df['NAME'].str.upper()
    constellation_map = {
        'STARLINK': 'Starlink', 'ONEWEB': 'OneWeb',  'IRIDIUM': 'Iridium',
        'GPS': 'GPS', 'GLONASS': 'GLONASS', 'GALILEO': 'Galileo',
        'BEIDOU': 'BeiDou', 'COSMOS': 'COSMOS', 'FENGYUN': 'FengYun',
        'GOES': 'GOES', 'NOAA': 'NOAA', 'ISS': 'ISS', 'HUBBLE': 'Hubble',
    }
    df['CONSTELLATION'] = 'Other'
    for key, val in constellation_map.items():
        mask = name_upper.str.contains(key, na=False) & (df['CONSTELLATION'] == 'Other')
        df.loc[mask, 'CONSTELLATION'] = val
    df = df.reset_index(drop=True)
    df['IDX'] = df.index
    return df

df_3d = prepare_3d_data(tle)
print(f"✅ Objectos 3D carregados: {len(df_3d):,}")

# ============================================================
# OTIMIZAÇÃO LIVE UPDATE (Vetorização SGP4)
# ============================================================
print("⏳ A pré-processar satélites para live updates...")
lista_satrecs = []
for index, row in df_3d.iterrows():
    try:
        sat = Satrec.twoline2rv(row['TLE_LINE1'], row['TLE_LINE2'])
        lista_satrecs.append(sat)
    except:
        pass
SAT_ARRAY = SatrecArray(lista_satrecs)
print("✅ SatrecArray criado com sucesso para o Live Update.")

# ============================================================
# CACHE E CÁLCULO DE CONJUNÇÕES
# ============================================================
_CONJ_CACHE = None

def _build_conjunction_cache(df):
    mu    = 398600.4418
    valid = (df['PERIOD'] > 0) & (df['ECCENTRICITY'] < 1) & (df['ECCENTRICITY'] >= 0)
    df    = df[valid].copy().reset_index(drop=True)
    a     = ((df['PERIOD'].values * 60 * np.sqrt(mu)) / (2 * np.pi))**(2/3)
    e     = df['ECCENTRICITY'].values
    df['_APOGEE_KM']  = a * (1 + e) - 6371.0
    df['_PERIGEE_KM'] = a * (1 - e) - 6371.0
    df['_A_KM']       = a
    return df

def _get_cache(df):
    global _CONJ_CACHE
    if _CONJ_CACHE is None:
        print("⏳ A construir cache de conjunções (uma vez)...")
        _CONJ_CACHE = _build_conjunction_cache(df)
        print(f"✅ Cache pronta: {len(_CONJ_CACHE):,} objectos.")
    return _CONJ_CACHE

def _propagate_batch(sats_df, n_steps, step_min):
    mu          = 398600.4418
    M0          = np.radians(sats_df['MEAN_ANOMALY'].values)
    mean_motion = sats_df['MEAN_MOTION'].values * 2 * np.pi / 1440.0
    e           = sats_df['ECCENTRICITY'].values
    inc         = np.radians(sats_df['INCLINATION'].values)
    raan        = np.radians(sats_df['RA_OF_ASC_NODE'].values)
    argp        = np.radians(sats_df['ARG_OF_PERICENTER'].values)
    a           = sats_df['_A_KM'].values
    dt  = np.arange(n_steps, dtype=np.float64) * step_min
    M_t = M0[:, None] + mean_motion[:, None] * dt[None, :]
    E = M_t.copy()
    for _ in range(6):
        E -= (E - e[:, None] * np.sin(E) - M_t) / (1.0 - e[:, None] * np.cos(E))
    nu = 2.0 * np.arctan2(
        np.sqrt(1.0 + e[:, None]) * np.sin(E / 2.0),
        np.sqrt(1.0 - e[:, None]) * np.cos(E / 2.0),
    )
    r  = a[:, None] * (1.0 - e[:, None]**2) / (1.0 + e[:, None] * np.cos(nu))
    xo = r * np.cos(nu); yo = r * np.sin(nu)
    cr, sr = np.cos(raan)[:, None], np.sin(raan)[:, None]
    ca, sa = np.cos(argp)[:, None], np.sin(argp)[:, None]
    ci, si = np.cos(inc)[:, None],  np.sin(inc)[:, None]
    X = (cr*ca - sr*sa*ci)*xo + (-cr*sa - sr*ca*ci)*yo
    Y = (sr*ca + cr*sa*ci)*xo + (-sr*sa + cr*ca*ci)*yo
    Z = (sa*si)*xo             + (ca*si)*yo
    return X, Y, Z

def run_live_conjunction_analysis(target_norad_id, tle_dataframe, days=7, step_minutes=15.0, top_n=10, buffer_km=75.0):
    df_c            = _get_cache(tle_dataframe)
    target_norad_id = int(target_norad_id)
    tgt_mask = df_c['NORAD_CAT_ID'] == target_norad_id
    if not tgt_mask.any():
        return pd.DataFrame(columns=['NAME','NORAD_ID','MIN_DIST_KM','TIME_UTC'])
    tgt_row     = df_c[tgt_mask].iloc[0]
    tgt_apogee  = float(tgt_row['_APOGEE_KM'])
    tgt_perigee = float(tgt_row['_PERIGEE_KM'])
    cand_mask = (
        (~tgt_mask) &
        (df_c['_PERIGEE_KM'] <= tgt_apogee  + buffer_km) &
        (df_c['_APOGEE_KM']  >= tgt_perigee - buffer_km) &
        (df_c['PERIOD'] > 0) &
        (df_c['ECCENTRICITY'] < 1)
    )
    candidates = df_c[cand_mask].copy()
    if candidates.empty:
        return pd.DataFrame(columns=['NAME','NORAD_ID','MIN_DIST_KM','TIME_UTC'])
    n_steps = max(1, int(days * 24 * 60 / step_minutes))
    Xt, Yt, Zt = _propagate_batch(df_c[tgt_mask], n_steps, step_minutes)
    Xc, Yc, Zc = _propagate_batch(candidates,     n_steps, step_minutes)
    dist         = np.sqrt((Xc - Xt)**2 + (Yc - Yt)**2 + (Zc - Zt)**2)
    min_dist_idx = dist.argmin(axis=1)
    min_dist_val = dist[np.arange(len(candidates)), min_dist_idx]
    top_idx = np.argsort(min_dist_val)[:top_n]
    now_utc = datetime.utcnow()
    records = []
    for i in top_idx:
        row = candidates.iloc[i]
        t_offset = timedelta(minutes=float(min_dist_idx[i]) * step_minutes)
        records.append({
            'NAME':        str(row['NAME']),
            'NORAD_ID':    int(row['NORAD_CAT_ID']),
            'MIN_DIST_KM': round(float(min_dist_val[i]), 2),
            'TIME_UTC':    (now_utc + t_offset).strftime('%Y-%m-%d %H:%M'),
        })
    return pd.DataFrame(records)

# ============================================================
# ÓRBITA COMPLETA (SGP4)
# ============================================================
def compute_orbit_line(row, n_points=300):
    sat = Satrec.twoline2rv(row['TLE_LINE1'], row['TLE_LINE2'])
    period_minutes = float(row['PERIOD'])
    tempo_atual = pd.to_datetime(row['SNAPSHOT_TIME'])
    X, Y, Z = [], [], []
    for i in range(n_points):
        delta_minutes = (period_minutes / n_points) * i
        t_point = tempo_atual + timedelta(minutes=delta_minutes)
        jd, fr = jday(t_point.year, t_point.month, t_point.day,
                      t_point.hour, t_point.minute, t_point.second + t_point.microsecond / 1e6)
        e, r, v = sat.sgp4(jd, fr)
        if e == 0:
            X.append(r[0]); Y.append(r[1]); Z.append(r[2])
    if len(X) > 0:
        X.append(X[0]); Y.append(Y[0]); Z.append(Z[0])
    return X, Y, Z

# ============================================================
# HELPER: posição de um satélite num instante específico (ECEF)
# ============================================================
def get_position_at_time(tle_row, target_dt):
    """Retorna (x, y, z) em ECEF para um dado datetime UTC."""
    try:
        sat = Satrec.twoline2rv(tle_row['TLE_LINE1'], tle_row['TLE_LINE2'])
        jd, fr = jday(target_dt.year, target_dt.month, target_dt.day,
                      target_dt.hour, target_dt.minute,
                      target_dt.second + target_dt.microsecond / 1e6)
        e, r, v = sat.sgp4(jd, fr)
        if e != 0:
            return None
        rx, ry, rz = r
        jd_now = pd.Timestamp(target_dt).to_julian_date()
        d = jd_now - 2451545.0
        theta = np.radians((280.46061837 + 360.98564736629 * d) % 360)
        x_ecef =  rx * np.cos(theta) + ry * np.sin(theta)
        y_ecef = -rx * np.sin(theta) + ry * np.cos(theta)
        z_ecef =  rz
        return x_ecef, y_ecef, z_ecef
    except:
        return None

# ============================================================
# LIVE UPDATE DE POSIÇÕES
# ============================================================
def update_live_positions(df):
    tempo_atual = datetime.utcnow()
    jd, fr = jday(tempo_atual.year, tempo_atual.month, tempo_atual.day,
                  tempo_atual.hour, tempo_atual.minute, tempo_atual.second)
    jd_arr = np.array([jd]); fr_arr = np.array([fr])
    e, r, v = SAT_ARRAY.sgp4(jd_arr, fr_arr)
    df['X_ECI'] = r[:, 0, 0]; df['Y_ECI'] = r[:, 0, 1]; df['Z_ECI'] = r[:, 0, 2]
    erro_mask = (e[:, 0] != 0)
    df.loc[erro_mask, ['X_ECI', 'Y_ECI', 'Z_ECI']] = np.nan
    jd_now = pd.Timestamp(tempo_atual).to_julian_date()
    d = jd_now - 2451545.0
    gmst = 280.46061837 + 360.98564736629 * d
    theta = np.radians(gmst % 360)
    df['X'] = df['X_ECI'] * np.cos(theta) + df['Y_ECI'] * np.sin(theta)
    df['Y'] = -df['X_ECI'] * np.sin(theta) + df['Y_ECI'] * np.cos(theta)
    df['Z'] = df['Z_ECI']
    return df

# ============================================================
# GLOBO 3D E ESTILOS
# ============================================================
def build_earth_surface():
    phi   = np.linspace(0, 2*np.pi, 180)
    theta = np.linspace(0, np.pi, 90)
    x_e = 6371 * np.outer(np.cos(phi), np.sin(theta))
    y_e = 6371 * np.outer(np.sin(phi), np.sin(theta))
    z_e = 6371 * np.outer(np.ones(np.size(phi)), np.cos(theta))
    return x_e, y_e, z_e

def build_coastlines():
    try:
        url = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json"
        with urlopen(url, timeout=5) as resp:
            geo = json.loads(resp.read().decode())
        xs, ys, zs = [], [], []
        r = 6372.0
        for feat in geo['features']:
            geom  = feat['geometry']
            parts = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
            for part in parts:
                for poly in part:
                    lons  = [p[0] for p in poly]
                    lats  = [p[1] for p in poly]
                    lat_r = np.radians(lats); lon_r = np.radians(lons)
                    xs.extend((r * np.cos(lat_r) * np.cos(lon_r)).tolist() + [None])
                    ys.extend((r * np.cos(lat_r) * np.sin(lon_r)).tolist() + [None])
                    zs.extend((r * np.sin(lat_r)).tolist() + [None])
        return xs, ys, zs
    except Exception as e:
        print(f"[AVISO] Coastlines não carregadas: {e}")
        return None, None, None

_EARTH_SURFACE = build_earth_surface()
_COASTLINES    = build_coastlines()

COLOR_MAP = {
    'Satellite':     '#ADD8E6',
    'Debris':        '#8B0000',
    'Rocket Body':   '#F08080',
    'Space Station': '#1E90FF',
    'Component':     '#FFD700',
    'In Analysis':   '#FFA500',
    'Unknown':       '#A9A9A9'
}

def _eci_orbit_to_ecef(ox, oy, oz, ref_time):
    """Converte array de pontos ECI para ECEF usando o GMST do ref_time."""
    ox = np.array(ox); oy = np.array(oy); oz = np.array(oz)
    jd_now = pd.Timestamp(ref_time).to_julian_date()
    d = jd_now - 2451545.0
    theta = np.radians((280.46061837 + 360.98564736629 * d) % 360)
    ox_ecef =  ox * np.cos(theta) + oy * np.sin(theta)
    oy_ecef = -ox * np.sin(theta) + oy * np.cos(theta)
    return ox_ecef, oy_ecef, oz

def build_globe_figure(df_filtered, orbit_row=None, current_time_str="", time_offset_hours=0):
    """
    Constrói o globo 3D principal.
    time_offset_hours: deslocamento em horas (do slider de tempo) relativo a agora.
    """
    x_e, y_e, z_e             = _EARTH_SURFACE
    coast_x, coast_y, coast_z = _COASTLINES
    max_range = 50000

    # Se há offset de tempo, calculamos o instante alvo
    if time_offset_hours != 0 and orbit_row is not None:
        target_time = datetime.utcnow() + timedelta(hours=time_offset_hours)
    else:
        target_time = None

    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=x_e, y=y_e, z=z_e,
        colorscale=[[0, '#040b1a'], [1, '#0a1628']],
        showscale=False, opacity=1, hoverinfo='skip',
        lighting=dict(ambient=0.6, diffuse=0.8), name='Terra', showlegend=False
    ))
    if coast_x is not None:
        fig.add_trace(go.Scatter3d(
            x=coast_x, y=coast_y, z=coast_z,
            mode='lines', line=dict(color='white', width=5),
            hoverinfo='skip', showlegend=False
        ))

    for obj_type, color in COLOR_MAP.items():
        mask = df_filtered['OBJECT_TYPE'] == obj_type
        if mask.sum() == 0:
            continue
        sub = df_filtered[mask].dropna(subset=['X', 'Y', 'Z'])
        fig.add_trace(go.Scatter3d(
            x=sub['X'], y=sub['Y'], z=sub['Z'],
            mode='markers', name=obj_type,
            marker=dict(size=2, color=color, opacity=0.75,
                        line=dict(width=4, color='rgba(255,255,255,0)')),
            customdata=sub[['IDX','NAME','ALTITUDE','ORBIT_TYPE',
                             'CONSTELLATION','INCLINATION','PERIOD','NORAD_CAT_ID']].values,
            hovertemplate=(
                '<b>%{customdata[1]}</b><br>'
                'Alt: %{customdata[2]:.0f} km | Orbit: %{customdata[3]}<br>'
                'Constelação: %{customdata[4]}<br>'
                'Inclinação: %{customdata[5]:.1f}° | Período: %{customdata[6]:.1f} min'
                '<extra></extra>'
            )
        ))

    if orbit_row is not None:
        try:
            ox, oy, oz = compute_orbit_line(orbit_row)
            ox_ecef, oy_ecef, oz_ecef = _eci_orbit_to_ecef(ox, oy, oz, datetime.utcnow())
            fig.add_trace(go.Scatter3d(
                x=ox_ecef, y=oy_ecef, z=oz_ecef, mode='lines',
                line=dict(color='white', width=2),
                name=f"Órbita: {orbit_row['NAME']}",
                hoverinfo='skip', showlegend=True, uirevision='constant'
            ))

            # Posição do satélite: com ou sem offset de tempo
            if target_time is not None:
                pos = get_position_at_time(orbit_row, target_time)
                if pos:
                    sx, sy, sz = pos
                else:
                    sx, sy, sz = float(orbit_row['X']), float(orbit_row['Y']), float(orbit_row['Z'])
            else:
                sx, sy, sz = float(orbit_row['X']), float(orbit_row['Y']), float(orbit_row['Z'])

            fig.add_trace(go.Scatter3d(
                x=[sx], y=[sy], z=[sz], mode='markers',
                marker=dict(size=6, color='white', symbol='diamond',
                            line=dict(color='yellow', width=2)),
                name='Seleccionado',
                hovertemplate=f"<b>{orbit_row['NAME']}</b><extra></extra>",
                showlegend=True, uirevision='constant'
            ))
        except Exception as ex:
            print(f"Erro ao calcular órbita: {ex}")

    # Tempo a mostrar no relógio
    if time_offset_hours != 0:
        display_time = (datetime.utcnow() + timedelta(hours=time_offset_hours)).strftime('%Y-%m-%d %H:%M:%S')
        clock_color  = '#ffd700'   # amarelo quando é previsão
    else:
        display_time = current_time_str
        clock_color  = 'white'

    invis = dict(
        showbackground=False, showgrid=False, showline=False,
        showticklabels=False, zeroline=False, title='',
        showspikes=False, range=[-max_range, max_range]
    )
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        # scene=dict(xaxis=invis, yaxis=invis, zaxis=invis, bgcolor='rgba(0,0,0,0)',
        #            aspectmode='manual', aspectratio=dict(x=1, y=1, z=1)),
        scene=dict(xaxis=invis, yaxis=invis, zaxis=invis, bgcolor='rgba(0,0,0,0)',
                   aspectmode='manual', aspectratio=dict(x=1, y=1, z=1),
                   uirevision='manter_camara_globo'), # para o globo nao se mexer quando atualiza posiçao
        legend=dict(x=0.01, y=0.99, font=dict(color='white', size=10),
                    bgcolor='rgba(0,0,0,0.5)', bordercolor='#2d3748', itemsizing='constant'),
        margin=dict(l=0, r=0, t=0, b=0), uirevision='constant', hoverdistance=50,
        annotations=[
            dict(
                text=f"🕒 {display_time} UTC",
                x=0.02, y=0.15, xref="paper", yref="paper",
                font=dict(color=clock_color, size=13, family="monospace"),
                showarrow=False,
                bgcolor="rgba(0,0,0,0.7)", bordercolor="#4a6fa5", borderpad=6
            )
        ] if display_time else []
    )
    return fig


def build_conjunction_orbit_figure(primary_row, secondary_row, conjunction_time_str):
    """
    Constrói um globo 3D mostrando as duas órbitas (primária e secundária)
    e as posições de ambos os satélites no instante da conjunção.
    """
    x_e, y_e, z_e             = _EARTH_SURFACE
    coast_x, coast_y, coast_z = _COASTLINES

    # Parsear o tempo da conjunção
    try:
        conj_dt = datetime.strptime(conjunction_time_str, '%Y-%m-%d %H:%M')
    except:
        conj_dt = datetime.utcnow()

    max_range = 50000
    fig = go.Figure()

    fig.add_trace(go.Surface(
        x=x_e, y=y_e, z=z_e,
        colorscale=[[0, '#040b1a'], [1, '#0a1628']],
        showscale=False, opacity=1, hoverinfo='skip',
        lighting=dict(ambient=0.6, diffuse=0.8), name='Terra', showlegend=False
    ))
    if coast_x is not None:
        fig.add_trace(go.Scatter3d(
            x=coast_x, y=coast_y, z=coast_z,
            mode='lines', line=dict(color='white', width=5),
            hoverinfo='skip', showlegend=False
        ))

    # Órbita primária (branca)
    try:
        ox, oy, oz = compute_orbit_line(primary_row)
        ox_e, oy_e, oz_e = _eci_orbit_to_ecef(ox, oy, oz, conj_dt)
        fig.add_trace(go.Scatter3d(
            x=ox_e, y=oy_e, z=oz_e, mode='lines',
            line=dict(color='#00d4ff', width=2),
            name=f"Órbita: {primary_row['NAME']}",
            hoverinfo='skip', showlegend=True
        ))
    except Exception as ex:
        print(f"Erro órbita primária: {ex}")

    # Órbita secundária (laranja)
    try:
        ox2, oy2, oz2 = compute_orbit_line(secondary_row)
        ox2_e, oy2_e, oz2_e = _eci_orbit_to_ecef(ox2, oy2, oz2, conj_dt)
        fig.add_trace(go.Scatter3d(
            x=ox2_e, y=oy2_e, z=oz2_e, mode='lines',
            line=dict(color='#ff6b35', width=2),
            name=f"Órbita: {secondary_row['NAME']}",
            hoverinfo='skip', showlegend=True
        ))
    except Exception as ex:
        print(f"Erro órbita secundária: {ex}")

    # Posição primária no momento da conjunção (azul)
    pos1 = get_position_at_time(primary_row, conj_dt)
    if pos1:
        fig.add_trace(go.Scatter3d(
            x=[pos1[0]], y=[pos1[1]], z=[pos1[2]], mode='markers',
            marker=dict(size=7, color='#00d4ff', symbol='diamond',
                        line=dict(color='white', width=2)),
            name=primary_row['NAME'],
            hovertemplate=f"<b>{primary_row['NAME']}</b><br>{conjunction_time_str} UTC<extra></extra>",
            showlegend=True
        ))

    # Posição secundária no momento da conjunção (laranja)
    pos2 = get_position_at_time(secondary_row, conj_dt)
    if pos2:
        fig.add_trace(go.Scatter3d(
            x=[pos2[0]], y=[pos2[1]], z=[pos2[2]], mode='markers',
            marker=dict(size=7, color='#ff6b35', symbol='diamond',
                        line=dict(color='white', width=2)),
            name=secondary_row['NAME'],
            hovertemplate=f"<b>{secondary_row['NAME']}</b><br>{conjunction_time_str} UTC<extra></extra>",
            showlegend=True
        ))

    invis = dict(
        showbackground=False, showgrid=False, showline=False,
        showticklabels=False, zeroline=False, title='',
        showspikes=False, range=[-max_range, max_range]
    )
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        # scene=dict(xaxis=invis, yaxis=invis, zaxis=invis, bgcolor='rgba(0,0,0,0)',
        #            aspectmode='manual', aspectratio=dict(x=1, y=1, z=1)),
        scene=dict(xaxis=invis, yaxis=invis, zaxis=invis, bgcolor='rgba(0,0,0,0)',
                   aspectmode='manual', aspectratio=dict(x=1, y=1, z=1),
                   uirevision='manter_camara_conjuncao'),   # para o globo nao se mexer quando atualiza posiçao
        legend=dict(x=0.01, y=0.99, font=dict(color='white', size=10),
                    bgcolor='rgba(0,0,0,0.5)', bordercolor='#2d3748', itemsizing='constant'),
        margin=dict(l=0, r=0, t=0, b=0), uirevision='conj-view', hoverdistance=50,
        annotations=[
            dict(
                text=f"🕒 {conjunction_time_str} UTC",
                x=0.02, y=0.02, xref="paper", yref="paper",
                font=dict(color='#ffd700', size=13, family="monospace"),
                showarrow=False,
                bgcolor="rgba(0,0,0,0.7)", bordercolor="#ff6b35", borderpad=6
            )
        ]
    )
    return fig


# ============================================================
# GRÁFICOS SECUNDÁRIOS E VARIÁVEIS DE DESIGN
# ============================================================
fig_type_object = go.Figure(data=[go.Pie(
    values=df_3d['OBJECT_TYPE'].value_counts().values,
    labels=df_3d['OBJECT_TYPE'].value_counts().index.tolist(),
    hole=0.65, marker_colors=['#00d4ff','#ff6b35','#ffd700','#00ff88'],
    textinfo='percent+label', textposition='inside'
)])
fig_type_object.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    showlegend=False, margin=dict(l=10,r=10,t=20,b=20), font=dict(color='white', size=10),
    annotations=[dict(text='Type<br>object', x=0.5, y=0.5, font_size=12, font_color='white', showarrow=False)]
)

top_constellations = df_3d[df_3d['CONSTELLATION'] != 'Other']['CONSTELLATION'].value_counts().head(6)
fig_bar = go.Figure(data=[go.Bar(x=top_constellations.index.tolist(), y=top_constellations.values, marker_color='#4a6fa5')])
fig_bar.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=20,r=20,t=10,b=20),
    xaxis=dict(showgrid=False, color='white', tickfont=dict(size=10)),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white', tickfont=dict(size=10))
)

# 1. Calcular a altitude de todos
altitudes = np.sqrt(df_3d['X']**2 + df_3d['Y']**2 + df_3d['Z']**2) - 6371

# Função auxiliar para amostrar no máximo 5000 pontos (evita lag no browser)
def get_sample(mask):
    data = altitudes[mask]
    return data.sample(min(5000, len(data))) if len(data) > 0 else data

# Máscaras de filtro para cada tipo de órbita (limitando a 40.000km)
mask_all = (altitudes < 40000)
mask_leo = (altitudes <= 2000)
mask_meo = (altitudes > 2000) & (altitudes <= 35786)
mask_geo = (altitudes > 35786) & (altitudes <= 40000)

# Estilo base do teu violino
v_style = dict(box_visible=True, line_color='#4a6fa5', fillcolor='#2d4a6f', opacity=0.6)

fig_violin = go.Figure()

# 2. Adicionar 4 "camadas" ao gráfico. Apenas a primeira ('ALL') começa ligada (visible=True)
fig_violin.add_trace(go.Violin(y=get_sample(mask_all), visible=True, name='ALL', **v_style))
fig_violin.add_trace(go.Violin(y=get_sample(mask_leo), visible=False, name='LEO', **v_style))
fig_violin.add_trace(go.Violin(y=get_sample(mask_meo), visible=False, name='MEO', **v_style))
fig_violin.add_trace(go.Violin(y=get_sample(mask_geo), visible=False, name='GEO', **v_style))

# 3. Configurar Layout com os Botões Nativos
fig_violin.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)', 
    margin=dict(l=35, r=10, t=35, b=10), # 't' aumentado para dar espaço aos botões
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white', title=dict(text='Altitude (km)', font=dict(size=10))),
    xaxis=dict(showticklabels=False),
    showlegend=False,
    
    # OS 4 BOTÕES INTERATIVOS
    updatemenus=[
        dict(
            type="buttons",
            direction="right",     
            x=0.5, y=1.15,         
            xanchor='center',
            yanchor='bottom',
            showactive=True,
            buttons=list([
                dict(
                    label="ALL", 
                    method="update", 
                    args=[{"visible": [True,  False, False, False]}, 
                          {"yaxis.autorange": True}] # O Plotly calcula sozinho
                ),
                dict(
                    label="LEO", 
                    method="update", 
                    args=[{"visible": [False, True,  False, False]}, 
                          {"yaxis.range": [0, 2500]}] # Focamos a câmara entre 0 e 2500 km
                ),
                dict(
                    label="MEO", 
                    method="update", 
                    args=[{"visible": [False, False, True,  False]}, 
                          {"yaxis.range": [2000, 36500]}] # Focamos na zona média
                ),
                dict(
                    label="GEO", 
                    method="update", 
                    args=[{"visible": [False, False, False, True]}, 
                          {"yaxis.range": [35000, 41000]}] # Focamos lá no alto
                ),
            ]),
            font=dict(size=9, color="#00d4ff"),
            bgcolor="#1f2937",
            bordercolor="#4a6fa5",
            borderwidth=1
        )
    ]
)

df_3d['EPOCH_YEAR'] = pd.to_datetime(df_3d['EPOCH'], errors='coerce').dt.year
launches = df_3d.groupby('EPOCH_YEAR').size().reset_index(name='count')
launches = launches[launches['EPOCH_YEAR'] >= 1960]
fig_line = go.Figure(data=[go.Scatter(
    x=launches['EPOCH_YEAR'], y=launches['count'], mode='lines+markers',
    line=dict(color='#4a6fa5', width=2), marker=dict(size=4)
)])
fig_line.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=35,r=20,t=10,b=20),
    xaxis=dict(showgrid=False, color='white', tickfont=dict(size=10)),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white', tickfont=dict(size=10))
)

fig_pct = go.Figure(data=[go.Pie(
    values=[len(df_3d[df_3d['ORBIT_TYPE']=='LEO']), len(df_3d)-len(df_3d[df_3d['ORBIT_TYPE']=='LEO'])],
    hole=0.7, marker_colors=['#4a6fa5','#2d3748']
)])
fig_pct.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', showlegend=False, margin=dict(l=0,r=0,t=0,b=0),
    annotations=[dict(text='LEO', x=0.5, y=0.5, font_size=11, font_color='white', showarrow=False)]
)

COLORS = {'background': '#0d1421', 'card': '#1a2332', 'border': '#2d3748', 'text': '#ffffff', 'accent': '#4a6fa5'}
card_style = {'backgroundColor': COLORS['card'], 'borderRadius': '15px', 'padding': '10px', 'display': 'flex', 'flexDirection': 'column', 'justifyContent': 'center', 'alignItems': 'center'}
# button_style = {'backgroundColor': COLORS['card'], 'color': COLORS['text'], 'border': 'none', 'borderRadius': '20px', 'padding': '8px 20px', 'cursor': 'pointer', 'fontSize': '14px'}

button_style = {
    'padding': '6px 16px',
    'borderRadius': '20px',
    'fontSize': '13px',
    'fontWeight': '500',
    'textDecoration': 'none',  # 👈 Remove o sublinhado do texto
    'display': 'inline-block',
    'backgroundColor': COLORS['card'], # Cor passiva (exemplo)
    'color': '#9ca3af',
    'border': '1px solid #374151',
}

filter_groups = [
    {'id': 'orbit',   'label': '🛸 Orbit Type', 'options': ['LEO','MEO','GEO','HEO'], 'default': ['LEO','MEO','GEO','HEO']},
    {'id': 'constellation', 'label': '🌐 Constellation', 'options': ['Starlink','OneWeb','Iridium','GPS','GLONASS','Galileo','BeiDou','COSMOS','FengYun','GOES','NOAA','ISS','Hubble','Other'], 'default': ['Starlink','OneWeb','Iridium','GPS','GLONASS','Galileo','BeiDou','COSMOS','FengYun','GOES','NOAA','ISS','Hubble','Other']},
    {'id': 'object_type', 'label': '🔷 Object Type', 'options': ['Satellite','Debris','Rocket Body','Space Station','Component','In Analysis','Unknown'], 'default': ['Satellite']},
    {'id': 'altitude', 'label': '📏 Altitude (km)', 'type': 'range', 'min': 0, 'max': 40000, 'default': [0, 40000]},
    {'id': 'inclination', 'label': '📐 Inclination (°)', 'type': 'range', 'min': 0, 'max': 180, 'default': [0, 180]},
]

def make_filter_section(group):
    gid      = group['id']
    is_range = group.get('type') == 'range'
    control  = (
        dcc.RangeSlider(
            id=f'filter-{gid}', min=group['min'], max=group['max'],
            value=group['default'], step=max(1, group['max']//100),
            marks={group['min']: str(group['min']), group['max']: str(group['max'])},
            tooltip={"placement": "bottom", "always_visible": False}
        ) if is_range else
        dcc.Checklist(
            id=f'filter-{gid}', options=[{'label': o, 'value': o} for o in group['options']], value=group['default'],
            labelStyle={'display': 'block', 'color': 'white', 'fontSize': '12px', 'marginBottom': '4px'},
            inputStyle={'marginRight': '6px', 'accentColor': '#4a6fa5'}
        )
    )
    return html.Div([
        html.Div(id=f'toggle-{gid}', children=[
            html.Span(group['label'], style={'fontSize': '13px', 'fontWeight': 'bold', 'color': 'white', 'flex': '1'}),
            html.Span('▾', id=f'arrow-{gid}', style={'color': '#4a6fa5', 'fontSize': '14px'})
        ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
                  'cursor': 'pointer', 'padding': '8px 4px', 'borderBottom': '1px solid #2d3748', 'userSelect': 'none'}),
        html.Div(id=f'collapse-{gid}', children=[control], style={'padding': '8px 4px 4px 4px', 'display': 'block'})
    ], style={'marginBottom': '4px'})

# ============================================================
# APP INICIALIZAÇÃO
# ============================================================
app = dash.Dash(__name__, suppress_callback_exceptions=True)

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Orbital Dashboard</title>
        {%favicon%}
        {%css%}
        <style>
            .dash-range-slider-input {
                display: none !important;
            }
            /* Slider de tempo no globo */
            #time-travel-slider .rc-slider-track { background-color: #ffd700 !important; }
            #time-travel-slider .rc-slider-handle { border-color: #ffd700 !important; background-color: #ffd700 !important; }
            #time-travel-slider .rc-slider-handle:hover { box-shadow: 0 0 8px rgba(255,215,0,0.6) !important; }
            #time-travel-slider .rc-slider-rail { background-color: #2d3748 !important; }
            #time-travel-slider .rc-slider-mark-text { color: #6b7280 !important; font-size: 10px !important; }
            /* Slider de conjunções */
            #conjunction-days-slider .rc-slider-track { background-color: #4a6fa5 !important; }
            #conjunction-days-slider .rc-slider-handle { border-color: #4a6fa5 !important; background-color: #00d4ff !important; }
            #conjunction-days-slider .rc-slider-handle:hover { border-color: #00d4ff !important; box-shadow: 0 0 8px rgba(0,212,255,0.5) !important; }
            #conjunction-days-slider .rc-slider-rail { background-color: #2d3748 !important; }
            #conjunction-days-slider .rc-slider-mark-text { color: #6b7280 !important; font-size: 11px !important; }
            .dash-table-container .previous-next-container button { background-color: #1a2332 !important; color: #4a6fa5 !important; border: 1px solid #2d3748 !important; border-radius: 6px !important; padding: 4px 10px !important; }
            .dash-table-container .previous-next-container button:hover { background-color: #2d3748 !important; color: #00d4ff !important; }
            .dash-table-container .page-number { color: #9ca3af !important; }
            ::-webkit-scrollbar { width: 6px; }
            ::-webkit-scrollbar-track { background: #0d1421; }
            ::-webkit-scrollbar-thumb { background: #2d3748; border-radius: 3px; }
            ::-webkit-scrollbar-thumb:hover { background: #4a6fa5; }
            /* Linhas clicáveis na tabela de conjunções */
            .conjunction-row-clickable:hover { background-color: #2d3748 !important; cursor: pointer; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# ============================================================
# LAYOUT
# ============================================================
layout = html.Div(style={
    'backgroundColor': COLORS['background'], 'minHeight': '100vh', 'padding': '15px',
    'fontFamily': 'Arial, sans-serif', 'boxSizing': 'border-box'
}, children=[
    # Stores
    dcc.Store(id='selected-object-idx',    data=None),
    dcc.Store(id='selected-norad-id',      data=None),
    # *** NOVO: stores para a visualização de conjunção ***
    dcc.Store(id='conj-view-active',       data=False),   # está em modo conjunção?
    dcc.Store(id='conj-primary-norad',     data=None),    # NORAD do satélite primário
    dcc.Store(id='conj-secondary-norad',   data=None),    # NORAD do satélite secundário
    dcc.Store(id='conj-time-str',          data=None),    # "YYYY-MM-DD HH:MM" da conjunção
    dcc.Store(id='conj-table-data-store',  data=[]),      # guarda os dados da tabela

    dcc.Interval(id='live-update-interval', interval=2000, n_intervals=0),

    html.Div(style={
        'display': 'flex', 
        'justifyContent': 'flex-end',  # Alinha os botões à direita
        'width': '100%', 
        'marginBottom': '10px'         # Margem sutil antes de começarem os gráficos
    }, children=[
        html.Div(style={'display': 'flex', 'gap': '10px'}, children=[
            dcc.Link(
                html.Button("satellites", style=button_style),
                href="/"
            ),
            dcc.Link(
                html.Button("launch", style=button_style), 
                href="/launches"
            )
        ])
    ]),

    html.Div(style={
        'display': 'grid',
        'gridTemplateColumns': '1fr 1fr 1.5fr 280px',
        'gridTemplateRows': '220px 80px 650px 450px',
        'gap': '15px', 'width': '100%',
    }, children=[
        # Linha 1
        html.Div(style={**card_style, 'gridColumn': '1 / 3', 'gridRow': '1'}, children=[
            dcc.Graph(figure=fig_type_object, config={'displayModeBar': False}, style={'width': '100%', 'height': '100%'})
        ]),
        html.Div(style={**card_style, 'gridColumn': '3 / 5', 'gridRow': '1 / 3', 'justifyContent': 'space-between', 'padding': '15px'}, children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'width': '100%', 'marginBottom': '10px'}, children=[
                html.Div('TOP CONSTELLATIONS', style={'color': COLORS['text'], 'fontSize': '14px', 'fontWeight': 'bold'}),
            ]),
            dcc.Graph(figure=fig_bar, config={'displayModeBar': False}, style={'width': '100%', 'height': '100%', 'flex': '1'})
        ]),

        # Linha 2
        html.Div(style={**card_style, 'gridColumn': '1', 'gridRow': '2'}, children=[
            html.Div(id='kpi-objects-count', children=f'{len(df_3d):,}', style={'color': '#00d4ff', 'fontSize': '26px', 'fontWeight': 'bold'}),
            html.Div('OBJECTS', style={'color': COLORS['text'], 'fontSize': '12px', 'letterSpacing': '1px'})
        ]),
        html.Div(style={**card_style, 'gridColumn': '2', 'gridRow': '2'}, children=[
            dcc.Graph(id='kpi-pct-graph', figure=fig_pct, config={'displayModeBar': False}, style={'width': '70px', 'height': '70px'})
        ]),

        # Linha 3 - Globo
        html.Div(id='globe-container', style={
            **card_style, 'gridColumn': '1 / 4', 'gridRow': '3',
            'position': 'relative', 'padding': '0', 'overflow': 'hidden'
        }, children=[
            dcc.Graph(
                id='globe-3d', figure=build_globe_figure(df_3d),
                config={'displayModeBar': True, 'modeBarButtonsToRemove': ['toImage'], 'scrollZoom': True},
                style={'width': '100%', 'height': '100%'}, clear_on_unhover=True
            ),

            # *** NOVO: Slider de viagem no tempo — canto inferior esquerdo ***
            html.Div(id='time-travel-container', style={
                'position': 'absolute', 'bottom': '20px', 'left': '20px',
                'backgroundColor': 'rgba(13,20,33,0.85)', 'backdropFilter': 'blur(5px)',
                'borderRadius': '10px', 'padding': '10px 16px 6px 16px',
                'border': '1px solid #2d3748', 'zIndex': '10', 'width': '260px',
            }, children=[
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'marginBottom': '6px'}, children=[
                    html.Span('⏱ Time travel', style={'color': '#ffd700', 'fontSize': '11px', 'fontWeight': 'bold', 'letterSpacing': '0.5px'}),
                    html.Span(id='time-travel-label', children='+0h (Now)',
                              style={'color': '#ffd700', 'fontSize': '11px', 'fontFamily': 'monospace'}),
                ]),
                dcc.Slider(
                    id='time-travel-slider',
                    min=-72, max=72, step=1, value=0,
                    marks={
                        -72: {'label': '-3d', 'style': {'color': '#6b7280', 'fontSize': '10px'}},
                        -48: {'label': '-2d', 'style': {'color': '#6b7280', 'fontSize': '10px'}},
                        -24: {'label': '-1d', 'style': {'color': '#6b7280', 'fontSize': '10px'}},
                          0: {'label': 'Now', 'style': {'color': '#ffd700', 'fontSize': '10px'}},
                         24: {'label': '+1d', 'style': {'color': '#6b7280', 'fontSize': '10px'}},
                         48: {'label': '+2d', 'style': {'color': '#6b7280', 'fontSize': '10px'}},
                         72: {'label': '+3d', 'style': {'color': '#6b7280', 'fontSize': '10px'}},
                    },
                    tooltip={'always_visible': False, 'placement': 'top'},
                ),
            ]),

            # Painel de informação do satélite — canto inferior direito
            html.Div(id='selected-info', style={
                'position': 'absolute', 'bottom': '20px', 'right': '20px',
                'backgroundColor': 'rgba(26,35,50,0.85)', 'backdropFilter': 'blur(5px)',
                'borderRadius': '10px', 'padding': '15px', 'border': '1px solid #2d3748',
                'zIndex': '10', 'minWidth': '250px', 'display': 'flex', 'flexDirection': 'column'
            }, children=[
                html.Div(id='satellite-data-container', children=[
                    html.Div('Click on an object on the globe to see its orbit',
                             style={'color': '#9ca3af', 'fontSize': '13px', 'fontStyle': 'italic'})
                ]),
                html.Button('🔍 Conjunctions', id='check-conjunctions-btn', n_clicks=0,
                            style={'display': 'none'})
            ]),

            # *** NOVO: Overlay de visualização de conjunção (por cima do globo) ***
            html.Div(id='conj-orbit-overlay', style={
                'display': 'none', 'position': 'absolute', 'top': '0', 'left': '0',
                'width': '100%', 'height': '100%', 'zIndex': '20',
                'flexDirection': 'column'
            }, children=[
                # Barra de controlo superior
                html.Div(style={
                    'position': 'absolute', 'top': '12px', 'left': '50%',
                    'transform': 'translateX(-50%)', 'zIndex': '30',
                    'display': 'flex', 'gap': '10px', 'alignItems': 'center',
                    'backgroundColor': 'rgba(13,20,33,0.9)', 'backdropFilter': 'blur(6px)',
                    'borderRadius': '10px', 'padding': '8px 16px', 'border': '1px solid #ff6b35',
                }, children=[
                    html.Span(id='conj-orbit-title',
                              style={'color': '#ff6b35', 'fontSize': '13px', 'fontWeight': 'bold', 'letterSpacing': '0.5px'}),
                    html.Button('← Voltar à Tabela', id='conj-back-btn', n_clicks=0, style={
                        **button_style, 'backgroundColor': '#2d3748', 'padding': '5px 14px', 'fontSize': '12px'
                    }),
                    html.Button('✖ Fechar', id='conj-close-btn', n_clicks=0, style={
                        **button_style, 'backgroundColor': '#8B0000', 'padding': '5px 14px', 'fontSize': '12px'
                    }),
                ]),
                # Globo de conjunção
                dcc.Graph(
                    id='globe-conjunction', figure=go.Figure(),
                    config={'displayModeBar': True, 'modeBarButtonsToRemove': ['toImage'], 'scrollZoom': True},
                    style={'width': '100%', 'height': '100%'}
                ),
            ]),
        ]),

        # Filtros
        html.Div(style={
            **card_style, 'gridColumn': '4', 'gridRow': '3 / 5',
            'justifyContent': 'flex-start', 'alignItems': 'stretch',
            'padding': '15px', 'overflowY': 'auto'
        }, children=[
            html.Div('▼ FILTERS', style={'color': COLORS['text'], 'fontSize': '15px', 'fontWeight': 'bold', 'marginBottom': '15px', 'borderBottom': '1px solid #4a6fa5', 'paddingBottom': '10px'}),
            *[make_filter_section(g) for g in filter_groups],
            html.Button('Apply Filters', id='apply-filters', n_clicks=0, style={
                **button_style, 'marginTop': 'auto', 'width': '100%',
                'backgroundColor': '#4a6fa5', 'fontWeight': 'bold', 'padding': '12px'
            })
        ]),

        # Linha 4
        html.Div(style={**card_style, 'gridColumn': '1', 'gridRow': '4', 'padding': '15px', 'display': 'flex', 'flexDirection': 'column', 'minHeight': '350px'}, children=[
            html.Div(style={'textAlign': 'center', 'marginBottom': '5px'}, children=[
                html.Div('ALTITUDE DENSITY', style={'color': COLORS['text'], 'fontSize': '12px', 'fontWeight': 'bold'}),
            ]),
            dcc.Graph(figure=fig_violin, config={'displayModeBar': False}, style={'width': '100%', 'height': '100%', 'flex': '1'})
        ]),
        html.Div(style={**card_style, 'gridColumn': '2 / 4', 'gridRow': '4', 'padding': '15px', 'display': 'flex', 'flexDirection': 'column', 'minHeight': '350px '}, children=[
            html.Div('CATALOG ENTRIES / YEAR', style={'color': COLORS['text'], 'fontSize': '13px', 'fontWeight': 'bold', 'marginBottom': '10px'}),
            dcc.Graph(figure=fig_line, config={'displayModeBar': False}, style={'width': '100%', 'height': '100%',  'flex': '1'})
        ]),
    ]),

    # ============================================================
    # Modal Conjunções
    # ============================================================
    html.Div(id='conjunction-modal', style={
        'display': 'none', 'position': 'fixed', 'top': '0', 'left': '0',
        'width': '100vw', 'height': '100vh',
        'backgroundColor': 'rgba(0,0,0,0.85)', 'zIndex': '9999',
        'justifyContent': 'center', 'alignItems': 'center'
    }, children=[
        html.Div(style={
            **card_style, 'width': '800px', 'maxHeight': '85vh', 'position': 'relative',
            'padding': '25px', 'justifyContent': 'flex-start', 'alignItems': 'stretch',
            'border': '1px solid #2d3748',
        }, children=[
            html.Button('✖', id='close-modal-btn', n_clicks=0, style={
                'position': 'absolute', 'top': '15px', 'right': '15px',
                'background': 'none', 'border': 'none', 'color': '#9ca3af',
                'fontSize': '18px', 'cursor': 'pointer'
            }),
            html.H3(id='modal-title', children='Análise de Conjunções', style={
                'color': '#00d4ff', 'marginTop': '0', 'marginBottom': '20px',
                'fontSize': '18px', 'fontWeight': 'bold', 'letterSpacing': '0.5px'
            }),
            # Subtítulo de instrução
            html.Div('💡 Click on a row to visualize the two orbits on the globe', style={
                'color': '#6b7280', 'fontSize': '11px', 'marginBottom': '14px',
                'fontStyle': 'italic'
            }),
            # Slider de dias
            html.Div(style={'width': '100%', 'marginBottom': '28px'}, children=[
                html.Span('Janela de Tempo (Dias):', style={
                    'color': '#9ca3af', 'fontSize': '12px', 'letterSpacing': '1px',
                    'textTransform': 'uppercase', 'marginBottom': '12px', 'display': 'block'
                }),
                dcc.Slider(
                    id='conjunction-days-slider', min=1, max=5, step=1, value=3,
                    marks={i: dict(label=str(i), style={'color': '#6b7280', 'fontSize': '11px'}) for i in range(1, 6)},
                    tooltip={'always_visible': False, 'placement': 'bottom'},
                ),
            ]),
            # Tabela (clicável)
            dcc.Loading(color='#00d4ff', type='circle', children=[
                dash_table.DataTable(
                    id='conjunction-table',
                    columns=[
                        {'name': 'Objeto Espacial', 'id': 'NAME'},
                        {'name': 'NORAD ID',        'id': 'NORAD_ID'},
                        {'name': 'Dist. Mín. (km)', 'id': 'MIN_DIST_KM'},
                        {'name': 'Data/Hora (UTC)', 'id': 'TIME_UTC'},
                    ],
                    data=[],
                    page_size=10,
                    row_selectable='single',   # *** NOVO: permite seleccionar linha ***
                    selected_rows=[],
                    style_table={
                        'borderRadius': '8px', 'overflow': 'hidden',
                        'width': '100%', 'border': '1px solid #2d3748',
                    },
                    style_header={
                        'backgroundColor': '#0d1421', 'color': '#4a6fa5', 'fontWeight': 'bold',
                        'textAlign': 'left', 'border': 'none', 'borderBottom': '2px solid #2d3748',
                        'fontSize': '11px', 'letterSpacing': '1px', 'textTransform': 'uppercase',
                        'padding': '8px 10px'
                    },
                    style_cell={
                        'backgroundColor': '#1a2332', 'color': '#e2e8f0', 'textAlign': 'left',
                        'border': 'none', 'borderBottom': '1px solid #2d3748',
                        'padding': '6px 10px', 'fontSize': '12px',
                        'overflow': 'hidden', 'textOverflow': 'ellipsis', 'maxWidth': '0'
                    },
                    style_cell_conditional=[
                        {'if': {'column_id': 'NAME'},        'width': '38%'},
                        {'if': {'column_id': 'NORAD_ID'},    'width': '14%'},
                        {'if': {'column_id': 'MIN_DIST_KM'}, 'width': '22%'},
                        {'if': {'column_id': 'TIME_UTC'},    'width': '26%'},
                    ],
                    style_data_conditional=[
                        {'if': {'row_index': 'odd'}, 'backgroundColor': '#162030'},
                        {'if': {'filter_query': '{MIN_DIST_KM} < 10'},
                         'backgroundColor': 'rgba(255,107,53,0.20)', 'color': '#ff6b35', 'fontWeight': 'bold'},
                        {'if': {'filter_query': '{MIN_DIST_KM} >= 10 && {MIN_DIST_KM} < 100'},
                         'backgroundColor': 'rgba(255,215,0,0.08)', 'color': '#ffd700'},
                        {'if': {'state': 'active'},
                         'backgroundColor': '#2d3748', 'border': '1px solid #4a6fa5'},
                        {'if': {'state': 'selected'},
                         'backgroundColor': 'rgba(74,111,165,0.3)', 'border': '1px solid #4a6fa5'},
                    ],
                    style_as_list_view=True,
                )
            ]),
            # *** NOVO: botão "Ver Órbitas" que aparece quando há linha selecionada ***
            html.Div(style={'marginTop': '14px', 'display': 'flex', 'gap': '10px', 'justifyContent': 'flex-end'}, children=[
                html.Button('🌍 Ver Órbitas no Globo', id='view-conj-orbits-btn', n_clicks=0, style={
                    **button_style, 'backgroundColor': '#ff6b35', 'fontWeight': 'bold',
                    'padding': '8px 18px', 'fontSize': '12px', 'display': 'none'
                }),
            ]),
        ])
    ])
])

# ============================================================
# CALLBACKS
# ============================================================

# --- Filtros collapse ---
for group in filter_groups:
    gid = group['id']
    @callback(
        Output(f'collapse-{gid}', 'style'),
        Output(f'arrow-{gid}', 'children'),
        Input(f'toggle-{gid}', 'n_clicks'),
        State(f'collapse-{gid}', 'style'),
        prevent_initial_call=True
    )
    def toggle_collapse(n_clicks, current_style, _gid=gid):
        if current_style and current_style.get('display') == 'none':
            return {'padding': '8px 4px 4px 4px', 'display': 'block'}, '▾'
        return {'display': 'none'}, '▸'


# --- Click no globo ---
@callback(
    Output('selected-object-idx', 'data'),
    Output('selected-norad-id',   'data'),
    Input('globe-3d', 'clickData'),
    prevent_initial_call=True
)
def store_click(click_data):
    if click_data is None: return None, None
    try:
        pt = click_data['points'][0]
        cd = pt.get('customdata')
        if cd is not None: return int(cd[0]), int(cd[7])
    except Exception as ex:
        print(f"store_click error: {ex}")
    return None, None


# --- Label do slider de tempo ---
@callback(
    Output('time-travel-label', 'children'),
    Input('time-travel-slider', 'value')
)
def update_time_label(hours):
    if hours == 0:
        return '+0h (Now)'
    sign = '+' if hours > 0 else ''
    days = abs(hours) // 24
    rem  = abs(hours) % 24
    if days > 0 and rem > 0:
        label = f"{'-' if hours < 0 else '+'}{days}d {rem}h"
    elif days > 0:
        label = f"{'-' if hours < 0 else '+'}{days}d"
    else:
        label = f"{sign}{hours}h"
    target = datetime.utcnow() + timedelta(hours=hours)
    return f"{label}  ({target.strftime('%m-%d %H:%M')})"


# --- Globo principal ---
@callback(
    Output('globe-3d', 'figure'),
    Output('satellite-data-container', 'children'),
    Output('check-conjunctions-btn', 'style'),
    Output('kpi-pct-graph', 'figure'), 
    Output('kpi-objects-count', 'children'),
    Input('live-update-interval', 'n_intervals'),
    Input('apply-filters',        'n_clicks'),
    Input('selected-object-idx',  'data'),
    Input('close-modal-btn',      'n_clicks'),
    Input('time-travel-slider',   'value'),       # *** NOVO ***
    State('filter-orbit',         'value'),
    State('filter-constellation', 'value'),
    State('filter-object_type',   'value'),
    State('filter-altitude',      'value'),
    State('filter-inclination',   'value'),
    prevent_initial_call=False
)
def update_globe(n_intervals, apply_clicks, selected_idx, close_clicks, time_offset_hours,
                 orbit_vals, const_vals, obj_type_vals, alt_range, inc_range):
    global df_3d

    ctx     = dash.callback_context
    trigger = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

    # Só actualiza posições no live tick ou fecho do modal
    if trigger in ['live-update-interval', 'close-modal-btn']:
        df_3d = update_live_positions(df_3d)

    current_time_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    df_f = df_3d.copy()
    if orbit_vals:    df_f = df_f[df_f['ORBIT_TYPE'].isin(orbit_vals)]
    if const_vals:    df_f = df_f[df_f['CONSTELLATION'].isin(const_vals)]
    if obj_type_vals: df_f = df_f[df_f['OBJECT_TYPE'].isin(obj_type_vals)]
    if alt_range:     df_f = df_f[(df_f['ALTITUDE'] >= alt_range[0]) & (df_f['ALTITUDE'] <= alt_range[1])]
    if inc_range:     df_f = df_f[(df_f['INCLINATION'] >= inc_range[0]) & (df_f['INCLINATION'] <= inc_range[1])]

    orbit_row    = None
    btn_style    = {'display': 'none'}
    info_children = [html.Div('Click on an object on the globe to see its orbit',
                               style={'color': '#9ca3af', 'fontSize': '13px', 'fontStyle': 'italic'})]

    if selected_idx is not None and selected_idx in df_3d.index:
        orbit_row = df_3d.loc[selected_idx]

        def kpi(label, value):
            return html.Div([
                html.Div(value, style={'color': '#00d4ff', 'fontSize': '14px', 'fontWeight': 'bold'}),
                html.Div(label, style={'color': '#9ca3af', 'fontSize': '11px'})
            ], style={'textAlign': 'left'})

        info_children = [
            html.Div(orbit_row['NAME'], style={
                'color': 'white', 'fontSize': '15px', 'fontWeight': 'bold',
                'maxWidth': '220px', 'whiteSpace': 'nowrap', 'overflow': 'hidden',
                'textOverflow': 'ellipsis', 'borderBottom': '1px solid #2d3748',
                'paddingBottom': '10px', 'marginBottom': '12px'
            }),
            html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '12px'}, children=[
                kpi('Altitude',    f"{orbit_row['ALTITUDE']:.0f} km"),
                kpi('Órbita',      orbit_row['ORBIT_TYPE']),
                kpi('Inclinação',  f"{orbit_row['INCLINATION']:.1f}°"),
                kpi('Período',     f"{orbit_row['PERIOD']:.1f} min"),
                kpi('Constelação', orbit_row['CONSTELLATION']),
                kpi('NORAD ID',    str(int(orbit_row['NORAD_CAT_ID'])))
            ])
        ]
        btn_style = {
            **button_style, 'backgroundColor': '#4a6fa5', 'padding': '8px 10px',
            'fontSize': '12px', 'fontWeight': 'bold', 'display': 'block',
            'marginTop': '15px', 'width': '100%'
        }

    time_offset = time_offset_hours if time_offset_hours is not None else 0
    fig = build_globe_figure(df_f, orbit_row=orbit_row,
                             current_time_str=current_time_str,
                             time_offset_hours=time_offset)
    
    # DONUT GRAPH COM PERCENTAGEM DE OBJETOS E NUMERO DE OBJETOS
    total_global = len(df_3d)
    total_filtrado = len(df_f)
    percentagem = (total_filtrado / total_global) * 100 if total_global > 0 else 0

    fig_pct_nova = go.Figure(data=[go.Pie(
        values=[total_filtrado, total_global - total_filtrado],
        hole=0.7, 
        marker_colors=['#00d4ff', '#2d3748'], # Azul claro para os selecionados, fundo cinza para o resto
        textinfo='none', # Limpa o texto fora do gráfico
        hoverinfo='skip'
    )])
    
    fig_pct_nova.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', showlegend=False, margin=dict(l=0,r=0,t=0,b=0),
        annotations=[dict(
            text=f"{percentagem:.1f}%", # 👈 É aqui que a percentagem vai para o meio do círculo!
            x=0.5, y=0.5, font_size=12, font_color='white', font_weight='bold', showarrow=False
        )]
    )
    
    texto_total_novo = f"{total_filtrado:,}"

    return fig, info_children, btn_style, fig_pct_nova, texto_total_novo


# --- Modal abertura/fecho ---
@callback(
    Output('conjunction-modal', 'style'),
    Output('modal-title',       'children'),
    Input('check-conjunctions-btn', 'n_clicks'),
    Input('close-modal-btn',        'n_clicks'),
    State('selected-object-idx',    'data'),
    State('conjunction-modal',      'style'),
    prevent_initial_call=True
)
def toggle_modal(open_clicks, close_clicks, selected_idx, current_style):
    trigger = dash.callback_context.triggered[0]['prop_id'].split('.')[0]
    if trigger == 'close-modal-btn':
        return {**current_style, 'display': 'none'}, dash.no_update
    if trigger == 'check-conjunctions-btn' and open_clicks:
        title = 'Análise de Conjunções'
        if selected_idx is not None and selected_idx in df_3d.index:
            title = f"Risco de Colisão — {df_3d.loc[selected_idx, 'NAME']}"
        return {**current_style, 'display': 'flex'}, title
    return current_style, dash.no_update


# --- Tabela de conjunções ---
@callback(
    Output('conjunction-table',     'data'),
    Output('conj-table-data-store', 'data'),
    Input('check-conjunctions-btn',  'n_clicks'),
    Input('conjunction-days-slider', 'value'),
    State('selected-norad-id',       'data'),
    prevent_initial_call=True
)
def update_conjunction_table(open_clicks, days, norad_id):
    if not open_clicks or open_clicks < 1:
        return dash.no_update, dash.no_update
    if norad_id is None:
        return [], []
    try:
        df_result = run_live_conjunction_analysis(
            target_norad_id=int(norad_id), tle_dataframe=tle,
            days=int(days), step_minutes=15.0, top_n=10, buffer_km=75.0,
        )
        if df_result.empty:
            empty_row = [{'NAME': '✅ Órbita limpa (Sem risco detetado)', 'NORAD_ID': '-', 'MIN_DIST_KM': '-', 'TIME_UTC': '-'}]
            return empty_row, empty_row
        records = df_result.to_dict('records')
        return records, records
    except Exception as ex:
        print(f"❌ Erro conjunction analysis: {ex}")
        return [], []


# --- Botão "Ver Órbitas" aparece quando há linha selecionada ---
@callback(
    Output('view-conj-orbits-btn', 'style'),
    Input('conjunction-table', 'selected_rows'),
    State('conj-table-data-store', 'data'),
    prevent_initial_call=True
)
def show_view_orbits_btn(selected_rows, table_data):
    if selected_rows and table_data:
        row = table_data[selected_rows[0]]
        # Não mostrar se for a linha de "órbita limpa"
        if str(row.get('NORAD_ID', '-')) == '-':
            return {'display': 'none'}
        return {
            **button_style, 'backgroundColor': '#ff6b35', 'fontWeight': 'bold',
            'padding': '8px 18px', 'fontSize': '12px', 'display': 'block'
        }
    return {'display': 'none'}


# --- Activar visualização de conjunção (fechar modal e mostrar overlay) ---
@callback(
    Output('conjunction-modal',   'style', allow_duplicate=True),
    Output('conj-view-active',    'data'),
    Output('conj-primary-norad',  'data'),
    Output('conj-secondary-norad','data'),
    Output('conj-time-str',       'data'),
    Input('view-conj-orbits-btn', 'n_clicks'),
    State('conjunction-table',    'selected_rows'),
    State('conj-table-data-store','data'),
    State('selected-norad-id',    'data'),
    State('conjunction-modal',    'style'),
    prevent_initial_call=True
)
def activate_conj_view(n_clicks, selected_rows, table_data, primary_norad, modal_style):
    if not n_clicks or not selected_rows or not table_data:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    row = table_data[selected_rows[0]]
    secondary_norad = row.get('NORAD_ID')
    conj_time       = row.get('TIME_UTC')
    # Fechar modal
    new_modal_style = {**modal_style, 'display': 'none'}
    return new_modal_style, True, primary_norad, secondary_norad, conj_time


# --- Construir o globo de conjunção e controlar overlay ---
@callback(
    Output('conj-orbit-overlay',  'style'),
    Output('globe-conjunction',   'figure'),
    Output('conj-orbit-title',    'children'),
    Output('time-travel-slider',  'value'),        # *** Posiciona o slider na hora da conjunção ***
    Input('conj-view-active',     'data'),
    Input('conj-back-btn',        'n_clicks'),
    Input('conj-close-btn',       'n_clicks'),
    State('conj-primary-norad',   'data'),
    State('conj-secondary-norad', 'data'),
    State('conj-time-str',        'data'),
    prevent_initial_call=True
)
def render_conj_orbit_view(is_active, back_clicks, close_clicks,
                            primary_norad, secondary_norad, conj_time_str):
    trigger = dash.callback_context.triggered[0]['prop_id'].split('.')[0]

    hidden_style = {'display': 'none', 'position': 'absolute', 'top': '0', 'left': '0',
                    'width': '100%', 'height': '100%', 'zIndex': '20', 'flexDirection': 'column'}
    shown_style  = {**hidden_style, 'display': 'flex'}

    # Fechar / Voltar
    if trigger in ['conj-back-btn', 'conj-close-btn']:
        return hidden_style, dash.no_update, dash.no_update, 0

    if not is_active:
        return hidden_style, dash.no_update, dash.no_update, dash.no_update

    # Calcular offset de horas da conjunção para posicionar o slider
    slider_val = 0
    if conj_time_str:
        try:
            conj_dt   = datetime.strptime(conj_time_str, '%Y-%m-%d %H:%M')
            now_utc   = datetime.utcnow()
            delta_h   = (conj_dt - now_utc).total_seconds() / 3600.0
            slider_val = max(-72, min(72, round(delta_h)))
        except:
            slider_val = 0

    # Procurar linhas TLE dos dois satélites
    primary_rows   = tle[tle['NORAD_CAT_ID'] == int(primary_norad)]   if primary_norad   else pd.DataFrame()
    secondary_rows = tle[tle['NORAD_CAT_ID'] == int(secondary_norad)] if secondary_norad else pd.DataFrame()

    if primary_rows.empty or secondary_rows.empty:
        return shown_style, go.Figure(), '⚠ Dados TLE não encontrados', slider_val

    primary_tle_row   = primary_rows.iloc[0]
    secondary_tle_row = secondary_rows.iloc[0]

    # Adicionar SNAPSHOT_TIME (necessário para compute_orbit_line)
    now = datetime.utcnow()
    primary_tle_row   = primary_tle_row.copy();   primary_tle_row['SNAPSHOT_TIME']   = now
    secondary_tle_row = secondary_tle_row.copy(); secondary_tle_row['SNAPSHOT_TIME'] = now

    fig = build_conjunction_orbit_figure(primary_tle_row, secondary_tle_row, conj_time_str)

    p_name = str(primary_tle_row.get('NAME', primary_norad))
    s_name = str(secondary_tle_row.get('NAME', secondary_norad))
    title  = f"⚠ Conjunção: {p_name}  ↔  {s_name}  |  {conj_time_str} UTC"

    return shown_style, fig, title, slider_val


# --- "Voltar à Tabela": reabre o modal ---
@callback(
    Output('conjunction-modal', 'style', allow_duplicate=True),
    Output('conj-view-active',  'data',  allow_duplicate=True),
    Input('conj-back-btn', 'n_clicks'),
    State('conjunction-modal', 'style'),
    prevent_initial_call=True
)
def back_to_table(n_clicks, modal_style):
    if n_clicks:
        return {**modal_style, 'display': 'flex'}, False
    return dash.no_update, dash.no_update


if __name__ == '__main__':
    app.run(debug=True)