import sys
import dash
from dash import Dash, html, dcc
import subprocess

# ============================================================
# PIPELINE DE DADOS
# ============================================================
def executar_pipeline():
    # Execucao do Jupyter Notebook
    print("⏳ Dataset merge...")
    # Executar notebook em background via nbconvert
    subprocess.run(["jupyter", "nbconvert", "--to", "notebook", "--execute", "scripts/datasets_merge.ipynb"])
    print("✅ Notebook done!\n")

    # Execucao do Script Python
    # print("TLE infos...")
    # Garantir execucao com o interpretador atual
    # subprocess.run([sys.executable, "scripts/add_tle_infos.py"])
    print("✅ Script done!\n")

# ============================================================
# INICIALIZACAO DA APLICACAO
# ============================================================
if __name__ == '__main__':
    args = sys.argv[1:]  # Capturar argumentos da linha de comando
    if '--update-data' in args:
        executar_pipeline()

    # Configuracao da aplicacao com navegacao multipagina
    app = Dash(
        __name__, 
        use_pages=True, 
        pages_folder='scripts', 
        suppress_callback_exceptions=True  # Supressao de avisos de callbacks
    )

    # ============================================================
    # ESTILOS E LAYOUT
    # ============================================================
    # Estilo base dos botoes
    button_style = {
        'padding': '10px 20px', 'margin': '10px', 'backgroundColor': '#00d4ff',
        'color': 'black', 'textDecoration': 'none', 'fontWeight': 'bold',
        'borderRadius': '5px', 'display': 'inline-block'
    }

    app.layout = html.Div(style={'backgroundColor': '#040b1a', 'minHeight': '100vh', 'color': 'white'}, children=[
        # Contentor de injecao de paginas Dash
        dash.page_container
    ])

    # Desativar reloader para evitar execucoes redundantes
    # app.run_server(debug=True, use_reloader=False)
    app.run(
        debug=True, 
        use_reloader=False, 
        dev_tools_hot_reload=False
    )