import dash
from dash import html, dcc, callback, Input, Output
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
    # 1. Correr o Jupyter Notebook
    print("⏳ Dataset merge...")
    # O comando nbconvert permite correr um notebook por trás, sem abrir a janela
    subprocess.run(["jupyter", "nbconvert", "--to", "notebook", "--execute", "datasets_merge.ipynb"])
    print("✅ Notebook done!\n")

    # 2. Correr o Script Python
    print("⏳ TLE infos...")
    # sys.executable garante que usa o mesmo interpretador de Python
    subprocess.run([sys.executable, "add_tle_infos.py"])
    print("✅ Script done!\n")

# ============================================================
# ESTILOS REAPROVEITADOS
# ============================================================
COLORS = {
    'background': '#10151f', # A cor mais escura (fundo geral da página)
    'card': '#1f2735',       # A cor mais clara (fundo das tuas divs/cartões)
    'border': '#2d3748',     # Cor das bordas, se necessario
    'text': '#ffffff',       # Texto a branco
    'accent': '#4a6fa5'      # Azul de destaque para botões
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
    # Um pequeno sombreado para dar profundidade
    'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.3)' 
}

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

# ============================================================
# RANKING LIST - BAR PLOT
# ============================================================
df_launches = pd.read_csv(launch_file)

df_launches_sorted = df_launches.sort_values(by='count', ascending=False)

# 3. Agora sim, apanhamos o verdadeiro Top 7
df_top7 = df_launches_sorted.head(7)

# 4. Extrair as colunas para o gráfico
sites = df_top7['LAUNCH_SITE'].tolist()
launches = df_top7['count'].tolist()

fig_ranking = go.Figure(go.Bar(
    x=launches,          # Eixo X tem os números
    y=sites,               # Eixo Y tem os nomes
    orientation='h',        # 'h' significa Horizontal! O padrão é vertical.
    marker_color='#4a6fa5', # A cor da barra
    text=launches,       # Coloca o número escrito na própria barra
    textposition='auto',    # O Plotly decide se o texto fica dentro ou fora da barra
    textfont=dict(color='white')
))

# Limpar o fundo para ficar transparente e combinar com o teu design
fig_ranking.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=0, t=40, b=0), # Margens (Left, Right, Top, Bottom)
    xaxis=dict(showgrid=False, showticklabels=False, zeroline=False), # Escondemos os números do eixo X em baixo porque já estão nas barras
    yaxis=dict(autorange="reversed", showgrid=False, color='white', tickfont=dict(size=12)), # 'reversed' para o maior ficar no topo!
    title=dict(text="RANKING LIST", font=dict(color='white', size=18))
)

# ============================================================
# LAST LAUNCH
# ============================================================
df_merged = pd.read_csv(satellite_file)

# Converter a coluna LAUNCH_DATE para um formato de data "verdadeiro" do Pandas
df_merged['LAUNCH_DATE'] = pd.to_datetime(df_merged['LAUNCH_DATE'], errors='coerce')

# Ordenar as datas do mais recente para o mais antigo e apanhar a primeira linha (iloc[0])
last_launch = df_merged.sort_values(by='LAUNCH_DATE', ascending=False).iloc[0]

# Extrair as variáveis que queremos usar no cartão
last_launch_name = last_launch['NAME']
last_launch_site = last_launch['LAUNCH_SITE']
last_launch_id = last_launch['OBJECT_ID']
last_launch_date = last_launch['LAUNCH_DATE'].strftime('%Y-%m-%d') # Formatar a data para algo mais legível

# ============================================================
# LAST YEAR LAUNCHES VS THIS YEAR
# ============================================================
cur_year = pd.Timestamp.now().year
prev_year = cur_year - 1

# Extrair apenas o ano da coluna LAUNCH_DATE
df_merged['LAUNCH_YEAR'] = df_merged['LAUNCH_DATE'].dt.year

# Contar quantos lançamentos existem para cada ano
launches_this_year = len(df_merged[df_merged['LAUNCH_YEAR'] == cur_year])
launches_last_year = len(df_merged[df_merged['LAUNCH_YEAR'] == prev_year])

# ============================================================
# 2D MAP
# ============================================================
hover_texts = df_launches['LOCATION_NAME'] + '<br>Lançamentos: ' + df_launches['count'].astype(str)

fig_map = go.Figure(go.Scattergeo(
    lon = df_launches['LONGITUDE'],
    lat = df_launches['LATITUDE'],
    text = hover_texts,
    hoverinfo = 'text',
    marker = dict(
        size = df_launches['count'],
        sizemode = 'area', # Faz com que a área da bolha seja proporcional ao número
        # Matemática do Plotly para escalar o tamanho das bolhas (o 40 é o tamanho máximo)
        sizeref = 2. * max(df_launches['count']) / (40.**2), 
        sizemin = 3,
        color = '#e66b8b', # Este é o tom rosa/vermelho do teu mockup
        line_color = 'rgba(255, 255, 255, 0.8)', # Bordinha branca
        line_width = 1,
        opacity = 0.8
    )
))

# Estilizar o mapa para ficar com as tuas cores (oceano escuro, continentes azul-acinzentado)
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
        showlakes=True,           # <-- ADICIONAR ESTA LINHA
        lakecolor='#10151f',      # <-- ADICIONAR ESTA (usamos a cor do oceano)
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

# Ordenar do maior para o menor número de lançamentos
df_country = df_country.sort_values('total_launches', ascending=False)

fig_country = make_subplots(specs=[[{"secondary_y": True}]])

# Barra 1: Total Launches (A rosa/vermelha)
fig_country.add_trace(
    go.Bar(
        x=df_country['COUNTRY'], 
        y=df_country['total_launches'], 
        name="Total launches (Log)", 
        marker_color='#e66b8b',
        offsetgroup=1  # <--- ADICIONAR ISTO AQUI
    ), 
    secondary_y=False 
)

# Barra 2: Number of Sites (A azul/cinza clara)
fig_country.add_trace(
    go.Bar(
        x=df_country['COUNTRY'], 
        y=df_country['num_sites'], 
        name="Number of Sites (Linear)", 
        marker_color='#8ea4b8', 
        offsetgroup=2  # <--- E ADICIONAR ISTO AQUI
    ), 
    secondary_y=True 
)

# Estética Geral e Legenda no topo
fig_country.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=0, t=40, b=0),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="right", x=1,
        font=dict(color="white")
    ),
    barmode='group',
    bargap=0.3,       # Espaço entre os diferentes países (0 a 1)
    bargroupgap=0.1   # Espaço entre a barra rosa e a azul (0 a 1)
)

# Configurar o Eixo Y Principal (Esquerda - Logarítmico)
fig_country.update_yaxes(
    title_text="Number of Launches", 
    type="log", # <-- A magia da escala logarítmica!
    color='white', 
    showgrid=True, gridcolor='#2d3748', 
    secondary_y=False
)

# Configurar o Eixo Y Secundário (Direita - Linear)
fig_country.update_yaxes(
    title_text="Number of Sites", 
    type="linear",
    color='white', 
    showgrid=False, # Desligamos as linhas de fundo para não ficar confuso
    secondary_y=True,
    rangemode="tozero" # Força o eixo a começar no zero
)

# Configurar o Eixo X
fig_country.update_xaxes(
    color='white', 
    tickangle=-45 # Inclina os nomes dos países para caberem todos
)

# ============================================================
# LAUNCH PER YEAR
# ============================================================
df_yearly = df_merged.groupby('LAUNCH_YEAR').size().reset_index(name='launches')

df_yearly = df_yearly.sort_values('LAUNCH_YEAR')
df_yearly = df_yearly[df_yearly['LAUNCH_YEAR'] >= 1957] # inicio da era espacial

fig_line = go.Figure(go.Scatter(
    x=df_yearly['LAUNCH_YEAR'], 
    y=df_yearly['launches'],
    mode='lines+markers', # Mostra a linha e as "bolinhas" em cada ponto
    line=dict(color='#00d4ff', width=3),
    marker=dict(size=6, color='#e66b8b', line=dict(width=1, color='white')) # Pontos a cruzar as tuas duas cores principais!
))

fig_line.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=20, t=10, b=0),
    xaxis=dict(color='white', showgrid=False, tickformat="d"), # "d" força o Plotly a mostrar o ano sem vírgulas (ex: 2026 em vez de 2,026)
    yaxis=dict(color='white', showgrid=True, gridcolor='#2d3748', title="Number of Launches")
)


# ============================================================
# SELECT LAUNCH SITE (FILTER)
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
    
    # BOTOES DE NAVEGAÇÃO (Topo Direita)
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

    # O NOSSO GRID PRINCIPAL
    html.Div(style={
        'display': 'grid',
        'gridTemplateColumns': '1fr 1fr 1fr', # 3 colunas de larguras iguais
        'gap': '20px', # Espaço entre os cartões
        # As linhas ajustam-se automaticamente ao conteúdo, mas damos tamanhos base
        'gridAutoRows': 'minmax(150px, auto)' 
    }, children=[
        
        # LINHA 1 & 2
        # 1. RANKING LIST (Linha 1 & 2)
        html.Div(style={**card_style, 'gridColumn': '1', 'gridRow': '1 / 3', 'padding': '10px'}, children=[
            dcc.Graph(
                figure=fig_ranking, 
                config={'displayModeBar': False}, # Isto esconde aquela barra de ferramentas chata do Plotly
                style={'width': '100%', 'height': '100%'}
            )
        ]),

        # 2. LAST LAUNCH (Linha 1, Coluna 2)
        html.Div(style={**card_style, 'gridColumn': '2', 'gridRow': '1'}, children=[
            html.Div("LAST LAUNCH", style={'color': '#9ca3af', 'fontSize': '12px', 'letterSpacing': '1px', 'marginBottom': '10px'}),
            # Variáveis dinâmicas!
            html.Div(f"Launched on: {last_launch_date}", style={'color': '#00d4ff', 'fontSize': '12px', 'marginBottom': '10px'}),
            html.Div(str(last_launch_name), style={'fontSize': '14px', 'marginBottom': '5px'}),
            html.Div(str(last_launch_site), style={'fontSize': '36px', 'letterSpacing': '2px', 'marginBottom': '5px'}),
            html.Div(str(last_launch_id),   style={'color': '#9ca3af', 'fontSize': '12px'})
        ]),

        # 3. KPI - Last 12 Months (Linha 1, Coluna 3)
        html.Div(style={**card_style, 'gridColumn': '3', 'gridRow': '1', 'padding': '10px'}, children=[
            
            # Flexbox para alinhar tudo perfeitamente ao centro sem o título
            html.Div(style={'display': 'flex', 'justifyContent': 'space-evenly', 'alignItems': 'center', 'width': '100%', 'height': '100%'}, children=[
                
                # Bloco Esquerdo (Ano Anterior)
                html.Div([
                    html.Div(str(launches_last_year), style={'fontSize': '48px', 'fontWeight': 'bold', 'color': 'white'}),
                    html.Div(f"launches\n{prev_year}", style={'color': '#9ca3af', 'fontSize': '13px', 'whiteSpace': 'pre-line', 'textTransform': 'uppercase'})
                ]),
                
                # Linha divisória vertical
                html.Div(style={'width': '1px', 'height': '60px', 'backgroundColor': '#2d3748'}),
                
                # Bloco Direito (Ano Atual)
                html.Div([
                    html.Div(str(launches_this_year), style={'fontSize': '48px', 'fontWeight': 'bold', 'color': '#00d4ff'}),
                    html.Div(f"launches\n{cur_year}", style={'color': '#9ca3af', 'fontSize': '13px', 'whiteSpace': 'pre-line', 'textTransform': 'uppercase'})
                ])
            ])
        ]),

        # LINHA 2 (O mapa estica-se pelas colunas 2 e 3)
        html.Div(style={**card_style, 'gridColumn': '2 / 4', 'gridRow': '2', 'padding': '15px', 'minHeight': '350px'}, children=[
            # O Título alinhado à esquerda como no teu mockup
            html.H3("Global Satellite Launch Sites by Volume", style={
                'fontWeight': 'normal', 'marginBottom': '0px', 'textAlign': 'left', 
                'width': '100%', 'paddingLeft': '10px', 'fontSize': '16px'
            }),
            
            # O Gráfico
            dcc.Graph(
                figure=fig_map, 
                config={'displayModeBar': True, 'scrollZoom': True}, 
                style={'width': '100%', 'height': '100%', 'flex': '1'}
            )
        ]),

        # LINHA 3 (Gráfico de Barras estica-se por todas as 3 colunas)
        html.Div(style={**card_style, 'gridColumn': '1 / 4', 'gridRow': '3', 'minHeight': '400px'}, children=[
            html.H3("Launch information by country", style={'fontWeight': 'normal', 'fontSize': '16px', 'marginBottom': '10px', 'textAlign': 'left', 'width': '100%'}),
            dcc.Graph(figure=fig_country, config={'displayModeBar': False}, style={'width': '100%', 'height': '100%', 'flex': '1'})
        ]),

        # LINHA 4
        html.Div(style={**card_style, 'gridColumn': '1 / 3', 'gridRow': '4', 'minHeight': '400px', 'alignItems': 'flex-start'}, children=[
            
            # Título dinâmico (com ID para podermos alterá-lo)
            html.H3(id='line-chart-title', children="Launches over the years", style={'fontWeight': 'normal', 'fontSize': '16px', 'marginBottom': '10px'}),
            
            # O Dropdown para filtrar
            dcc.Dropdown(
                id='site-dropdown',
                # Criamos a opção "ALL" e depois juntamos todos os sites únicos do teu df_merged
                options=[{'label': 'All Sites', 'value': 'ALL'}] + [{'label': site, 'value': site} for site in df_merged['LAUNCH_SITE'].dropna().unique()],
                value='ALL', # Valor pré-selecionado ao abrir a página
                clearable=False,
                style={'width': '300px', 'color': 'black', 'marginBottom': '20px'} # Cor preta para o texto se ler no fundo branco do dropdown
            ),
            
            # O espaço vazio para o Gráfico (com ID para o Callback saber para onde o enviar)
            dcc.Graph(id='line-graph', config={'displayModeBar': False}, style={'width': '100%', 'height': '100%', 'flex': '1'})
        ]),

        html.Div("Select Launch Site (Filter)", style={**card_style, 'gridColumn': '3', 'gridRow': '4'}),

    ])
])

# ========================================
# CALLBACKS
# ========================================

@callback(
    Output('line-graph', 'figure'),
    Output('line-chart-title', 'children'),
    Input('site-dropdown', 'value')
)
def update_line_chart(selected_site):
    # 1. Filtrar os dados com base na escolha
    if selected_site == 'ALL':
        df_filtered = df_merged
        title = "Launches over the years: All Sites"
    else:
        df_filtered = df_merged[df_merged['LAUNCH_SITE'] == selected_site]
        title = f"Launches over the years: {selected_site}"
        
    # 2. Agrupar por ano (usando os dados filtrados)
    df_yearly = df_filtered.groupby('LAUNCH_YEAR').size().reset_index(name='launches')
    df_yearly = df_yearly[df_yearly['LAUNCH_YEAR'] >= 1957].sort_values('LAUNCH_YEAR')
    
    # 3. Desenhar a linha suave
    fig = go.Figure(go.Scatter(
        x=df_yearly['LAUNCH_YEAR'], 
        y=df_yearly['launches'],
        mode='lines+markers', # <-- MUDAR AQUI: adicionar '+markers'
        line=dict(color='#4a6fa5', width=3, shape='spline'), 
        marker=dict(size=6, color='#e66b8b', line=dict(width=1, color='white')) # <-- ADICIONAR AQUI: o estilo dos pontos
    ))
    
    # 4. Configurar a escala Logarítmica
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=20, t=10, b=0),
        xaxis=dict(color='white', showgrid=False, tickformat="d", title="Year"),
        yaxis=dict(
            color='white', 
            showgrid=True, gridcolor='#2d3748', 
            title="Number of Launches (Log)", 
            type='log' # type='log' faz a magia dos 10, 100, 1000
        )
    )
    
    return fig, title

if __name__ == '__main__':
    args = sys.argv[1:] 
    if '--update-data' in args:
        executar_pipeline()

    app.run(debug=True, port=8051)