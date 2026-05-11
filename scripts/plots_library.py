import plotly.graph_objects as go
import numpy as np

# Configuração de cores baseada na sua imagem
PASTEL_COLORS = ["#fff4dd", "#ffccac", "#b8c5d6", "#3e647d", "#6b8ca4"]

def create_donut_chart(df):
    # Exemplo baseado em 'Object Type'
    counts = df['OBJECT_TYPE'].value_counts()
    fig = go.Figure(data=[go.Pie(
        labels=counts.index, 
        values=counts.values,
        hole=.7,
        marker=dict(colors=PASTEL_COLORS),
        textinfo='none'
    )])
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        annotations=[dict(
            text='Type object', 
            x=0.5, y=0.5, 
            font_size=14, 
            showarrow=False, 
            font=dict(color="white") # O correto é dentro de font
        )]
    )
    return fig

def create_bar_graph(df):
    # Exemplo: Objetos por País
    counts = df['COUNTRY'].value_counts().head(10)
    fig = go.Figure(data=[go.Bar(
        x=counts.index,
        y=counts.values,
        marker_color='#6b8ca4'
    )])
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white"),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='#3e647d')
    )
    return fig


def prepare_3d_data(df):
    # Constantes
    R_EARTH = 6371.0
    mu = 398600.4418 

    # Converter colunas para radianos de uma só vez (Vectorização)
    inc = np.radians(df['INCLINATION'])
    raan = np.radians(df['RA_OF_ASC_NODE'])
    arg_p = np.radians(df['ARG_OF_PERICENTER'])
    m_anom = np.radians(df['MEAN_ANOMALY'])
    e = df['ECCENTRICITY']
    
    # Calcular o Semieixo Maior (a) a partir do Period (em minutos)
    period_sec = df['PERIOD'] * 60
    a = ((period_sec * np.sqrt(mu)) / (2 * np.pi))**(2/3)

    # 1. Posição no plano orbital (Coordenadas Perifocais)
    x_orb = a * (np.cos(m_anom) - e)
    y_orb = a * (np.sqrt(1 - e**2) * np.sin(m_anom))

    # 2. Transformação para ECEF (X, Y, Z terrestres)
    # Aplicando as matrizes de rotação combinadas
    cos_raan, sin_raan = np.cos(raan), np.sin(raan)
    cos_argp, sin_argp = np.cos(arg_p), np.sin(arg_p)
    cos_inc, sin_inc = np.cos(inc), np.sin(inc)

    df['X'] = (cos_raan * cos_argp - sin_raan * sin_argp * cos_inc) * x_orb + \
              (-cos_raan * sin_argp - sin_raan * cos_argp * cos_inc) * y_orb
              
    df['Y'] = (sin_raan * cos_argp + cos_raan * sin_argp * cos_inc) * x_orb + \
              (-sin_raan * sin_argp + cos_raan * cos_argp * cos_inc) * y_orb
              
    df['Z'] = (sin_argp * sin_inc) * x_orb + (cos_argp * sin_inc) * y_orb
    
    return df

def create_3d_map(df):
    df = prepare_3d_data(df)

    # Exemplo de órbita ou posição
    fig = go.Figure(data=[go.Scatter3d(
        x=df['x'], y=df['y'], z=df['z'],
        mode='markers',
        marker=dict(size=2, color=df['height'], colorscale='Viridis', opacity=0.8)
    )])
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            bgcolor='rgba(0,0,0,0)'
        )
    )
    return fig

def create_violin_plot(df):
    fig = go.Figure(data=go.Violin(
        y=df['height'],
        line_color='#ffccac',
        fillcolor='#3e647d',
        opacity=0.6,
        x0='Height'
    ))
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white"),
        yaxis=dict(showgrid=True, gridcolor='#3e647d')
    )
    return fig

def create_line_graph(df):
    # Exemplo: Lançamentos por Ano
    df_year = df.groupby('year').size().reset_index(name='counts')
    fig = go.Figure(data=go.Scatter(
        x=df_year['year'], 
        y=df_year['counts'],
        mode='lines+markers',
        line=dict(color='#fff4dd', width=3),
        marker=dict(size=6)
    ))
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white"),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='#3e647d')
    )
    return fig