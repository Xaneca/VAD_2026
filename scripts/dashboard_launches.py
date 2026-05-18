import dash
from dash import html, dcc, callback, Input, State, Output, no_update
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import pandas as pd
import subprocess
import sys
import asyncio
from plotly.subplots import make_subplots

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# FILES
launch_file = "./DATASETS_SATTELITES/launch_site_gps.csv"
satellite_file = "./DATASETS_SATTELITES/merged_dataset.csv"

dash.register_page(__name__, name='Launches', path='/launches')

def executar_pipeline():
    # Correr Jupyter Notebook
    print("⏳ Dataset merge...")
    # Executar processo em plano de fundo
    subprocess.run(["jupyter", "nbconvert", "--to", "notebook", "--execute", "datasets_merge.ipynb"])
    print("✅ Notebook done!\n")

    # Correr Script Python
    print("⏳ TLE infos...")
    # Executar com o interpretador atual
    subprocess.run([sys.executable, "add_tle_infos.py"])
    print("✅ Script done!\n")

# ============================================================
# ESTILOS REAPROVEITADOS
# ============================================================
COLORS = {
    'background': '#10151f', # Fundo geral da pagina
    'card': '#1f2735',       # Fundo dos cartoes
    'border': '#2d3748',     # Cor das bordas
    'text': '#ffffff',       # Cor do texto
    'accent': '#4a6fa5'      # Cor de destaque
}

card_style = {
    'backgroundColor': COLORS['card'],
    'borderRadius': '10px',
    'padding': '20px',
    'display': 'flex',
    'flexDirection': 'column',
    'justifyContent': 'center',
    'alignItems': 'center',
    'color': 'white',
    'textAlign': 'center',
    # Sombreado
    'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.3)' 
}

button_style = {
    'padding': '6px 16px',
    'borderRadius': '20px',
    'fontSize': '13px',
    'fontWeight': '500',
    'textDecoration': 'none',  # Remove sublinhado
    'display': 'inline-block',
    'backgroundColor': COLORS['card'], # Cor passiva
    'color': '#9ca3af',
    'border': '1px solid #374151',
}

# ============================================================
# RANKING LIST
# ============================================================
df_launches = pd.read_csv(launch_file)

df_launches_sorted = df_launches.sort_values(by='count', ascending=False)

# Obter valores do topo
df_top7 = df_launches_sorted.head(7)

# Extrair colunas para grafico
sites = df_top7['LAUNCH_SITE'].tolist()
launches = df_top7['count'].tolist()

fig_ranking = go.Figure(go.Bar(
    x=launches,          # Valores do Eixo X
    y=sites,               # Valores do Eixo Y
    orientation='h',        # Orientacao horizontal
    marker_color='#4a6fa5', # Cor da barra
    text=launches,       # Texto na barra
    textposition='auto',    # Posicao automatica do texto
    textfont=dict(color='white'),
    hovertemplate="<b>%{y}</b><br>Launches: %{x}<extra></extra>"
))

# Fundo transparente
fig_ranking.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=0, t=40, b=0), # Margens
    xaxis=dict(showgrid=False, showticklabels=False, zeroline=False), # Ocultar eixo X
    yaxis=dict(autorange="reversed", showgrid=False, color='white', tickfont=dict(size=12), tick0=20), # Inverter eixo Y
    title=dict(text="RANKING LIST", font=dict(color='white', size=18)),
)

# ============================================================
# LAST LAUNCH
# ============================================================
df_merged = pd.read_csv(satellite_file)

# Converter formato de data
df_merged['LAUNCH_DATE'] = pd.to_datetime(df_merged['LAUNCH_DATE'], errors='coerce')

# Obter registo mais recente
last_launch = df_merged.sort_values(by='LAUNCH_DATE', ascending=False).iloc[0]

# Extrair variaveis
last_launch_name = last_launch['NAME']
last_launch_site = last_launch['LAUNCH_SITE']
last_launch_id = last_launch['OBJECT_ID']
last_launch_date = last_launch['LAUNCH_DATE'].strftime('%Y-%m-%d') # Formatar data

# ============================================================
# LAST YEAR LAUNCHES VS THIS YEAR
# ============================================================
cur_year = pd.Timestamp.now().year
prev_year = cur_year - 1

# Extrair ano
df_merged['LAUNCH_YEAR'] = df_merged['LAUNCH_DATE'].dt.year

# Contagem por ano
launches_this_year = len(df_merged[df_merged['LAUNCH_YEAR'] == cur_year])
launches_last_year = len(df_merged[df_merged['LAUNCH_YEAR'] == prev_year])

# ============================================================
# MAPA
# ============================================================
hover_texts = df_launches['LOCATION_NAME'] + '<br>Launches: ' + df_launches['count'].astype(str)

fig_map = go.Figure(go.Scattergeo(
    lon = df_launches['LONGITUDE'],
    lat = df_launches['LATITUDE'],
    text = hover_texts,
    hoverinfo = 'text',
    marker = dict(
        size = df_launches['count'],
        sizemode = 'area', # Area proporcional
        # Escalar bolhas
        sizeref = 2. * max(df_launches['count']) / (40.**2), 
        sizemin = 3,
        color = '#e66b8b', # Cor dos marcadores
        line_color = 'rgba(255, 255, 255, 0.8)', # Cor da borda
        line_width = 1,
        opacity = 0.8
    )
))

# Estilo do mapa
fig_map.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=0, t=0, b=0),
    geo=dict(
        bgcolor='rgba(0,0,0,0)',
        showland=True,
        landcolor='#253e50',      
        showocean=True,
        oceancolor='#10151f',     
        showlakes=True,           # Mostrar lagos
        lakecolor='#10151f',      # Cor dos lagos
        showcountries=True,
        countrycolor='#2d3748',   
        projection_type='natural earth',
        showframe=False,          
        coastlinecolor='#2d3748'
    )
)

# ============================================================
# COUNTRY LAUNCH
# ============================================================
df_country = df_launches.groupby('COUNTRY').agg(
    total_launches=('count', 'sum'),
    num_sites=('LAUNCH_SITE', 'nunique')
).reset_index()

# Ordenar decrescente
df_country = df_country.sort_values('total_launches', ascending=False)

fig_country = make_subplots(specs=[[{"secondary_y": True}]])

# Barra Total Launches
fig_country.add_trace(
    go.Bar(
        x=df_country['COUNTRY'], 
        y=df_country['total_launches'], 
        name="Total launches (Log)", 
        marker_color='#e66b8b',
        offsetgroup=1,
        hovertemplate="<b>%{x}</b><br>Launches: %{y}<extra></extra>"
    ), 
    secondary_y=False 
)

# Barra Number of Sites
fig_country.add_trace(
    go.Bar(
        x=df_country['COUNTRY'], 
        y=df_country['num_sites'], 
        name="Number of Sites (Linear)", 
        marker_color='#8ea4b8', 
        offsetgroup=2,
        hovertemplate="<b>%{x}</b><br>Num sites: %{y}<extra></extra>"
    ), 
    secondary_y=True 
)

# Estetica geral e legenda
fig_country.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=50, r=60, t=40, b=0),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="right", x=1,
        font=dict(color="white")
    ),
    barmode='group',
    bargap=0.3,       # Espaco entre grupos
    bargroupgap=0.1   # Espaco entre barras
)

# Configurar Eixo Y Principal Logaritmico
fig_country.update_yaxes(
    title_text="Number of Launches", 
    type="log", # Escala logaritmica
    color='white', 
    showgrid=True, gridcolor='#2d3748', 
    secondary_y=False
)

# Configurar Eixo Y Secundario Linear
fig_country.update_yaxes(
    title_text="Number of Sites", 
    type="linear",
    color='white', 
    showgrid=False, # Ocultar grelha
    secondary_y=True,
    rangemode="tozero" # Iniciar no zero
)

# Configurar Eixo X
fig_country.update_xaxes(
    color='white', 
    tickangle=-45 # Inclinacao das legendas
)

# ============================================================
# LAUNCH PER YEAR
# ============================================================
df_yearly = df_merged.groupby('LAUNCH_YEAR').size().reset_index(name='launches')

df_yearly = df_yearly.sort_values('LAUNCH_YEAR')
df_yearly = df_yearly[df_yearly['LAUNCH_YEAR'] >= 1957] # Inicio da contagem temporal

fig_line = go.Figure(go.Scatter(
    x=df_yearly['LAUNCH_YEAR'], 
    y=df_yearly['launches'],
    mode='lines+markers', # Modo linha e marcadores
    line=dict(color='#00d4ff', width=3),
    marker=dict(size=6, color='#e66b8b', line=dict(width=1, color='white')) # Estilo dos marcadores
))

fig_line.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=20, t=10, b=0),
    xaxis=dict(color='white', showgrid=False, tickformat="d"), # Formatar tick do eixo
    yaxis=dict(color='white', showgrid=True, gridcolor='#2d3748', title="Number of Launches")
)


# ============================================================
# SELECT LAUNCH SITE
# ============================================================
# TODO

# ============================================================
# INICIAR APP
# ============================================================
app = dash.Dash(__name__)

layout = html.Div(style={
        'backgroundColor': COLORS['background'],
        'minHeight': '100vh',
        'padding': '30px',
        'fontFamily': 'Arial, sans-serif'
    }, children=[
    
    # BOTOES DE NAVEGACAO
    html.Div(style={
        'display': 'flex', 
        'justifyContent': 'flex-end',  # Alinhamento
        'width': '100%', 
        'marginBottom': '10px'         # Margem
    }, children=[
        dcc.Store(id='last-clicked-site', data=None),
        html.Div(style={'display': 'flex', 'gap': '10px'}, children=[
            dcc.Link(
                html.Button("satellites", className="nav-pill-btn"),
                href="/"
            ),
            dcc.Link(
                html.Button("launch", className="nav-pill-btn"), 
                href="/launches"
            )
        ])
    ]),

    # GRID PRINCIPAL
    html.Div(style={
        'display': 'grid',
        'gridTemplateColumns': '1fr 1fr 1fr', # Definicao de colunas
        'gap': '20px', 
        # Definicao de linhas
        'gridAutoRows': 'minmax(150px, auto)' 
    }, children=[
        
        # LINHAS INICIAIS
        # RANKING LIST
        html.Div(style={**card_style, 'gridColumn': '1', 'gridRow': '1 / 3', 'padding': '10px'}, children=[
            dcc.Graph(
                id='bar-ranking',
                figure=fig_ranking, 
                config={'displayModeBar': False}, # Esconder tools
                style={'width': '100%', 'height': '100%'}
            )
        ]),

        # LAST LAUNCH
        html.Div(style={**card_style, 'gridColumn': '2', 'gridRow': '1'}, children=[
            html.Div("LAST LAUNCH", style={'color': '#9ca3af', 'fontSize': '12px', 'letterSpacing': '1px', 'marginBottom': '10px'}),
            # Variaveis dinamicas
            html.Div(f"Launched on: {last_launch_date}", style={'color': '#00d4ff', 'fontSize': '12px', 'marginBottom': '10px'}),
            html.Div(str(last_launch_name), style={'fontSize': '14px', 'marginBottom': '5px'}),
            html.Div(str(last_launch_site), style={'fontSize': '36px', 'letterSpacing': '2px', 'marginBottom': '5px'}),
            html.Div(str(last_launch_id),   style={'color': '#9ca3af', 'fontSize': '12px'})
        ]),

        # KPI LAST MONTHS
        html.Div(style={**card_style, 'gridColumn': '3', 'gridRow': '1', 'padding': '10px'}, children=[
            
            # Alinhamento flexbox
            html.Div(style={'display': 'flex', 'justifyContent': 'space-evenly', 'alignItems': 'center', 'width': '100%', 'height': '100%'}, children=[
                
                # Bloco Esquerdo
                html.Div([
                    html.Div(str(launches_last_year), style={'fontSize': '48px', 'fontWeight': 'bold', 'color': 'white'}),
                    html.Div(f"launches\n{prev_year}", style={'color': '#9ca3af', 'fontSize': '13px', 'whiteSpace': 'pre-line', 'textTransform': 'uppercase'})
                ]),
                
                # Linha divisoria
                html.Div(style={'width': '1px', 'height': '60px', 'backgroundColor': '#2d3748'}),
                
                # Bloco Direito
                html.Div([
                    html.Div(str(launches_this_year), style={'fontSize': '48px', 'fontWeight': 'bold', 'color': '#00d4ff'}),
                    html.Div(f"launches\n{cur_year}", style={'color': '#9ca3af', 'fontSize': '13px', 'whiteSpace': 'pre-line', 'textTransform': 'uppercase'})
                ])
            ])
        ]),

        # SEGUNDA LINHA
        html.Div(style={**card_style, 'gridColumn': '2 / 4', 'gridRow': '2', 'padding': '15px', 'minHeight': '350px'}, children=[
            # Titulo alinhado
            html.H3("Global Satellite Launch Sites by Volume", style={
                'fontWeight': 'normal', 'marginBottom': '0px', 'textAlign': 'left', 
                'width': '100%', 'paddingLeft': '10px', 'fontSize': '16px'
            }),
            
            # Grafico principal
            dcc.Graph(
                id='mapa-2d',
                figure=fig_map, 
                config={'displayModeBar': True, 'scrollZoom': True}, 
                style={'width': '100%', 'height': '100%', 'flex': '1'}
            )
        ]),

        # TERCEIRA LINHA
        html.Div(style={**card_style, 'gridColumn': '1 / 4', 'gridRow': '3', 'minHeight': '400px'}, children=[
            html.H3("Launch information by country", style={'fontWeight': 'normal', 'fontSize': '16px', 'marginBottom': '10px', 'textAlign': 'left', 'width': '100%'}),
            dcc.Graph(figure=fig_country, config={'displayModeBar': False}, style={'width': '100%', 'height': '100%', 'flex': '1'})
        ]),

        # QUARTA LINHA
        html.Div(style={**card_style, 'gridColumn': '1 / 3', 'gridRow': '4', 'minHeight': '400px', 'alignItems': 'flex-start'}, children=[
            
            # Titulo dinamico
            html.H3(id='line-chart-title', children="Launches over the years", style={'fontWeight': 'normal', 'fontSize': '16px', 'marginBottom': '10px'}),
        
            
            # Grafico de linha
            dcc.Graph(id='line-graph', config={'displayModeBar': False}, style={'width': '100%', 'height': '100%', 'flex': '1'})
        ]),

        html.Div(style={
            **card_style, 
            'gridColumn': '3', 
            'gridRow': '4', 
            'justifyContent': 'flex-start', 
            'alignItems': 'stretch',
            'padding': '20px'
        }, children=[
            html.Div("Select Launch Sites (Cumulative)", style={'fontSize': '14px', 'fontWeight': 'bold', 'color': 'white', 'marginBottom': '15px', 'textAlign': 'left'}),
            
            html.Div(style={'display': 'flex', 'gap': '10px', 'marginBottom': '15px'}, children=[
                html.Button("Select All", id="select-all-btn", n_clicks=0,
                            style={'flex': '1', 'padding': '6px', 'fontSize': '11px', 'backgroundColor': '#2d3748', 'color': '#00d4ff', 'border': '1px solid #4a6fa5', 'borderRadius': '4px', 'cursor': 'pointer', 'fontWeight': 'bold'}),
                html.Button("Clear All", id="clear-all-btn", n_clicks=0,
                            style={'flex': '1', 'padding': '6px', 'fontSize': '11px', 'backgroundColor': '#2d3748', 'color': '#ff4b4b', 'border': '1px solid #ff4b4b', 'borderRadius': '4px', 'cursor': 'pointer', 'fontWeight': 'bold'}),
            ]),

            # Contentor com scroll
            html.Div(style={'overflowY': 'auto', 'maxHeight': '280px', 'textAlign': 'left', 'paddingLeft': '5px', 'minHeight': '400px'}, children=[
                dcc.Checklist(
                    id='site-checklist',
                    options=[{'label': f" {site}", 'value': site} for site in df_merged['LAUNCH_SITE'].dropna().unique()],
                    value=list(df_merged['LAUNCH_SITE'].dropna().unique()), 
                    labelStyle={'display': 'block', 'color': 'white', 'marginBottom': '8px', 'cursor': 'pointer', 'fontSize': '13px'},
                    inputStyle={'marginRight': '8px'}
                )
            ])
        ])
    ])
])

# ========================================
# CALLBACKS
# ========================================

@callback(
    Output('line-graph', 'figure'),
    Output('line-chart-title', 'children'),
    Input('site-checklist', 'value') # Atualizar para checklist
)
def update_line_chart(selected_sites): # Receber lista de sites
    # Tratar lista vazia
    if not selected_sites:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis={'visible': False}, yaxis={'visible': False})
        return fig, "No sites selected"

    # Filtrar dados
    df_filtered = df_merged[df_merged['LAUNCH_SITE'].isin(selected_sites)]
    title = f"Launches over the years ({len(selected_sites)} sites combined)"
        
    # Agrupar por ano
    df_yearly = df_filtered.groupby('LAUNCH_YEAR').size().reset_index(name='launches')
    df_yearly = df_yearly[df_yearly['LAUNCH_YEAR'] >= 1957].sort_values('LAUNCH_YEAR')
    
    # Renderizar linha suave
    fig = go.Figure(go.Scatter(
        x=df_yearly['LAUNCH_YEAR'], 
        y=df_yearly['launches'],
        mode='lines+markers', 
        line=dict(color='#4a6fa5', width=3, shape='spline'), 
        marker=dict(size=6, color='#e66b8b', line=dict(width=1, color='white')) 
    ))
    
    # Configurar escala logaritmica
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=20, t=10, b=0),
        xaxis=dict(color='white', showgrid=False, tickformat="d", title="Year"),
        yaxis=dict(
            color='white', 
            showgrid=True, gridcolor='#2d3748', 
            title="Number of Launches (Log)", 
            type='log' 
        )
    )
    
    return fig, title

@callback(
    Output('mapa-2d', 'figure'),
    Output('last-clicked-site', 'data'), # Guardar estado
    Output('bar-ranking', 'clickData'),
    Input('bar-ranking', 'clickData'),
    State('last-clicked-site', 'data')   # Ler estado
)
def highlight_site_on_map(clickData, last_clicked):
    # Validar clique
    if clickData is None:
        raise PreventUpdate
        
    # Obter barra clicada
    site_clicado = clickData['points'][0]['y']
    
    # ==========================================
    # LOGICA DO TOGGLE
    # ==========================================
    if site_clicado == last_clicked:
        # Desativar selecao atual
        novo_selecionado = None
    else:
        # Ativar nova selecao
        novo_selecionado = site_clicado
        
    # Gerar cores condicionalmente
    cores = []
    for site in df_launches['LAUNCH_SITE']:
        if novo_selecionado is None:
            cores.append('#e66b8b') # Cor estado neutro
        elif site == novo_selecionado:
            cores.append('#00d4ff') # Cor estado selecionado
        else:
            cores.append('#e66b8b') # Cor estado inativo
            
    # Renderizar mapa atualizado
    hover_texts = df_launches['LOCATION_NAME'] + '<br>Lançamentos: ' + df_launches['count'].astype(str)

    fig_mapa_nova = go.Figure(go.Scattergeo(
        lon = df_launches['LONGITUDE'],
        lat = df_launches['LATITUDE'],
        text = hover_texts,
        hoverinfo = 'text',
        marker = dict(
            size = df_launches['count'],
            sizemode = 'area',
            sizeref = 2. * max(df_launches['count']) / (40.**2), 
            sizemin = 3,
            color = cores,          
            opacity = 0.8,  
            line_color = 'rgba(255, 255, 255, 0.8)',
            line_width = 1
        )
    ))

    fig_mapa_nova.update_layout(
        geo=dict(
            bgcolor='rgba(0,0,0,0)',
            showland=True, landcolor='#253e50',      
            showocean=True, oceancolor='#10151f',     
            showlakes=True, lakecolor='#10151f',      
            showcountries=True, countrycolor='#2d3748',   
            projection_type='natural earth',
            showframe=False,          
            coastlinecolor='#2d3748'
        ),
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=0, b=0)
    )
    
    return fig_mapa_nova, novo_selecionado, None

# Botoes de selecao em massa
@callback(
    Output('site-checklist', 'value'),
    Input('select-all-btn', 'n_clicks'),
    Input('clear-all-btn', 'n_clicks'),
    State('site-checklist', 'options'),
    prevent_initial_call=True
)
def handle_select_all_clear(all_clicks, clear_clicks, options):
    # Identificar origem do trigger
    trigger = dash.ctx.triggered_id

    if trigger == 'select-all-btn':
        # Marcar todos
        return [opt['value'] for opt in options]

    elif trigger == 'clear-all-btn':
        # Desmarcar todos
        return []

    raise dash.exceptions.PreventUpdate

if __name__ == '__main__':
    args = sys.argv[1:] 
    if '--update-data' in args:
        executar_pipeline()

    app.run(debug=True, port=8051)