import dash
from dash import Dash, html, dcc

# O parâmetro use_pages=True é a magia que ativa a navegação
app = Dash(
    __name__, 
    use_pages=True, 
    pages_folder='scripts', 
    suppress_callback_exceptions=True  # ISTO TIRA UM WARNING Q ESTAVA A APARECER
)

# Estilo simples para os botões parecerem botões e não links normais
button_style = {
    'padding': '10px 20px', 'margin': '10px', 'backgroundColor': '#00d4ff',
    'color': 'black', 'textDecoration': 'none', 'fontWeight': 'bold',
    'borderRadius': '5px', 'display': 'inline-block'
}

app.layout = html.Div(style={'backgroundColor': '#040b1a', 'minHeight': '100vh', 'color': 'white'}, children=[
    # O contentor onde o Dash vai injetar os teus dois dashboards
    dash.page_container
])

if __name__ == '__main__':
    app.run_server(debug=True)