from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import pandas as pd

# IMPORTAÇÃO DA SUA BIBLIOTECA
import plots_library as plib

# 1. Carregamento dos dados (Ajuste o path conforme seu arquivo)
df = pd.read_csv('../DATASETS_SATTELITES/merged_dataset_tle.csv') 

app = Dash(__name__)

# Estilos de Cores
BG_COLOR = "#00121a"
CARD_COLOR = "#244355"
ACCENT_BLUE = "#3e647d"

app.layout = html.Div(style={'backgroundColor': BG_COLOR, 'padding': '20px', 'fontFamily': 'Segoe UI, sans-serif'}, children=[
    
    # Header Buttons
    html.Div(style={'display': 'flex', 'justifyContent': 'flex-end', 'gap': '10px', 'marginBottom': '10px'}, children=[
        html.Button("orbit", style={'borderRadius': '10px', 'border': 'none', 'backgroundColor': ACCENT_BLUE, 'color': 'white', 'padding': '5px 20px', 'cursor': 'pointer'}),
        html.Button("launch", style={'borderRadius': '10px', 'border': 'none', 'backgroundColor': ACCENT_BLUE, 'color': 'white', 'padding': '5px 20px', 'cursor': 'pointer'}),
    ]),

    # GRID PRINCIPAL
    html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(4, 1fr)', 'gridGap': '15px'}, children=[
        
        # Coluna 1: Donut e KPI
        html.Div(style={'gridColumn': '1 / 2'}, children=[
            html.Div(style={'backgroundColor': CARD_COLOR, 'borderRadius': '20px', 'padding': '15px'}, children=[
                dcc.Graph(figure=plib.create_donut_chart(df), style={'height': '220px'}, config={'displayModeBar': False})
            ]),
            html.Div(style={'display': 'flex', 'gap': '10px', 'marginTop': '15px'}, children=[
                html.Div([
                    html.Small("NUM OBJECTS", style={'color': '#b8c5d6'}),
                    html.H3(len(df), style={'margin': '0', 'color': 'white'})
                ], style={'backgroundColor': CARD_COLOR, 'borderRadius': '15px', 'padding': '15px', 'flex': 2}),
                html.Div("98%", style={'backgroundColor': CARD_COLOR, 'borderRadius': '50%', 'width': '65px', 'height': '65px', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'color': 'white', 'fontWeight': 'bold'})
            ])
        ]),

        # Coluna 2-4: Bar Graph
        html.Div(style={'gridColumn': '2 / 5', 'backgroundColor': CARD_COLOR, 'borderRadius': '20px', 'padding': '20px'}, children=[
            html.Strong("OBJECT / COUNTRY", style={'color': 'white'}),
            dcc.Graph(figure=plib.create_bar_graph(df), style={'height': '280px'})
        ]),

        # Linha do Meio: 3D Map (3/4) e Filtros (1/4)
        html.Div(style={'gridColumn': '1 / 4', 'backgroundColor': CARD_COLOR, 'borderRadius': '20px', 'overflow': 'hidden'}, children=[
            dcc.Graph(figure=plib.create_3d_map(df), style={'height': '400px'})
        ]),

        html.Div(style={'gridColumn': '4 / 5', 'backgroundColor': CARD_COLOR, 'borderRadius': '20px', 'padding': '20px', 'color': 'white'}, children=[
            html.P("▼ FILTERS", style={'fontSize': '12px', 'opacity': 0.7}),
            html.Br(),
            dcc.Dropdown(
                id='filter-type',
                options=[{'label': i, 'value': i} for i in df['type'].unique()],
                multi=True,
                placeholder="Select Type...",
                style={'backgroundColor': '#1a3240', 'color': 'black'}
            )
        ]),

        # Linha Inferior
        html.Div(style={'backgroundColor': CARD_COLOR, 'borderRadius': '20px', 'padding': '15px'}, children=[
            html.Small("HEIGHT DENSIT.", style={'color': 'white'}),
            dcc.Graph(figure=plib.create_violin_plot(df), style={'height': '200px'})
        ]),
        
        html.Div(style={'gridColumn': '2 / 4', 'backgroundColor': CARD_COLOR, 'borderRadius': '20px', 'padding': '15px'}, children=[
            html.Small("LAUNCH / YEAR", style={'color': 'white'}),
            dcc.Graph(figure=plib.create_line_graph(df), style={'height': '200px'})
        ]),

        html.Div(style={'backgroundColor': CARD_COLOR, 'borderRadius': '20px', 'padding': '20px', 'color': 'white', 'textAlign': 'center'}, children=[
            html.Small("SELECT YEAR"),
            dcc.Slider(min=2000, max=2024, step=1, value=2024, marks={2000: '00', 2024: '24'})
        ]),
    ])
])

if __name__ == '__main__':
    app.run_server(debug=True)