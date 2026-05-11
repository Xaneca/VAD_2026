import dash
from dash import dcc, html
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Inicializar a app
app = dash.Dash(__name__)

# ============================================================
# DADOS DE EXEMPLO (substituir pelos seus dados reais)
# ============================================================
df_example = pd.DataFrame({
    'country': ['USA', 'China', 'Russia', 'Europe', 'Japan'],
    'objects': [3000, 2500, 1500, 800, 400],
    'year': [2020, 2021, 2022, 2023, 2024],
    'launches': [40, 55, 60, 75, 90]
})

# ============================================================
# GRÁFICOS (criar os seus gráficos aqui)
# ============================================================

# 1. Donut Chart - Type Object
fig_type_object = go.Figure(data=[go.Pie(
    values=[45, 30, 15, 10],
    labels=['Satellites', 'Debris', 'Rocket Bodies', 'Other'],
    hole=0.6,
    marker_colors=['#e8c298', '#8b9dc3', '#4a5568', '#2d3748']
)])
fig_type_object.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    showlegend=False,
    margin=dict(l=10, r=10, t=10, b=10),
    annotations=[dict(text='Type<br>object', x=0.5, y=0.5, font_size=12, font_color='white', showarrow=False)]
)

# 2. Mini Donut - Percentagem
fig_percentage = go.Figure(data=[go.Pie(
    values=[75, 25],
    hole=0.7,
    marker_colors=['#4a6fa5', '#2d3748']
)])
fig_percentage.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    showlegend=False,
    margin=dict(l=5, r=5, t=5, b=5),
    annotations=[dict(text='%', x=0.5, y=0.5, font_size=14, font_color='white', showarrow=False)]
)

# 3. Bar Graph - Object/Country
fig_bar_country = go.Figure(data=[go.Bar(
    x=df_example['country'],
    y=df_example['objects'],
    marker_color='#4a6fa5'
)])
fig_bar_country.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=20, r=20, t=20, b=40),
    xaxis=dict(showgrid=False, color='white'),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white')
)

# 4. 3D Map Placeholder (substituir por mapa real)
fig_3d_map = go.Figure(data=[go.Scattergeo(
    lon=[0], lat=[0],
    mode='markers',
    marker=dict(size=1, color='#4a6fa5')
)])
fig_3d_map.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    geo=dict(
        bgcolor='rgba(0,0,0,0)',
        showland=True,
        landcolor='#2d3748',
        showocean=True,
        oceancolor='#1a2332',
        showcoastlines=True,
        coastlinecolor='#4a5568',
        projection_type='orthographic'
    ),
    margin=dict(l=0, r=0, t=0, b=0)
)

# 5. Violin Plot - Height Density
fig_violin = go.Figure(data=[go.Violin(
    y=[200, 400, 500, 600, 800, 1000, 1200, 35786],
    box_visible=True,
    line_color='#4a6fa5',
    fillcolor='#2d4a6f',
    opacity=0.6
)])
fig_violin.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=20, r=20, t=20, b=20),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white'),
    xaxis=dict(showticklabels=False)
)

# 6. Line Graph - Launch/Year
fig_line_year = go.Figure(data=[go.Scatter(
    x=df_example['year'],
    y=df_example['launches'],
    mode='lines+markers',
    line=dict(color='#4a6fa5', width=2),
    marker=dict(size=8)
)])
fig_line_year.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=30, r=20, t=20, b=40),
    xaxis=dict(showgrid=False, color='white'),
    yaxis=dict(showgrid=True, gridcolor='#2d3748', color='white')
)

# ============================================================
# ESTILOS
# ============================================================
COLORS = {
    'background': '#0d1421',
    'card': '#1a2332',
    'border': '#2d3748',
    'text': '#ffffff',
    'accent': '#4a6fa5'
}

card_style = {
    'backgroundColor': COLORS['card'],
    'borderRadius': '15px',
    'padding': '10px',
    'display': 'flex',
    'flexDirection': 'column',
    'justifyContent': 'center',
    'alignItems': 'center'
}

button_style = {
    'backgroundColor': COLORS['card'],
    'color': COLORS['text'],
    'border': 'none',
    'borderRadius': '20px',
    'padding': '8px 20px',
    'cursor': 'pointer',
    'fontSize': '14px'
}

# ============================================================
# LAYOUT
# ============================================================
app.layout = html.Div(style={
    'backgroundColor': COLORS['background'],
    'minHeight': '100vh',
    'padding': '0px',
    'fontFamily': 'Arial, sans-serif'
}, children=[
    
    # Container principal com CSS Grid
    html.Div(style={
        'display': 'grid',
        'gridTemplateColumns': '1fr 1fr 1.5fr 1fr',
        'gridTemplateRows': 'auto auto auto auto',
        'gap': '15px',
        'maxWidth': '900px',
        'margin': '0 auto'
    }, children=[
        
        # ===== LINHA 1 =====
        
        # Donut Chart - Type Object (ocupa 2 colunas)
        html.Div(style={**card_style, 'gridColumn': '1 / 3', 'gridRow': '1 / 2', 'height': '180px'}, children=[
            dcc.Graph(figure=fig_type_object, config={'displayModeBar': False}, 
                      style={'width': '100%', 'height': '100%'})
        ]),
        
        # Botões Orbit/Launch + Bar Graph
        html.Div(style={**card_style, 'gridColumn': '3 / 5', 'gridRow': '1 / 2', 'height': '180px'}, children=[
            html.Div(style={'display': 'flex', 'gap': '10px', 'marginBottom': '10px'}, children=[
                html.Button('orbit', style=button_style),
                html.Button('launch', style={**button_style, 'backgroundColor': '#2d3748'})
            ]),
            html.Div('OBJECT / COUNTRY', style={'color': COLORS['text'], 'fontSize': '16px', 'fontWeight': 'bold'}),
            html.Div('(BAR GRAPH)', style={'color': '#6b7280', 'fontSize': '12px'}),
            dcc.Graph(figure=fig_bar_country, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '80px'})
        ]),
        
        # ===== LINHA 2 - KPIs =====
        
        # NUM OBJECTS
        html.Div(style={**card_style, 'gridColumn': '1', 'gridRow': '2', 'height': '60px'}, children=[
            html.Div('NUM', style={'color': COLORS['text'], 'fontSize': '14px', 'fontWeight': 'bold'}),
            html.Div('OBJECTS', style={'color': COLORS['text'], 'fontSize': '14px', 'fontWeight': 'bold'})
        ]),
        
        # Mini Donut Percentagem
        html.Div(style={**card_style, 'gridColumn': '2', 'gridRow': '2', 'height': '60px'}, children=[
            dcc.Graph(figure=fig_percentage, config={'displayModeBar': False},
                      style={'width': '60px', 'height': '60px'})
        ]),
        
        # ===== LINHA 3 - 3D MAP + FILTERS =====
        
        # 3D MAP (ocupa 3 colunas)
        html.Div(style={**card_style, 'gridColumn': '1 / 4', 'gridRow': '3 / 4', 'height': '200px'}, children=[
            html.Div('3D MAP', style={'color': COLORS['text'], 'fontSize': '18px', 'fontWeight': 'bold', 
                                       'position': 'absolute', 'bottom': '20px', 'left': '20px'}),
            dcc.Graph(figure=fig_3d_map, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '100%'})
        ]),
        
        # FILTERS
        html.Div(style={**card_style, 'gridColumn': '4', 'gridRow': '2 / 4', 'height': 'auto'}, children=[
            html.Div('▼', style={'color': COLORS['text'], 'fontSize': '16px', 'marginBottom': '20px'}),
            html.Div('FILTERS', style={'color': COLORS['text'], 'fontSize': '18px', 'fontWeight': 'bold'})
        ]),
        
        # ===== LINHA 4 - BOTTOM ROW =====
        
        # HEIGHT DENSITY (Violin)
        html.Div(style={**card_style, 'gridColumn': '1', 'gridRow': '4', 'height': '150px'}, children=[
            html.Div('HEIGHT', style={'color': COLORS['text'], 'fontSize': '14px', 'fontWeight': 'bold'}),
            html.Div('DENSIT.', style={'color': COLORS['text'], 'fontSize': '14px', 'fontWeight': 'bold'}),
            html.Div('(VIOLIN)', style={'color': '#6b7280', 'fontSize': '10px'}),
            dcc.Graph(figure=fig_violin, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '80px'})
        ]),
        
        # LAUNCH/YEAR (Line Graph)
        html.Div(style={**card_style, 'gridColumn': '2 / 4', 'gridRow': '4', 'height': '150px'}, children=[
            html.Div('LAUNCH', style={'color': COLORS['text'], 'fontSize': '16px', 'fontWeight': 'bold'}),
            html.Div('/YEAR', style={'color': COLORS['text'], 'fontSize': '16px', 'fontWeight': 'bold'}),
            html.Div('(LINE GRAPH)', style={'color': '#6b7280', 'fontSize': '10px'}),
            dcc.Graph(figure=fig_line_year, config={'displayModeBar': False},
                      style={'width': '100%', 'height': '80px'})
        ]),
        
        # SELECT YEAR
        html.Div(style={**card_style, 'gridColumn': '4', 'gridRow': '4', 'height': '150px'}, children=[
            html.Div('SELECT', style={'color': COLORS['text'], 'fontSize': '14px', 'fontWeight': 'bold'}),
            html.Div('YEAR', style={'color': COLORS['text'], 'fontSize': '14px', 'fontWeight': 'bold'}),
            dcc.Dropdown(
                options=[{'label': str(y), 'value': y} for y in range(2020, 2027)],
                value=2024,
                style={'width': '100px', 'marginTop': '10px'}
            )
        ])
    ])
])

# ============================================================
# EXECUTAR
# ============================================================
if __name__ == '__main__':
    app.run(debug=True)
