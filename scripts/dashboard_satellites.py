import dash
from dash import dcc, html, Input, Output, State, dash_table
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from urllib.request import urlopen

from sgp4.api import Satrec, jday
from datetime import datetime

# ============================================================
# CARREGAR DADOS
# ============================================================
path = '.'
tle = pd.read_csv(f'{path}/../DATASETS_SATTELITES/spacetrack_last_data_tle.csv')
tle = pd.read_csv(f'{path}/../DATASETS_SATTELITES/merged_dataset_tle.csv')

# ============================================================
# PREPARAR DADOS 3D
# ============================================================
def prepare_3d_data(df):
    mu = 398600.4418
    
    # 1. Filtros iniciais
    valid = (df['PERIOD'] > 0) & (df['ECCENTRICITY'] < 1) & (df['ECCENTRICITY'] >= 0)
    df = df[valid].copy()

    # 2. Converter EPOCH para formato data e definir o tempo atual
    # Usamos utcnow() porque os TLEs usam UTC
    df['EPOCH'] = pd.to_datetime(df['EPOCH'])
    tempo_atual = datetime.utcnow()
    
    # Calcular diferença de tempo em dias
    delta_t_dias = (tempo_atual - df['EPOCH']).dt.total_seconds() / 86400.0

    # 3. Propagar a Anomalia Média para o tempo atual
    # MEAN_MOTION está em revoluções por dia. Multiplicamos por 2*pi para radianos/dia.
    delta_m_rad = df['MEAN_MOTION'] * 2 * np.pi * delta_t_dias
    m_anom_atual = np.radians(df['MEAN_ANOMALY']) + delta_m_rad

    period_sec = df['PERIOD'] * 60
    e      = df['ECCENTRICITY']
    inc    = np.radians(df['INCLINATION'])
    raan   = np.radians(df['RA_OF_ASC_NODE'])
    arg_p  = np.radians(df['ARG_OF_PERICENTER'])

    a = ((period_sec * np.sqrt(mu)) / (2 * np.pi))**(2/3)

    # 4. Usar a nova anomalia média propagada (m_anom_atual)
    x_orb = a * (np.cos(m_anom_atual) - e)
    y_orb = a * (np.sqrt(1 - e**2) * np.sin(m_anom_atual))

    cr, sr = np.cos(raan), np.sin(raan)
    ca, sa = np.cos(arg_p), np.sin(arg_p)
    ci, si = np.cos(inc),   np.sin(inc)

    # Cálculo do X, Y, Z (igual ao teu código)
    df['X'] = (cr*ca - sr*sa*ci)*x_orb + (-cr*sa - sr*ca*ci)*y_orb
    df['Y'] = (sr*ca + cr*sa*ci)*x_orb + (-sr*sa + cr*ca*ci)*y_orb
    df['Z'] = (sa*si)*x_orb            + (ca*si)*y_orb

    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=['X','Y','Z'])

    df['ORBIT_TYPE'] = pd.cut(
        df['PERIOD'],
        bins=[0, 128, 600, 1500, 99999],
        labels=['LEO', 'MEO', 'GEO', 'HEO']
    ).astype(str)

    name_upper = df['NAME'].str.upper()
    conditions = [
        name_upper.str.contains('DEB|DEBRIS', na=False),
        name_upper.str.contains(r'R/B|ROCKET', na=False),
        name_upper.str.contains('ISS|STATION', na=False),
    ]
    
    type_mapping = {
        'SATELLITE': 'Satellite',
        'ROCKET BODY': 'Rocket Body',
        'DEBRIS': 'Debris',
        'SPACE STATION': 'Space Station',
        'COMPONENT': 'Component',
        'IN ANALYSIS': 'In Analysis',
        'UNKNOWN': 'Unknown'
    }

    df['OBJECT_TYPE'] = df['OBJECT_TYPE'].str.upper().map(type_mapping).fillna('Satellite')

    # Refinar apenas se o tipo for Unknown ou Satellite usando o nome
    name_upper = df['NAME'].str.upper()
    mask_refine = df['OBJECT_TYPE'].isin(['Satellite', 'Unknown'])

    df.loc[mask_refine & name_upper.str.contains('ISS|STATION|TIANGONG'), 'OBJECT_TYPE'] = 'Space Station'
    df.loc[mask_refine & name_upper.str.contains(r'R/B|ROCKET|STAGE'), 'OBJECT_TYPE'] = 'Rocket Body'
    df.loc[mask_refine & name_upper.str.contains('DEB|DEBRIS'), 'OBJECT_TYPE'] = 'Debris'

    constellation_map = {
        'STARLINK': 'Starlink', 'ONEWEB': 'OneWeb',  'IRIDIUM': 'Iridium',
        'GPS':      'GPS',      'GLONASS': 'GLONASS', 'GALILEO': 'Galileo',
        'BEIDOU':   'BeiDou',   'COSMOS':  'COSMOS',  'FENGYUN': 'FengYun',
        'GOES':     'GOES',     'NOAA':    'NOAA',    'ISS':     'ISS',
        'HUBBLE':   'Hubble',
    }
    
    df['CONSTELLATION'] = 'Other'
    for key, val in constellation_map.items():
        mask = name_upper.str.contains(key, na=False) & (df['CONSTELLATION'] == 'Other')
        df.loc[mask, 'CONSTELLATION'] = val

    df['ALTITUDE'] = (np.sqrt(df['X']**2 + df['Y']**2 + df['Z']**2) - 6371).round(0)
    df = df.reset_index(drop=True)
    df['IDX'] = df.index
    return df

# SEGUNDA OPÇAO COM SGP4
def prepare_3d_data(df):
    # 1. Limpar objetos que não tenham TLE
    df = df.dropna(subset=['TLE_LINE1', 'TLE_LINE2']).copy()

    # 2. Obter o tempo atual exato em formato Julian Date (necessário para a NASA/SGP4)
    tempo_atual = datetime.utcnow()

    df['SNAPSHOT_TIME'] = tempo_atual

    jd, fr = jday(tempo_atual.year, tempo_atual.month, tempo_atual.day, 
                  tempo_atual.hour, tempo_atual.minute, tempo_atual.second)

    # Listas para guardar os resultados
    x_list, y_list, z_list = [], [], []
    vel_list, alt_list = [], []

    # 3. A Magia: Calcular a posição real para cada satélite
    for index, row in df.iterrows():
        try:
            # Carregar o satélite
            sat = Satrec.twoline2rv(row['TLE_LINE1'], row['TLE_LINE2'])
            
            # e = erro (0 é bom), r = posição [x,y,z], v = velocidade [vx,vy,vz]
            e, r, v = sat.sgp4(jd, fr)

            if e == 0:
                x_list.append(r[0])
                y_list.append(r[1])
                z_list.append(r[2])
                
                # Calcular Velocidade (km/s) e Altitude (km)
                vel_list.append(np.sqrt(v[0]**2 + v[1]**2 + v[2]**2))
                alt_list.append(np.sqrt(r[0]**2 + r[1]**2 + r[2]**2) - 6371.0)
            else:
                # Se houver erro no TLE, preenchemos com NaN
                x_list.append(np.nan); y_list.append(np.nan); z_list.append(np.nan)
                vel_list.append(np.nan); alt_list.append(np.nan)
        except:
            x_list.append(np.nan); y_list.append(np.nan); z_list.append(np.nan)
            vel_list.append(np.nan); alt_list.append(np.nan)

    # Guardar os resultados no DataFrame
    df['X_ECI'] = x_list
    df['Y_ECI'] = y_list
    df['Z_ECI'] = z_list
    df['VELOCITY'] = vel_list
    df['ALTITUDE'] = alt_list

    # Remover os satélites corrompidos
    df = df.dropna(subset=['X_ECI', 'Y_ECI', 'Z_ECI'])

    # 4. CORREÇÃO DA ROTAÇÃO DA TERRA (ECI para ECEF)
    # A biblioteca dá-nos as coordenadas "no espaço" (ECI).
    # Como o teu mapa Plotly não roda, temos de rodar as coordenadas do satélite 
    # de acordo com o tempo sideral para baterem certo com os países.
    def calculate_gmst(date_utc):
        jd_now = pd.Timestamp(date_utc).to_julian_date()
        d = jd_now - 2451545.0
        gmst = 280.46061837 + 360.98564736629 * d
        return np.radians(gmst % 360)

    theta = calculate_gmst(tempo_atual)

    # Rotação matemática para alinhar com os continentes
    df['X'] = df['X_ECI'] * np.cos(theta) + df['Y_ECI'] * np.sin(theta)
    df['Y'] = -df['X_ECI'] * np.sin(theta) + df['Y_ECI'] * np.cos(theta)
    df['Z'] = df['Z_ECI']  # O Z (Polos) não muda com a rotação

    if 'PERIOD' in df.columns:
        df['ORBIT_TYPE'] = pd.cut(
            df['PERIOD'],
            bins=[0, 128, 600, 1500, 99999],
            labels=['LEO', 'MEO', 'GEO', 'HEO']
        ).astype(str)
    
    # -> Object Type (Satellite, Debris, etc)
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
    
    name_upper = df['NAME'].str.upper() # Precisamos disto para o filtro não falhar
    
    constellation_map = {
        'STARLINK': 'Starlink', 'ONEWEB': 'OneWeb',  'IRIDIUM': 'Iridium',
        'GPS':      'GPS',      'GLONASS': 'GLONASS', 'GALILEO': 'Galileo',
        'BEIDOU':   'BeiDou',   'COSMOS':  'COSMOS',  'FENGYUN': 'FengYun',
        'GOES':     'GOES',     'NOAA':    'NOAA',    'ISS':     'ISS',
        'HUBBLE':   'Hubble',
    }
    
    df['CONSTELLATION'] = 'Other'
    for key, val in constellation_map.items():
        mask = name_upper.str.contains(key, na=False) & (df['CONSTELLATION'] == 'Other')
        df.loc[mask, 'CONSTELLATION'] = val
    # ---------------------------------------------

    df = df.reset_index(drop=True)
    df['IDX'] = df.index
    return df

df_3d = prepare_3d_data(tle)
print(f"✅ Objectos 3D carregados: {len(df_3d):,}")

# ============================================================
# CACHE E CÁLCULO DE CONJUNÇÕES (vectorizado, sem Skyfield)
# ============================================================
_CONJ_CACHE = None

def _build_conjunction_cache(df: pd.DataFrame) -> pd.DataFrame:
    mu    = 398600.4418
    valid = (df['PERIOD'] > 0) & (df['ECCENTRICITY'] < 1) & (df['ECCENTRICITY'] >= 0)
    df    = df[valid].copy().reset_index(drop=True)
    a     = ((df['PERIOD'].values * 60 * np.sqrt(mu)) / (2 * np.pi))**(2/3)
    e     = df['ECCENTRICITY'].values
    df['_APOGEE_KM']  = a * (1 + e) - 6371.0
    df['_PERIGEE_KM'] = a * (1 - e) - 6371.0
    df['_A_KM']       = a
    return df

def _get_cache(df: pd.DataFrame) -> pd.DataFrame:
    global _CONJ_CACHE
    if _CONJ_CACHE is None:
        print("⏳ A construir cache de conjunções (uma vez)...")
        _CONJ_CACHE = _build_conjunction_cache(df)
        print(f"✅ Cache pronta: {len(_CONJ_CACHE):,} objectos.")
    return _CONJ_CACHE

def _propagate_batch(sats_df: pd.DataFrame, n_steps: int, step_min: float):
    """Propaga todos os satélites vectorizados. Devolve X,Y,Z [n_sats × n_steps]."""
    mu          = 398600.4418
    M0          = np.radians(sats_df['MEAN_ANOMALY'].values)
    mean_motion = sats_df['MEAN_MOTION'].values * 2 * np.pi / 1440.0  # rad/min
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
    xo = r * np.cos(nu)
    yo = r * np.sin(nu)

    cr, sr = np.cos(raan)[:, None], np.sin(raan)[:, None]
    ca, sa = np.cos(argp)[:, None], np.sin(argp)[:, None]
    ci, si = np.cos(inc)[:, None],  np.sin(inc)[:, None]

    X = (cr*ca - sr*sa*ci)*xo + (-cr*sa - sr*ca*ci)*yo
    Y = (sr*ca + cr*sa*ci)*xo + (-sr*sa + cr*ca*ci)*yo
    Z = (sa*si)*xo             + (ca*si)*yo
    return X, Y, Z

def run_live_conjunction_analysis(
    target_norad_id : int,
    tle_dataframe   : pd.DataFrame,
    days            : int   = 7,
    step_minutes    : float = 15.0,
    top_n           : int   = 10,
    buffer_km       : float = 75.0,
) -> pd.DataFrame:
    df_c            = _get_cache(tle_dataframe)
    target_norad_id = int(target_norad_id)

    tgt_mask = df_c['NORAD_CAT_ID'] == target_norad_id
    if not tgt_mask.any():
        print(f"❌ NORAD ID {target_norad_id} não encontrado na cache.")
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
    print(f"🔍 {len(candidates):,} candidatos após pré-filtro de altitude.")

    if candidates.empty:
        return pd.DataFrame(columns=['NAME','NORAD_ID','MIN_DIST_KM','TIME_UTC'])

    n_steps = max(1, int(days * 24 * 60 / step_minutes))
    print(f"⏳ A propagar {len(candidates):,} objectos × {n_steps} passos...")

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

    print(f"✅ Análise concluída.")
    return pd.DataFrame(records)

# ============================================================
# ÓRBITA COMPLETA (Kepler)
# ============================================================
def compute_orbit_line(row, n_points: int = 300):
    mu         = 398600.4418
    period_sec = float(row['PERIOD']) * 60
    a          = ((period_sec * np.sqrt(mu)) / (2 * np.pi))**(2/3)
    e          = float(row['ECCENTRICITY'])
    inc        = np.radians(float(row['INCLINATION']))
    raan       = np.radians(float(row['RA_OF_ASC_NODE']))
    argp       = np.radians(float(row['ARG_OF_PERICENTER']))

    nu  = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    r   = a * (1 - e**2) / (1 + e * np.cos(nu))
    xo  = r * np.cos(nu)
    yo  = r * np.sin(nu)

    cr, sr = np.cos(raan), np.sin(raan)
    ca, sa = np.cos(argp), np.sin(argp)
    ci, si = np.cos(inc),  np.sin(inc)

    X = (cr*ca - sr*sa*ci)*xo + (-cr*sa - sr*ca*ci)*yo
    Y = (sr*ca + cr*sa*ci)*xo + (-sr*sa + cr*ca*ci)*yo
    Z = (sa*si)*xo             + (ca*si)*yo

    X = np.append(X, X[0])
    Y = np.append(Y, Y[0])
    Z = np.append(Z, Z[0])
    return X.tolist(), Y.tolist(), Z.tolist()

def compute_orbit_line(row, n_points: int = 300):
    # 1. Carregar o satélite exato a partir das TLE Lines
    sat = Satrec.twoline2rv(row['TLE_LINE1'], row['TLE_LINE2'])
    
    # 2. Obter o período em minutos
    period_minutes = float(row['PERIOD'])
    
    # 3. Marcar o tempo inicial ("agora")
    # tempo_atual = datetime.utcnow()
    tempo_atual = pd.to_datetime(row['SNAPSHOT_TIME'])
    
    X, Y, Z = [], [], []
    
    # 4. Calcular 'n_points' ao longo da órbita com o SGP4
    for i in range(n_points):
        # Avançar o tempo (fração do período)
        delta_minutes = (period_minutes / n_points) * i
        t_point = tempo_atual + timedelta(minutes=delta_minutes)
        
        # Converter este momento para Julian Date
        jd, fr = jday(t_point.year, t_point.month, t_point.day, 
                      t_point.hour, t_point.minute, t_point.second + t_point.microsecond / 1e6)
        
        # Pedir ao SGP4 a posição ECI neste exato segundo
        e, r, v = sat.sgp4(jd, fr)
        
        if e == 0:
            X.append(r[0])
            Y.append(r[1])
            Z.append(r[2])

    # 5. Fechar o anel perfeitamente (ligar o último ponto ao primeiro)
    if len(X) > 0:
        X.append(X[0])
        Y.append(Y[0])
        Z.append(Z[0])
        
    return X, Y, Z

# ============================================================
# GLOBO 3D
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
                    lat_r = np.radians(lats)
                    lon_r = np.radians(lons)
                    xs.extend((r * np.cos(lat_r) * np.cos(lon_r)).tolist() + [None])
                    ys.extend((r * np.cos(lat_r) * np.sin(lon_r)).tolist() + [None])
                    zs.extend((r * np.sin(lat_r)).tolist() + [None])
        print("✅ Coastlines carregadas.")
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

def build_globe_figure(df_filtered, orbit_row=None):
    x_e, y_e, z_e             = _EARTH_SURFACE
    coast_x, coast_y, coast_z = _COASTLINES

    max_range = 50000 if len(df_filtered) == 0 else max(
        df_filtered['X'].abs().max(),
        df_filtered['Y'].abs().max(),
        df_filtered['Z'].abs().max()
    ) * 1.1

    fig = go.Figure()

    fig.add_trace(go.Surface(
        x=x_e, y=y_e, z=z_e,
        colorscale=[[0, '#040b1a'], [1, '#0a1628']],
        showscale=False, opacity=1, hoverinfo='skip',
        lighting=dict(ambient=0.6, diffuse=0.8), name='Terra'
    ))

    # 2. O traço das COSTA/PAÍSES (é aqui que mudas a espessura)
    fig.add_trace(go.Scatter3d(
        x=coast_x, y=coast_y, z=coast_z,
        mode='lines',
        line=dict(
            color='white', # Ou a cor que preferires
            width=5        # Aumenta este valor (ex: de 2 para 5 ou 8) para o traço ficar mais grosso
        ),
        hoverinfo='skip',
        name='Fronteiras'
    ))

    if coast_x is not None:
        fig.add_trace(go.Scatter3d(
            x=coast_x, y=coast_y, z=coast_z,
            mode='lines', line=dict(color='rgba(255,255,255,0.8)', width=1.5),
            hoverinfo='skip', name='Continentes', showlegend=False
        ))

    for obj_type, color in COLOR_MAP.items():
        mask = df_filtered['OBJECT_TYPE'] == obj_type
        if mask.sum() == 0:
            continue
        sub = df_filtered[mask]
        fig.add_trace(go.Scatter3d(
            x=sub['X'], y=sub['Y'], z=sub['Z'],
            mode='markers', name=obj_type,
            marker=dict(size=2, color=color, opacity=0.75),
            customdata=sub[['IDX','NAME','ALTITUDE','ORBIT_TYPE',
                             'CONSTELLATION','INCLINATION','PERIOD',
                             'NORAD_CAT_ID']].values,
            hovertemplate=(
                '<b>%{customdata[1]}</b><br>'
                'Alt: %{customdata[2]:.0f} km | Orbit: %{customdata[3]}<br>'
                'Constelação: %{customdata[4]}<br>'
                'Inclinação: %{customdata[5]:.1f}° | Período: %{customdata[6]:.1f} min'
                '<extra></extra>'
            )
        ))

    # if orbit_row is not None:
    #     try:
    #         ox, oy, oz = compute_orbit_line(orbit_row)
    #         fig.add_trace(go.Scatter3d(
    #             x=ox, y=oy, z=oz, mode='lines',
    #             line=dict(color='white', width=2),
    #             name=f"Órbita: {orbit_row['NAME']}",
    #             hoverinfo='skip', showlegend=True
    #         ))
    #         fig.add_trace(go.Scatter3d(
    #             x=[float(orbit_row['X'])],
    #             y=[float(orbit_row['Y'])],
    #             z=[float(orbit_row['Z'])],
    #             mode='markers',
    #             marker=dict(size=6, color='white', symbol='diamond',
    #                         line=dict(color='yellow', width=2)),
    #             name='Seleccionado',
    #             hovertemplate=f"<b>{orbit_row['NAME']}</b><extra></extra>",
    #             showlegend=True
    #         ))
    #         orbit_max = max(max(abs(v) for v in ox),
    #                         max(abs(v) for v in oy),
    #                         max(abs(v) for v in oz)) * 1.1
    #         max_range = max(max_range, orbit_max)
    #     except Exception as ex:
    #         print(f"Erro ao calcular órbita: {ex}")
    # novo com sgp4
    if orbit_row is not None:
        try:
            # 1. Obter a linha da órbita original (em ECI)
            ox, oy, oz = compute_orbit_line(orbit_row)
            
            # 2. Converter para numpy arrays para facilitar a matemática
            import numpy as np
            from datetime import datetime
            import pandas as pd
            
            ox = np.array(ox)
            oy = np.array(oy)
            oz = np.array(oz)

            # 3. Calcular a Rotação Atual da Terra (o mesmo theta de antes)
            tempo_atual = datetime.utcnow()
            jd_now = pd.Timestamp(tempo_atual).to_julian_date()
            d = jd_now - 2451545.0
            gmst = 280.46061837 + 360.98564736629 * d
            theta = np.radians(gmst % 360)

            # 4. Rodar a Órbita inteira para o sistema ECEF (alinhar com os países e satélites)
            ox_ecef = ox * np.cos(theta) + oy * np.sin(theta)
            oy_ecef = -ox * np.sin(theta) + oy * np.cos(theta)
            oz_ecef = oz  # O Z não precisa de rodar

            # 5. Desenhar a linha da Órbita Rodada
            fig.add_trace(go.Scatter3d(
                x=ox_ecef, y=oy_ecef, z=oz_ecef, mode='lines',
                line=dict(color='white', width=2),
                name=f"Órbita: {orbit_row['NAME']}",
                hoverinfo='skip', showlegend=True
            ))
            
            # 6. Desenhar o Ponto Selecionado (este já vem rodado do dataframe)
            fig.add_trace(go.Scatter3d(
                x=[float(orbit_row['X'])],
                y=[float(orbit_row['Y'])],
                z=[float(orbit_row['Z'])],
                mode='markers',
                marker=dict(size=6, color='white', symbol='diamond',
                            line=dict(color='yellow', width=2)),
                name='Seleccionado',
                hovertemplate=f"<b>{orbit_row['NAME']}</b><extra></extra>",
                showlegend=True
            ))
            
            orbit_max = max(max(abs(v) for v in ox_ecef),
                            max(abs(v) for v in oy_ecef),
                            max(abs(v) for v in oz_ecef)) * 1.1
            max_range = max(max_range, orbit_max)
        except Exception as ex:
            print(f"Erro ao calcular órbita: {ex}")

    invis = dict(
        showbackground=False, showgrid=False, showline=False,
        showticklabels=False, zeroline=False, title='',
        showspikes=False, range=[-max_range, max_range]
    )
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        scene=dict(xaxis=invis, yaxis=invis, zaxis=invis,
                   bgcolor='rgba(0,0,0,0)',
                   aspectmode='manual', aspectratio=dict(x=1, y=1, z=1)),
        legend=dict(x=0.01, y=0.99, font=dict(color='white', size=10),
                    bgcolor='rgba(0,0,0,0.5)', bordercolor='#2d3748'),
        margin=dict(l=0, r=0, t=0, b=0),
        uirevision='constant'
    )
    return fig

# ============================================================
# GRÁFICOS SECUNDÁRIOS
# ============================================================
fig_type_object = go.Figure(data=[go.Pie(
    values=df_3d['OBJECT_TYPE'].value_counts().values,
    labels=df_3d['OBJECT_TYPE'].value_counts().index.tolist(),
    hole=0.65,
    marker_colors=['#00d4ff','#ff6b35','#ffd700','#00ff88'],
    textinfo='percent+label', textposition='inside'
)])
fig_type_object.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    showlegend=False, margin=dict(l=10,r=10,t=20,b=20),
    font=dict(color='white', size=10),
    annotations=[dict(text='Type<br>object', x=0.5, y=0.5,
                      font_size=12, font_color='white', showarrow=False)]
)

top_constellations = df_3d[df_3d['CONSTELLATION'] != 'Other']['CONSTELLATION'].value_counts().head(6)
fig_bar = go.Figure(data=[go.Bar(
    x=top_constellations.index.tolist(), y=top_constellations.values,
    marker_color='#4a6fa5'
)])
fig_bar.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=20,r=20,t=10,b=20),
    xaxis=dict(showgrid=False, color='white', tickfont=dict(size=10)),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white', tickfont=dict(size=10))
)

altitudes = np.sqrt(df_3d['X']**2 + df_3d['Y']**2 + df_3d['Z']**2) - 6371
fig_violin = go.Figure(data=[go.Violin(
    y=altitudes[altitudes < 40000].sample(min(5000, len(altitudes))),
    box_visible=True, line_color='#4a6fa5', fillcolor='#2d4a6f', opacity=0.6
)])
fig_violin.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=35,r=10,t=10,b=10),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white',
               title=dict(text='Altitude (km)', font=dict(size=10))),
    xaxis=dict(showticklabels=False)
)

df_3d['EPOCH_YEAR'] = pd.to_datetime(df_3d['EPOCH'], errors='coerce').dt.year
launches = df_3d.groupby('EPOCH_YEAR').size().reset_index(name='count')
launches = launches[launches['EPOCH_YEAR'] >= 1960]
fig_line = go.Figure(data=[go.Scatter(
    x=launches['EPOCH_YEAR'], y=launches['count'],
    mode='lines+markers', line=dict(color='#4a6fa5', width=2), marker=dict(size=4)
)])
fig_line.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=35,r=20,t=10,b=20),
    xaxis=dict(showgrid=False, color='white', tickfont=dict(size=10)),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white', tickfont=dict(size=10))
)

fig_pct = go.Figure(data=[go.Pie(
    values=[len(df_3d[df_3d['ORBIT_TYPE']=='LEO']),
            len(df_3d)-len(df_3d[df_3d['ORBIT_TYPE']=='LEO'])],
    hole=0.7, marker_colors=['#4a6fa5','#2d3748']
)])
fig_pct.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', showlegend=False,
    margin=dict(l=0,r=0,t=0,b=0),
    annotations=[dict(text='LEO', x=0.5, y=0.5,
                      font_size=11, font_color='white', showarrow=False)]
)

# ============================================================
# ESTILOS
# ============================================================
COLORS = {
    'background': '#0d1421', 'card': '#1a2332',
    'border': '#2d3748',     'text': '#ffffff', 'accent': '#4a6fa5'
}
card_style = {
    'backgroundColor': COLORS['card'], 'borderRadius': '15px',
    'padding': '10px', 'display': 'flex',
    'flexDirection': 'column', 'justifyContent': 'center', 'alignItems': 'center'
}
button_style = {
    'backgroundColor': COLORS['card'], 'color': COLORS['text'],
    'border': 'none', 'borderRadius': '20px',
    'padding': '8px 20px', 'cursor': 'pointer', 'fontSize': '14px'
}

# ============================================================
# FILTROS COLAPSÁVEIS
# ============================================================
filter_groups = [
    {'id': 'orbit',   'label': '🛸 Orbit Type',
     'options': ['LEO','MEO','GEO','HEO'], 'default': ['LEO','MEO','GEO','HEO']},
    {'id': 'constellation', 'label': '🌐 Constellation',
     'options': ['Starlink','OneWeb','Iridium','GPS','GLONASS','Galileo',
                 'BeiDou','COSMOS','FengYun','GOES','NOAA','ISS','Hubble','Other'],
     'default': ['Starlink','OneWeb','Iridium','GPS','GLONASS','Galileo',
                 'BeiDou','COSMOS','FengYun','GOES','NOAA','ISS','Hubble','Other']},
    {'id': 'object_type', 'label': '🔷 Object Type',
     'options': ['Satellite','Debris','Rocket Body','Space Station', 'Component', 'In Analysis', 'Unknown'],
     'default': ['Satellite']},
    {'id': 'altitude', 'label': '📏 Altitude (km)',
     'type': 'range', 'min': 0, 'max': 40000, 'default': [0, 40000]},
    {'id': 'inclination', 'label': '📐 Inclination (°)',
     'type': 'range', 'min': 0, 'max': 180, 'default': [0, 180]},
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
            id=f'filter-{gid}',
            options=[{'label': o, 'value': o} for o in group['options']],
            value=group['default'],
            labelStyle={'display': 'block', 'color': 'white',
                        'fontSize': '12px', 'marginBottom': '4px'},
            inputStyle={'marginRight': '6px', 'accentColor': '#4a6fa5'}
        )
    )
    return html.Div([
        html.Div(id=f'toggle-{gid}', children=[
            html.Span(group['label'], style={'fontSize': '13px', 'fontWeight': 'bold',
                                             'color': 'white', 'flex': '1'}),
            html.Span('▾', id=f'arrow-{gid}', style={'color': '#4a6fa5', 'fontSize': '14px'})
        ], style={'display': 'flex', 'justifyContent': 'space-between',
                  'alignItems': 'center', 'cursor': 'pointer',
                  'padding': '8px 4px', 'borderBottom': '1px solid #2d3748',
                  'userSelect': 'none'}),
        html.Div(id=f'collapse-{gid}', children=[control],
                 style={'padding': '8px 4px 4px 4px', 'display': 'block'})
    ], style={'marginBottom': '4px'})

# ============================================================
# APP — com CSS injectado via index_string
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
            /* ── Slider da janela de conjunções ── */
            #conjunction-days-slider .rc-slider-track {
                background-color: #4a6fa5 !important;
            }
            #conjunction-days-slider .rc-slider-handle {
                border-color: #4a6fa5 !important;
                background-color: #00d4ff !important;
            }
            #conjunction-days-slider .rc-slider-handle:hover,
            #conjunction-days-slider .rc-slider-handle:active {
                border-color: #00d4ff !important;
                box-shadow: 0 0 8px rgba(0, 212, 255, 0.5) !important;
            }
            #conjunction-days-slider .rc-slider-rail {
                background-color: #2d3748 !important;
            }
            #conjunction-days-slider .rc-slider-mark-text {
                color: #6b7280 !important;
                font-size: 11px !important;
            }
            /* ── Paginação da tabela ── */
            .dash-table-container .previous-next-container button {
                background-color: #1a2332 !important;
                color: #4a6fa5 !important;
                border: 1px solid #2d3748 !important;
                border-radius: 6px !important;
                padding: 4px 10px !important;
            }
            .dash-table-container .previous-next-container button:hover {
                background-color: #2d3748 !important;
                color: #00d4ff !important;
            }
            .dash-table-container .page-number {
                color: #9ca3af !important;
            }
            /* ── Scrollbar global ── */
            ::-webkit-scrollbar { width: 6px; }
            ::-webkit-scrollbar-track { background: #0d1421; }
            ::-webkit-scrollbar-thumb { background: #2d3748; border-radius: 3px; }
            ::-webkit-scrollbar-thumb:hover { background: #4a6fa5; }
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
app.layout = html.Div(style={
    'backgroundColor': COLORS['background'],
    'minHeight': '100vh', 'padding': '15px',
    'fontFamily': 'Arial, sans-serif', 'boxSizing': 'border-box'
}, children=[

    dcc.Store(id='selected-object-idx', data=None),
    dcc.Store(id='selected-norad-id',   data=None),

    html.Div(style={
        'display': 'grid',
        'gridTemplateColumns': '1fr 1fr 1.5fr 280px',
        'gridTemplateRows': '220px 80px minmax(450px, 1fr) auto 200px',
        'gap': '15px', 'width': '100%',
    }, children=[

        # ── Linha 1 ──────────────────────────────────────────
        html.Div(style={**card_style, 'gridColumn': '1 / 3', 'gridRow': '1'}, children=[
            dcc.Graph(figure=fig_type_object, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '100%'})
        ]),
        html.Div(style={**card_style, 'gridColumn': '3 / 5', 'gridRow': '1',
                        'justifyContent': 'space-between', 'padding': '15px'}, children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between',
                            'alignItems': 'center', 'width': '100%', 'marginBottom': '10px'}, children=[
                html.Div('TOP CONSTELLATIONS', style={'color': COLORS['text'],
                                                       'fontSize': '14px', 'fontWeight': 'bold'}),
                html.Div(style={'display': 'flex', 'gap': '10px'}, children=[
                    html.Button('orbit',        style=button_style),
                    html.Button('constellation', style={**button_style, 'backgroundColor': '#2d3748'})
                ])
            ]),
            dcc.Graph(figure=fig_bar, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '100%', 'flex': '1'})
        ]),

        # ── Linha 2 — KPIs ───────────────────────────────────
        html.Div(style={**card_style, 'gridColumn': '1', 'gridRow': '2'}, children=[
            html.Div(f'{len(df_3d):,}', style={'color': '#00d4ff', 'fontSize': '26px', 'fontWeight': 'bold'}),
            html.Div('OBJECTS', style={'color': COLORS['text'], 'fontSize': '12px', 'letterSpacing': '1px'})
        ]),
        html.Div(style={**card_style, 'gridColumn': '2', 'gridRow': '2'}, children=[
            dcc.Graph(figure=fig_pct, config={'displayModeBar': False},
                      style={'width': '70px', 'height': '70px'})
        ]),

        # ── Linha 3 — Globo 3D ───────────────────────────────
        html.Div(id='globe-container', style={
            **card_style, 'gridColumn': '1 / 4', 'gridRow': '3',
            'position': 'relative', 'padding': '0'
        }, children=[
            dcc.Graph(
                id='globe-3d',
                figure=build_globe_figure(df_3d),
                config={'displayModeBar': True,
                        'modeBarButtonsToRemove': ['toImage'],
                        'scrollZoom': True},
                style={'width': '100%', 'height': '100%'},
                clear_on_unhover=True
            )
        ]),

        # ── Filtros (coluna direita) ──────────────────────────
        html.Div(style={
            **card_style, 'gridColumn': '4', 'gridRow': '2 / 6',
            'justifyContent': 'flex-start', 'alignItems': 'stretch',
            'padding': '15px', 'overflowY': 'auto'
        }, children=[
            html.Div('▼ FILTERS', style={
                'color': COLORS['text'], 'fontSize': '15px', 'fontWeight': 'bold',
                'marginBottom': '15px', 'borderBottom': '1px solid #4a6fa5',
                'paddingBottom': '10px'
            }),
            *[make_filter_section(g) for g in filter_groups],
            html.Button('Apply Filters', id='apply-filters', n_clicks=0,
                        style={**button_style, 'marginTop': 'auto', 'width': '100%',
                               'backgroundColor': '#4a6fa5', 'fontWeight': 'bold',
                               'padding': '12px'})
        ]),

        # ── Linha 4 — Info satélite ───────────────────────────
        html.Div(id='selected-info', style={
            **card_style, 'gridColumn': '1 / 4', 'gridRow': '4',
            'minHeight': '70px', 'padding': '10px 20px',
            'flexDirection': 'row', 'justifyContent': 'flex-start',
            'alignItems': 'center', 'gap': '30px', 'flexWrap': 'wrap'
        }, children=[
            html.Div('Clica num objecto no globo para ver a sua órbita',
                     style={'color': '#6b7280', 'fontSize': '14px', 'fontStyle': 'italic'})
        ]),

        # ── Linha 5 — Gráficos inferiores ────────────────────
        html.Div(style={**card_style, 'gridColumn': '1', 'gridRow': '5', 'padding': '15px'}, children=[
            html.Div(style={'textAlign': 'center', 'marginBottom': '5px'}, children=[
                html.Div('ALTITUDE', style={'color': COLORS['text'], 'fontSize': '12px', 'fontWeight': 'bold'}),
                html.Div('DENSITY',  style={'color': COLORS['text'], 'fontSize': '12px', 'fontWeight': 'bold'}),
            ]),
            dcc.Graph(figure=fig_violin, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '100%', 'flex': '1'})
        ]),
        html.Div(style={**card_style, 'gridColumn': '2 / 4', 'gridRow': '5', 'padding': '15px'}, children=[
            html.Div('CATALOG ENTRIES / YEAR', style={'color': COLORS['text'],
                                                       'fontSize': '13px', 'fontWeight': 'bold',
                                                       'marginBottom': '10px'}),
            dcc.Graph(figure=fig_line, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '100%', 'flex': '1'})
        ]),
    ]),

    # ============================================================
    # MODAL DE CONJUNÇÕES
    # ============================================================
    html.Div(id='conjunction-modal', style={
        'display': 'none',
        'position': 'fixed', 'top': '0', 'left': '0',
        'width': '100vw', 'height': '100vh',
        'backgroundColor': 'rgba(0,0,0,0.85)', 'zIndex': '9999',
        'justifyContent': 'center', 'alignItems': 'center'
    }, children=[
        html.Div(style={
            **card_style,
            'width': '800px', 'maxHeight': '85vh',
            'position': 'relative', 'padding': '25px',
            'justifyContent': 'flex-start', 'alignItems': 'stretch',
            'border': '1px solid #2d3748',
        }, children=[

            # Botão fechar
            html.Button('✖', id='close-modal-btn', n_clicks=0, style={
                'position': 'absolute', 'top': '15px', 'right': '15px',
                'background': 'none', 'border': 'none',
                'color': '#9ca3af', 'fontSize': '18px', 'cursor': 'pointer',
            }),

            # Título
            html.H3(id='modal-title', children='Análise de Conjunções', style={
                'color': '#00d4ff', 'marginTop': '0', 'marginBottom': '20px',
                'fontSize': '18px', 'fontWeight': 'bold', 'letterSpacing': '0.5px',
            }),

            # Slider
            html.Div(style={'width': '100%', 'marginBottom': '28px'}, children=[
                html.Span('Janela de Tempo (Dias):', style={
                    'color': '#9ca3af', 'fontSize': '12px',
                    'letterSpacing': '1px', 'textTransform': 'uppercase',
                    'marginBottom': '12px', 'display': 'block'
                }),
                dcc.Slider(
                    id='conjunction-days-slider', min=1, max=20, step=1, value=7,
                    marks={i: dict(label=str(i), style={'color': '#6b7280', 'fontSize': '11px'})
                           for i in range(1, 21, 2)},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ]),

            # Tabela
            dcc.Loading(color='#00d4ff', type='circle', children=[
                dash_table.DataTable(
                    id='conjunction-table',
                    columns=[
                        {'name': 'Objeto Espacial',  'id': 'NAME'},
                        {'name': 'NORAD ID',         'id': 'NORAD_ID'},
                        {'name': 'Dist. Mín. (km)',  'id': 'MIN_DIST_KM'},
                        {'name': 'Data/Hora (UTC)',   'id': 'TIME_UTC'},
                    ],
                    data=[],
                    page_size=7,
                    style_table={
                        'borderRadius': '8px',
                        'overflow': 'hidden',
                        'width': '100%',
                        'border': '1px solid #2d3748',
                    },
                    style_header={
                        'backgroundColor': '#0d1421',
                        'color': '#4a6fa5',
                        'fontWeight': 'bold',
                        'textAlign': 'left',
                        'border': 'none',
                        'borderBottom': '2px solid #2d3748',
                        'fontSize': '12px',
                        'letterSpacing': '1px',
                        'textTransform': 'uppercase',
                        'padding': '12px 14px',
                    },
                    style_cell={
                        'backgroundColor': '#1a2332',
                        'color': '#e2e8f0',
                        'textAlign': 'left',
                        'border': 'none',
                        'borderBottom': '1px solid #2d3748',
                        'padding': '10px 14px',
                        'fontSize': '13px',
                        'overflow': 'hidden',
                        'textOverflow': 'ellipsis',
                        'maxWidth': '0',
                    },
                    style_cell_conditional=[
                        {'if': {'column_id': 'NAME'},        'width': '38%'},
                        {'if': {'column_id': 'NORAD_ID'},    'width': '14%'},
                        {'if': {'column_id': 'MIN_DIST_KM'}, 'width': '22%'},
                        {'if': {'column_id': 'TIME_UTC'},    'width': '26%'},
                    ],
                    style_data_conditional=[
                        # Linhas alternadas
                        {'if': {'row_index': 'odd'},
                         'backgroundColor': '#162030'},
                        # Risco alto < 10 km — laranja
                        {'if': {'filter_query': '{MIN_DIST_KM} < 10'},
                         'backgroundColor': 'rgba(255,107,53,0.20)',
                         'color': '#ff6b35', 'fontWeight': 'bold'},
                        # Risco médio 10–100 km — amarelo subtil
                        {'if': {'filter_query': '{MIN_DIST_KM} >= 10 && {MIN_DIST_KM} < 100'},
                         'backgroundColor': 'rgba(255,215,0,0.08)',
                         'color': '#ffd700'},
                        # Célula activa
                        {'if': {'state': 'active'},
                         'backgroundColor': '#2d3748',
                         'border': '1px solid #4a6fa5'},
                    ],
                    style_as_list_view=True,
                )
            ])
        ])
    ])
])

# ============================================================
# CALLBACKS — Filtros colapsáveis
# ============================================================
for group in filter_groups:
    gid = group['id']
    @app.callback(
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

# ============================================================
# CALLBACK — Capturar click no globo
# ============================================================
@app.callback(
    Output('selected-object-idx', 'data'),
    Output('selected-norad-id',   'data'),
    Input('globe-3d', 'clickData'),
    prevent_initial_call=True
)
def store_click(click_data):
    if click_data is None:
        return None, None
    try:
        pt = click_data['points'][0]
        cd = pt.get('customdata')
        if cd is not None:
            return int(cd[0]), int(cd[7])
    except Exception as ex:
        print(f"store_click error: {ex}")
    return None, None

# ============================================================
# CALLBACK — Actualizar globo + info bar
# ============================================================
@app.callback(
    Output('globe-3d',      'figure'),
    Output('selected-info', 'children'),
    Input('apply-filters',        'n_clicks'),
    Input('selected-object-idx',  'data'),
    State('filter-orbit',         'value'),
    State('filter-constellation', 'value'),
    State('filter-object_type',   'value'),
    State('filter-altitude',      'value'),
    State('filter-inclination',   'value'),
    prevent_initial_call=False
)
def update_globe(n_clicks, selected_idx,
                 orbit_vals, const_vals, obj_type_vals, alt_range, inc_range):
    df_f = df_3d.copy()
    if orbit_vals:    df_f = df_f[df_f['ORBIT_TYPE'].isin(orbit_vals)]
    if const_vals:    df_f = df_f[df_f['CONSTELLATION'].isin(const_vals)]
    if obj_type_vals: df_f = df_f[df_f['OBJECT_TYPE'].isin(obj_type_vals)]
    if alt_range:     df_f = df_f[(df_f['ALTITUDE'] >= alt_range[0]) & (df_f['ALTITUDE'] <= alt_range[1])]
    if inc_range:     df_f = df_f[(df_f['INCLINATION'] >= inc_range[0]) & (df_f['INCLINATION'] <= inc_range[1])]

    orbit_row     = None
    info_children = [html.Div('Clica num objecto no globo para ver a sua órbita',
                              style={'color': '#6b7280', 'fontSize': '13px', 'fontStyle': 'italic'})]

    if selected_idx is not None and selected_idx in df_3d.index:
        orbit_row = df_3d.loc[selected_idx]

        def kpi(label, value):
            return html.Div([
                html.Div(value, style={'color': '#00d4ff', 'fontSize': '15px', 'fontWeight': 'bold'}),
                html.Div(label, style={'color': '#9ca3af', 'fontSize': '11px'})
            ], style={'textAlign': 'center', 'minWidth': '80px'})

        info_children = [
            html.Div(orbit_row['NAME'],
                     style={'color': 'white', 'fontSize': '14px', 'fontWeight': 'bold',
                            'marginRight': '20px', 'alignSelf': 'center'}),
            kpi('Altitude',    f"{orbit_row['ALTITUDE']:.0f} km"),
            kpi('Órbita',      orbit_row['ORBIT_TYPE']),
            kpi('Inclinação',  f"{orbit_row['INCLINATION']:.1f}°"),
            kpi('Período',     f"{orbit_row['PERIOD']:.1f} min"),
            kpi('Constelação', orbit_row['CONSTELLATION']),
            kpi('NORAD ID',    str(int(orbit_row['NORAD_CAT_ID']))),
            html.Button('🔍 Conjunctions', id='check-conjunctions-btn', n_clicks=0,
                        style={**button_style, 'backgroundColor': '#4a6fa5',
                               'marginLeft': 'auto', 'alignSelf': 'center',
                               'fontWeight': 'bold'})
        ]

    return build_globe_figure(df_f, orbit_row=orbit_row), info_children

# ============================================================
# CALLBACK — Abrir / fechar modal
# ============================================================
@app.callback(
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

# ============================================================
# CALLBACK — Calcular tabela de conjunções
# ============================================================
@app.callback(
    Output('conjunction-table', 'data'),
    Input('check-conjunctions-btn',  'n_clicks'),
    Input('conjunction-days-slider', 'value'),
    State('selected-norad-id',       'data'),
    prevent_initial_call=True
)
def update_conjunction_table(open_clicks, days, norad_id):
    if not open_clicks or open_clicks < 1:
        return dash.no_update
    if norad_id is None:
        return []
    try:
        df_result = run_live_conjunction_analysis(
            target_norad_id = int(norad_id),
            tle_dataframe   = tle,
            days            = int(days),
            step_minutes    = 15.0,
            top_n           = 10,
            buffer_km       = 75.0,
        )
        return [] if df_result.empty else df_result.to_dict('records')
    except Exception as ex:
        print(f"❌ Erro conjunction analysis: {ex}")
        import traceback; traceback.print_exc()
        return []

# ============================================================
# EXECUTAR
# ============================================================
if __name__ == '__main__':
    app.run(debug=True)