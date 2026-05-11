import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import json
import plotly
import os
from urllib.request import urlopen

# ============================================================
# CARREGAR E PREPARAR DADOS
# ============================================================
path = '.'
# Nota: Certifica-te que o ficheiro existe no caminho indicado
tle = pd.read_csv(f'{path}/../DATASETS_SATTELITES/spacetrack_last_data_tle.csv')

def prepare_3d_data(df):
    mu = 398600.4418

    inc    = np.radians(df['INCLINATION'])
    raan   = np.radians(df['RA_OF_ASC_NODE'])
    arg_p  = np.radians(df['ARG_OF_PERICENTER'])
    m_anom = np.radians(df['MEAN_ANOMALY'])
    e      = df['ECCENTRICITY']

    period_sec = df['PERIOD'] * 60
    # Filtrar períodos inválidos antes de calcular
    valid = (period_sec > 0) & (e < 1) & (e >= 0)
    df = df[valid].copy()

    period_sec = df['PERIOD'] * 60
    e          = df['ECCENTRICITY']
    inc        = np.radians(df['INCLINATION'])
    raan       = np.radians(df['RA_OF_ASC_NODE'])
    arg_p      = np.radians(df['ARG_OF_PERICENTER'])
    m_anom     = np.radians(df['MEAN_ANOMALY'])

    a = ((period_sec * np.sqrt(mu)) / (2 * np.pi))**(2/3)

    x_orb = a * (np.cos(m_anom) - e)
    y_orb = a * (np.sqrt(1 - e**2) * np.sin(m_anom))

    cos_raan, sin_raan = np.cos(raan), np.sin(raan)
    cos_argp, sin_argp = np.cos(arg_p), np.sin(arg_p)
    cos_inc,  sin_inc  = np.cos(inc),   np.sin(inc)

    df['X'] = (cos_raan*cos_argp - sin_raan*sin_argp*cos_inc)*x_orb + \
              (-cos_raan*sin_argp - sin_raan*cos_argp*cos_inc)*y_orb
    df['Y'] = (sin_raan*cos_argp + cos_raan*sin_argp*cos_inc)*x_orb + \
              (-sin_raan*sin_argp + cos_raan*cos_argp*cos_inc)*y_orb
    df['Z'] = (sin_argp*sin_inc)*x_orb + (cos_argp*sin_inc)*y_orb

    # Remover NaN/Inf que possam surgir de dados corrompidos
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=['X','Y','Z'])

    # Classificação de órbita
    df['ORBIT_TYPE'] = pd.cut(
        df['PERIOD'],
        bins=[0, 128, 600, 1500, 99999],
        labels=['LEO', 'MEO', 'GEO', 'HEO']
    ).astype(str)

    # Tipo de objeto
    name_upper = df['OBJECT_NAME'].str.upper()
    conditions = [
        name_upper.str.contains('DEB|DEBRIS', na=False),
        name_upper.str.contains(r'R/B|ROCKET', na=False),
        name_upper.str.contains('ISS|STATION', na=False),
    ]
    choices = ['Debris', 'Rocket Body', 'Space Station']
    df['OBJECT_TYPE'] = np.select(conditions, choices, default='Satellite')

    # Constelação
    constellation_map = {
        'STARLINK': 'Starlink', 'ONEWEB': 'OneWeb', 'IRIDIUM': 'Iridium',
        'GPS': 'GPS', 'GLONASS': 'GLONASS', 'GALILEO': 'Galileo',
        'BEIDOU': 'BeiDou', 'COSMOS': 'COSMOS', 'FENGYUN': 'FengYun',
        'GOES': 'GOES', 'NOAA': 'NOAA', 'ISS': 'ISS', 'HUBBLE': 'Hubble',
    }
    df['CONSTELLATION'] = 'Other'
    for key, val in constellation_map.items():
        mask = name_upper.str.contains(key, na=False) & (df['CONSTELLATION'] == 'Other')
        df.loc[mask, 'CONSTELLATION'] = val

    df['ALTITUDE'] = (np.sqrt(df['X']**2 + df['Y']**2 + df['Z']**2) - 6371).round(0)

    # Índice numérico para identificar o objeto no click
    df = df.reset_index(drop=True)
    df['IDX'] = df.index

    return df

df_3d = prepare_3d_data(tle)
print(f"✅ Objetos carregados: {len(df_3d):,}")

# ============================================================
# ÓRBITA COMPLETA (Kepler — true anomaly sweep)
# ============================================================
def compute_orbit_line(row, n_points=300):
    mu = 398600.4418
    period_sec = float(row['PERIOD']) * 60
    a    = ((period_sec * np.sqrt(mu)) / (2 * np.pi))**(2/3)
    e    = float(row['ECCENTRICITY'])
    inc  = np.radians(float(row['INCLINATION']))
    raan = np.radians(float(row['RA_OF_ASC_NODE']))
    argp = np.radians(float(row['ARG_OF_PERICENTER']))

    nu = np.linspace(0, 2 * np.pi, n_points)
    r  = a * (1 - e**2) / (1 + e * np.cos(nu))

    x_o = r * np.cos(nu)
    y_o = r * np.sin(nu)

    cos_raan, sin_raan = np.cos(raan), np.sin(raan)
    cos_argp, sin_argp = np.cos(argp), np.sin(argp)
    cos_inc,  sin_inc  = np.cos(inc),   np.sin(inc)

    Xo = (cos_raan*cos_argp - sin_raan*sin_argp*cos_inc)*x_o + \
         (-cos_raan*sin_argp - sin_raan*cos_argp*cos_inc)*y_o
    Yo = (sin_raan*cos_argp + cos_raan*sin_argp*cos_inc)*x_o + \
         (-sin_raan*sin_argp + cos_raan*cos_argp*cos_inc)*y_o
    Zo = (sin_argp*sin_inc)*x_o + (cos_argp*sin_inc)*y_o

    return Xo.tolist(), Yo.tolist(), Zo.tolist()

# ============================================================
# GLOBO 3D (REFORMULADO)
# ============================================================
def build_earth_surface():
    phi   = np.linspace(0, 2*np.pi, 180)
    theta = np.linspace(0, np.pi, 90)
    x_e = 6371 * np.outer(np.cos(phi), np.sin(theta))
    y_e = 6371 * np.outer(np.sin(phi), np.sin(theta))
    z_e = 6371 * np.outer(np.ones(np.size(phi)), np.cos(theta))
    return x_e, y_e, z_e

def build_coastlines():
    """
    Forma melhorada: Carrega GeoJSON via URL para garantir que as 
    fronteiras aparecem de forma limpa e independente do sistema local.
    """
    try:
        url = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json"
        with urlopen(url) as response:
            geo_data = json.loads(response.read().decode())
        
        xs, ys, zs = [], [], []
        r = 6372.0 # Ligeiramente acima da superfície para evitar flicker

        for feature in geo_data['features']:
            coords = feature['geometry']['coordinates']
            # O GeoJSON pode ter Polygon ou MultiPolygon
            parts = coords if feature['geometry']['type'] == 'MultiPolygon' else [coords]
            
            for part in parts:
                for poly in part:
                    lons = [p[0] for p in poly]
                    lats = [p[1] for p in poly]
                    
                    lat_r = np.radians(lats)
                    lon_r = np.radians(lons)
                    
                    xs.extend((r * np.cos(lat_r) * np.cos(lon_r)).tolist() + [None])
                    ys.extend((r * np.cos(lat_r) * np.sin(lon_r)).tolist() + [None])
                    zs.extend((r * np.sin(lat_r)).tolist() + [None])
        
        print("[OK] Continentes carregados via GeoJSON")
        return xs, ys, zs
    except Exception as e:
        print(f"[ERRO] build_coastlines: {e}")
        return None, None, None

# Pré-computar superfície e costas
_EARTH_SURFACE = build_earth_surface()
_COASTLINES    = build_coastlines()

COLOR_MAP = {
    'Satellite':     '#00d4ff',
    'Debris':        '#ff6b35',
    'Rocket Body':   '#ffd700',
    'Space Station': '#00ff88',
}

def build_globe_figure(df_filtered, orbit_row=None):
    x_e, y_e, z_e = _EARTH_SURFACE
    coast_x, coast_y, coast_z = _COASTLINES

    if len(df_filtered) == 0:
        max_range = 50000
    else:
        max_range = max(
            df_filtered['X'].abs().max(),
            df_filtered['Y'].abs().max(),
            df_filtered['Z'].abs().max()
        ) * 1.1

    fig = go.Figure()

    # Terra (Efeito Deep Blue)
    fig.add_trace(go.Surface(
        x=x_e, y=y_e, z=z_e,
        colorscale=[[0, '#040b1a'], [1, '#0a1628']],
        showscale=False, opacity=1, hoverinfo='skip',
        lighting=dict(ambient=0.6, diffuse=0.8),
        name='Terra'
    ))

    # Costas (Linhas Estilo Digital)
    if coast_x is not None:
        fig.add_trace(go.Scatter3d(
            x=coast_x, y=coast_y, z=coast_z,
            mode='lines',
            line=dict(color='rgba(0, 212, 255, 0.4)', width=1.5),
            hoverinfo='skip', name='Continentes', showlegend=False
        ))

    # Satélites
    for obj_type, color in COLOR_MAP.items():
        mask = df_filtered['OBJECT_TYPE'] == obj_type
        if mask.sum() == 0:
            continue
        sub = df_filtered[mask]
        fig.add_trace(go.Scatter3d(
            x=sub['X'], y=sub['Y'], z=sub['Z'],
            mode='markers',
            name=obj_type,
            marker=dict(size=2, color=color, opacity=0.75),
            customdata=sub[['IDX', 'OBJECT_NAME', 'ALTITUDE', 'ORBIT_TYPE',
                             'CONSTELLATION', 'INCLINATION', 'PERIOD']].values,
            hovertemplate=(
                '<b>%{customdata[1]}</b><br>'
                'Alt: %{customdata[2]:.0f} km<br>'
                'Orbit: %{customdata[3]}<br>'
                'Constelação: %{customdata[4]}<br>'
                'Inclinação: %{customdata[5]:.1f}°<br>'
                'Período: %{customdata[6]:.1f} min'
                '<extra></extra>'
            )
        ))

    # Órbita do objecto seleccionado
    if orbit_row is not None:
        try:
            ox, oy, oz = compute_orbit_line(orbit_row)
            ox.append(ox[0]); oy.append(oy[0]); oz.append(oz[0])
            fig.add_trace(go.Scatter3d(
                x=ox, y=oy, z=oz,
                mode='lines',
                line=dict(color='white', width=2),
                name=f"Órbita: {orbit_row['OBJECT_NAME']}",
                hoverinfo='skip',
                showlegend=True
            ))
            fig.add_trace(go.Scatter3d(
                x=[float(orbit_row['X'])],
                y=[float(orbit_row['Y'])],
                z=[float(orbit_row['Z'])],
                mode='markers',
                marker=dict(size=6, color='white',
                            symbol='diamond',
                            line=dict(color='yellow', width=2)),
                name='Seleccionado',
                hovertemplate=f"<b>{orbit_row['OBJECT_NAME']}</b><extra></extra>",
                showlegend=True
            ))
            orbit_max = max(max(abs(x) for x in ox),
                            max(abs(y) for y in oy),
                            max(abs(z) for z in oz)) * 1.1
            max_range = max(max_range, orbit_max)
        except Exception as ex:
            print(f"Erro ao calcular órbita: {ex}")

    # Configuração de eixo "fantasma" absoluto
    invisible_axis = dict(
        showbackground=False,
        showgrid=False,
        showline=False,
        showticklabels=False,
        zeroline=False,
        title='',
        showspikes=False,          # 1. Desliga o motor de linhas
        spikesides=False,          # 2. Desliga as projecções nas paredes
        spikethickness=0,          # 3. Força a espessura da linha a zero
        spikecolor='rgba(0,0,0,0)',# 4. Força a cor a ser 100% transparente
        range=[-max_range, max_range]
    )

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        scene=dict(
            xaxis=invisible_axis,
            yaxis=invisible_axis,
            zaxis=invisible_axis,
            bgcolor='rgba(0,0,0,0)',
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=1),
        ),
        legend=dict(
            x=0.01, y=0.99,
            font=dict(color='white', size=10),
            bgcolor='rgba(0,0,0,0.5)',
            bordercolor='#2d3748'
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        uirevision='constant'
    )
    
    return fig

# ============================================================
# OUTROS GRÁFICOS (MANTIDOS)
# ============================================================
fig_type_object = go.Figure(data=[go.Pie(
    values=df_3d['OBJECT_TYPE'].value_counts().values,
    labels=df_3d['OBJECT_TYPE'].value_counts().index.tolist(),
    hole=0.6,
    marker_colors=['#00d4ff', '#ff6b35', '#ffd700', '#00ff88']
)])
fig_type_object.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    showlegend=False, margin=dict(l=10, r=10, t=10, b=10),
    font=dict(color='white'),
    annotations=[dict(text='Type<br>object', x=0.5, y=0.5,
                      font_size=12, font_color='white', showarrow=False)]
)

top_constellations = df_3d[df_3d['CONSTELLATION'] != 'Other']['CONSTELLATION'].value_counts().head(6)
fig_bar_country = go.Figure(data=[go.Bar(
    x=top_constellations.index.tolist(),
    y=top_constellations.values,
    marker_color='#4a6fa5'
)])
fig_bar_country.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=20, r=20, t=20, b=40),
    xaxis=dict(showgrid=False, color='white', tickfont=dict(size=9)),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white')
)

altitudes = np.sqrt(df_3d['X']**2 + df_3d['Y']**2 + df_3d['Z']**2) - 6371
fig_violin = go.Figure(data=[go.Violin(
    y=altitudes[altitudes < 40000].sample(min(5000, len(altitudes))),
    box_visible=True,
    line_color='#4a6fa5', fillcolor='#2d4a6f', opacity=0.6
)])
fig_violin.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=20, r=20, t=20, b=20),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white',
               title=dict(text='Altitude (km)', font=dict(size=10))),
    xaxis=dict(showticklabels=False)
)

df_3d['EPOCH_YEAR'] = pd.to_datetime(df_3d['EPOCH'], errors='coerce').dt.year
launches_per_year = df_3d.groupby('EPOCH_YEAR').size().reset_index(name='count')
launches_per_year = launches_per_year[launches_per_year['EPOCH_YEAR'] >= 1960]
fig_line_year = go.Figure(data=[go.Scatter(
    x=launches_per_year['EPOCH_YEAR'],
    y=launches_per_year['count'],
    mode='lines+markers',
    line=dict(color='#4a6fa5', width=2),
    marker=dict(size=4)
)])
fig_line_year.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=30, r=20, t=20, b=40),
    xaxis=dict(showgrid=False, color='white'),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white')
)

fig_percentage = go.Figure(data=[go.Pie(
    values=[len(df_3d[df_3d['ORBIT_TYPE']=='LEO']),
            len(df_3d)-len(df_3d[df_3d['ORBIT_TYPE']=='LEO'])],
    hole=0.7,
    marker_colors=['#4a6fa5', '#2d3748']
)])
fig_percentage.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', showlegend=False,
    margin=dict(l=5, r=5, t=5, b=5),
    annotations=[dict(text='LEO', x=0.5, y=0.5,
                      font_size=10, font_color='white', showarrow=False)]
)

# ============================================================
# ESTILOS E FILTROS (MANTIDOS)
# ============================================================
COLORS = {
    'background': '#0d1421', 'card': '#1a2332',
    'border': '#2d3748', 'text': '#ffffff', 'accent': '#4a6fa5'
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

filter_groups = [
    {'id': 'orbit',   'label': '🛸 Orbit Type',
     'options': ['LEO','MEO','GEO','HEO'],
     'default': ['LEO','MEO','GEO','HEO']},
    {'id': 'constellation', 'label': '🌐 Constellation',
     'options': ['Starlink','OneWeb','Iridium','GPS','GLONASS',
                 'Galileo','BeiDou','COSMOS','FengYun','GOES',
                 'NOAA','ISS','Hubble','Other'],
     'default': ['Starlink','OneWeb','Iridium','GPS','GLONASS',
                 'Galileo','BeiDou','COSMOS','FengYun','GOES',
                 'NOAA','ISS','Hubble','Other']},
    {'id': 'object_type', 'label': '🔷 Object Type',
     'options': ['Satellite','Debris','Rocket Body','Space Station'],
     'default': ['Satellite','Debris','Rocket Body','Space Station']},
    {'id': 'altitude', 'label': '📏 Altitude Range (km)',
     'type': 'range', 'min': 0, 'max': 40000, 'default': [0, 40000]},
    {'id': 'inclination', 'label': '📐 Inclination (°)',
     'type': 'range', 'min': 0, 'max': 180, 'default': [0, 180]},
]

def make_filter_section(group):
    gid      = group['id']
    label    = group['label']
    is_range = group.get('type') == 'range'

    if is_range:
        control = dcc.RangeSlider(
            id=f'filter-{gid}',
            min=group['min'], max=group['max'],
            value=group['default'],
            step=max(1, group['max'] // 100),
            marks={group['min']: str(group['min']),
                   group['max']: str(group['max'])},
            tooltip={"placement": "bottom", "always_visible": False}
        )
    else:
        control = dcc.Checklist(
            id=f'filter-{gid}',
            options=[{'label': o, 'value': o} for o in group['options']],
            value=group['default'],
            labelStyle={'display': 'block', 'color': 'white',
                        'fontSize': '12px', 'marginBottom': '4px'},
            inputStyle={'marginRight': '6px', 'accentColor': '#4a6fa5'}
        )

    return html.Div([
        html.Div(id=f'toggle-{gid}', children=[
            html.Span(label, style={'fontSize': '13px', 'fontWeight': 'bold',
                                    'color': 'white', 'flex': '1'}),
            html.Span('▾', id=f'arrow-{gid}',
                      style={'color': '#4a6fa5', 'fontSize': '14px'})
        ], style={
            'display': 'flex', 'justifyContent': 'space-between',
            'alignItems': 'center', 'cursor': 'pointer',
            'padding': '8px 4px', 'borderBottom': '1px solid #2d3748',
            'userSelect': 'none'
        }),
        html.Div(id=f'collapse-{gid}', children=[control],
                 style={'padding': '8px 4px 4px 4px', 'display': 'block'})
    ], style={'marginBottom': '4px'})

# ============================================================
# APP E LAYOUT (MANTIDOS)
# ============================================================
app = dash.Dash(__name__, suppress_callback_exceptions=True)

app.layout = html.Div(style={
    'backgroundColor': COLORS['background'],
    'minHeight': '100vh', 'padding': '15px',
    'fontFamily': 'Arial, sans-serif'
}, children=[
    dcc.Store(id='selected-object-idx', data=None),
    dcc.Store(id='filtered-indices', data=None),

    html.Div(style={
        'display': 'grid',
        'gridTemplateColumns': '1fr 1fr 1.5fr 1fr',
        'gridTemplateRows': 'auto auto auto auto auto',
        'gap': '15px',
        'maxWidth': '1100px',
        'margin': '0 auto'
    }, children=[
        html.Div(style={**card_style, 'gridColumn': '1 / 3', 'gridRow': '1', 'height': '180px'}, children=[
            dcc.Graph(figure=fig_type_object, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '100%'})
        ]),
        html.Div(style={**card_style, 'gridColumn': '3 / 5', 'gridRow': '1', 'height': '180px'}, children=[
            html.Div(style={'display': 'flex', 'gap': '10px', 'marginBottom': '6px'}, children=[
                html.Button('orbit', style=button_style),
                html.Button('constellation', style={**button_style, 'backgroundColor': '#2d3748'})
            ]),
            html.Div('TOP CONSTELLATIONS', style={'color': COLORS['text'], 'fontSize': '13px', 'fontWeight': 'bold'}),
            dcc.Graph(figure=fig_bar_country, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '90px'})
        ]),

        html.Div(style={**card_style, 'gridColumn': '1', 'gridRow': '2', 'height': '70px'}, children=[
            html.Div(f'{len(df_3d):,}', style={'color': '#00d4ff', 'fontSize': '22px', 'fontWeight': 'bold'}),
            html.Div('OBJECTS', style={'color': COLORS['text'], 'fontSize': '12px'})
        ]),
        html.Div(style={**card_style, 'gridColumn': '2', 'gridRow': '2', 'height': '70px'}, children=[
            dcc.Graph(figure=fig_percentage, config={'displayModeBar': False},
                      style={'width': '65px', 'height': '65px'})
        ]),

        html.Div(id='globe-container', style={
            **card_style,
            'gridColumn': '1 / 4', 'gridRow': '3 / 4',
            'height': '400px', 'position': 'relative', 'padding': '0'
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

        html.Div(style={
            **card_style,
            'gridColumn': '4', 'gridRow': '2 / 5',
            'justifyContent': 'flex-start', 'alignItems': 'stretch',
            'padding': '12px', 'overflowY': 'auto', 'maxHeight': '640px'
        }, children=[
            html.Div('▼ FILTERS', style={
                'color': COLORS['text'], 'fontSize': '15px', 'fontWeight': 'bold',
                'marginBottom': '10px', 'borderBottom': '1px solid #4a6fa5',
                'paddingBottom': '6px'
            }),
            *[make_filter_section(g) for g in filter_groups],
            html.Button('Apply Filters', id='apply-filters', n_clicks=0,
                        style={**button_style, 'marginTop': '12px', 'width': '100%',
                               'backgroundColor': '#4a6fa5', 'fontWeight': 'bold'})
        ]),

        html.Div(id='selected-info', style={
            **card_style,
            'gridColumn': '1 / 4', 'gridRow': '4',
            'minHeight': '50px', 'padding': '10px 16px',
            'flexDirection': 'row', 'justifyContent': 'flex-start',
            'gap': '30px', 'flexWrap': 'wrap'
        }, children=[
            html.Div('Clica num objecto no globo para ver a sua órbita',
                     style={'color': '#6b7280', 'fontSize': '13px', 'fontStyle': 'italic'})
        ]),

        html.Div(style={**card_style, 'gridColumn': '1', 'gridRow': '5', 'height': '150px'}, children=[
            html.Div('ALTITUDE', style={'color': COLORS['text'], 'fontSize': '12px', 'fontWeight': 'bold'}),
            html.Div('DENSITY', style={'color': COLORS['text'], 'fontSize': '12px', 'fontWeight': 'bold'}),
            dcc.Graph(figure=fig_violin, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '100px'})
        ]),
        html.Div(style={**card_style, 'gridColumn': '2 / 4', 'gridRow': '5', 'height': '150px'}, children=[
            html.Div('CATALOG ENTRIES / YEAR', style={'color': COLORS['text'], 'fontSize': '13px', 'fontWeight': 'bold'}),
            dcc.Graph(figure=fig_line_year, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '100px'})
        ]),
    ])
])

# ============================================================
# CALLBACKS (MANTIDOS)
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

@app.callback(
    Output('selected-object-idx', 'data'),
    Input('globe-3d', 'clickData'),
    prevent_initial_call=True
)
def store_click(click_data):
    if click_data is None: return None
    try:
        pt = click_data['points'][0]
        cd = pt.get('customdata')
        if cd is not None: return int(cd[0])
    except Exception: pass
    return None

@app.callback(
    Output('globe-3d', 'figure'),
    Output('selected-info', 'children'),
    Input('apply-filters', 'n_clicks'),
    Input('selected-object-idx', 'data'),
    State('filter-orbit', 'value'),
    State('filter-constellation', 'value'),
    State('filter-object_type', 'value'),
    State('filter-altitude', 'value'),
    State('filter-inclination', 'value'),
    prevent_initial_call=False
)
def update_globe(n_clicks, selected_idx, orbit_vals, const_vals, obj_type_vals, alt_range, inc_range):
    df_f = df_3d.copy()
    if orbit_vals: df_f = df_f[df_f['ORBIT_TYPE'].isin(orbit_vals)]
    if const_vals: df_f = df_f[df_f['CONSTELLATION'].isin(const_vals)]
    if obj_type_vals: df_f = df_f[df_f['OBJECT_TYPE'].isin(obj_type_vals)]
    if alt_range: df_f = df_f[(df_f['ALTITUDE'] >= alt_range[0]) & (df_f['ALTITUDE'] <= alt_range[1])]
    if inc_range: df_f = df_f[(df_f['INCLINATION'] >= inc_range[0]) & (df_f['INCLINATION'] <= inc_range[1])]

    orbit_row = None
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
            html.Div(orbit_row['OBJECT_NAME'], style={'color': 'white', 'fontSize': '14px', 'fontWeight': 'bold', 'marginRight': '20px', 'alignSelf': 'center'}),
            kpi('Altitude', f"{orbit_row['ALTITUDE']:.0f} km"),
            kpi('Órbita', orbit_row['ORBIT_TYPE']),
            kpi('Inclinação', f"{orbit_row['INCLINATION']:.1f}°"),
            kpi('Período', f"{orbit_row['PERIOD']:.1f} min"),
            kpi('Constelação', orbit_row['CONSTELLATION']),
        ]

    fig = build_globe_figure(df_f, orbit_row=orbit_row)
    return fig, info_children

if __name__ == '__main__':
    app.run(debug=True)