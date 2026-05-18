import sys
import dash
from dash import Dash, html, dcc
import subprocess

def executar_pipeline():
    # 1. Correr o Jupyter Notebook
    print("⏳ Dataset merge...")
    # O comando nbconvert permite correr um notebook por trás, sem abrir a janela
    subprocess.run(["jupyter", "nbconvert", "--to", "notebook", "--execute", "scripts/datasets_merge.ipynb"])
    print("✅ Notebook done!\n")

    # 2. Correr o Script Python
    # print("⏳ TLE infos...")
    # sys.executable garante que usa o mesmo interpretador de Python
    # subprocess.run([sys.executable, "scripts/add_tle_infos.py"])
    print("✅ Script done!\n")

if __name__ == '__main__':
    args = sys.argv[1:]  # Pega os argumentos passados na linha de comando, ignorando o nome do script
    if '--update-data' in args:
        executar_pipeline()

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
        # O contentor onde o Dash vai injetar os dois dashboards
        dash.page_container
    ])

    # realoader falso para nao rodar sempre o dataset_merge cada vez que fazemos uma alteração
    # app.run_server(debug=True, use_reloader=False)
    app.run(
        debug=True, 
        use_reloader=False, 
        dev_tools_hot_reload=False
    )