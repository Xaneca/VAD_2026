import dash
from dash import dcc, html # <-- Adiciona o dcc aqui se não o tiveres
import plotly.graph_objects as go
import pandas as pd
import subprocess
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# FILES
launch_file = "../DATASETS_SATTELITES/launch_site_gps.csv"
satellite_file = "../DATASETS_SATTELITES/merged_dataset.csv"


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
# TODO
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
# TODO

# ============================================================
# 2D MAP
# ============================================================
# TODO

# ============================================================
# COUNTRY LAUNCH
# ============================================================
# TODO

# ============================================================
# LAUNCH PER YEAR
# ============================================================
# TODO

# ============================================================
# SELECT LAUNCH SITE (FILTER)
# ============================================================
# TODO

# ============================================================
# INICIAR APP
# ============================================================
app = dash.Dash(__name__)

app.layout = html.Div(style={
    'backgroundColor': COLORS['background'],
    'minHeight': '100vh',
    'padding': '30px',
    'fontFamily': 'Arial, sans-serif'
}, children=[
    
    # BOTOES DE NAVEGAÇÃO (Topo Direita)
    html.Div(style={'display': 'flex', 'justifyContent': 'flex-end', 'marginBottom': '20px', 'gap': '10px'}, children=[
        html.Button('orbit', style={'backgroundColor': '#253e50', 'color': 'white', 'border': 'none', 'padding': '8px 20px', 'borderRadius': '20px'}),
        html.Button('launch', style={'backgroundColor': '#4a6fa5', 'color': 'white', 'border': 'none', 'padding': '8px 20px', 'borderRadius': '20px'}),
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
        html.Div(style={**card_style, 'gridColumn': '3', 'gridRow': '1'}, children=[
            html.Div("launch: last 12 months vs previous year", style={'color': '#9ca3af', 'fontSize': '12px', 'marginBottom': '20px', 'textAlign': 'center'}),
            
            # Colocamos os dois números lado a lado usando flexbox
            html.Div(style={'display': 'flex', 'justifyContent': 'space-around', 'width': '100%'}, children=[
                # Bloco Esquerdo (Last Year)
                html.Div([
                    html.Div("50", style={'fontSize': '38px'}),
                    html.Div("launches\nlast year", style={'color': '#9ca3af', 'fontSize': '11px', 'whiteSpace': 'pre-line'})
                ]),
                # Bloco Direito (This Year)
                html.Div([
                    html.Div("27", style={'fontSize': '38px'}),
                    html.Div("launches\nthis year", style={'color': '#9ca3af', 'fontSize': '11px', 'whiteSpace': 'pre-line'})
                ])
            ])
        ]),

        # LINHA 2 (O mapa estica-se pelas colunas 2 e 3)
        html.Div("2D MAP (country)", style={**card_style, 'gridColumn': '2 / 4', 'gridRow': '2', 'minHeight': '250px'}),

        # LINHA 3 (Gráfico de Barras estica-se por todas as 3 colunas)
        html.Div("Country launch - num sites vs num launches", style={**card_style, 'gridColumn': '1 / 4', 'gridRow': '3', 'minHeight': '300px'}),

        # LINHA 4
        html.Div("Launch per year (Line Graph)", style={**card_style, 'gridColumn': '1 / 3', 'gridRow': '4', 'minHeight': '300px'}),
        html.Div("Select Launch Site (Filter)", style={**card_style, 'gridColumn': '3', 'gridRow': '4'}),

    ])
])

if __name__ == '__main__':
    args = sys.argv[1:]  # Pega os argumentos passados na linha de comando, ignorando o nome do script
    if '--update-data' in args:
        executar_pipeline()

    app.run(debug=True, port=8051)