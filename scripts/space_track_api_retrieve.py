import requests
import pandas as pd
import io
import configparser
import time

def get_spacetrack_data(configUsr, configPwd, uriBase, requestLogin, requestAllGP):
    with requests.Session() as session:
        # 1. Login
        siteCred = {'identity': configUsr, 'password': configPwd}
        resp = session.post(uriBase + requestLogin, data=siteCred)
        
        if resp.status_code != 200:
            print("Erro no Login. Verifica as credenciais no .ini")
            return None

        # 2. Request de Dados (Todos os objetos)
        print("A descarregar catálogo completo do Space-Track... (Aguarde)")
        resp = session.get(uriBase + requestAllGP)
        
        if resp.status_code == 200:
            # Transformar o texto CSV diretamente num DataFrame
            df = pd.read_csv(io.StringIO(resp.text))
            print(f"Sucesso! {len(df)} objetos carregados.")
            return df
        else:
            print(f"Erro no download: {resp.status_code}")
            return None

def load_config():
    # --- CONFIGURAÇÃO ---
    config = configparser.ConfigParser()
    config.read("./SLTrack.ini")
    configUsr = config.get("configuration", "username")
    configPwd = config.get("configuration", "password")

    uriBase = "https://www.space-track.org"
    requestLogin = "/ajaxauth/login"

    # Esta query pede os dados GP (General Perturbations) mais recentes de TODOS os objetos
    # format/csv é o mais eficiente para processar milhares de linhas
    requestAllGP = "/basicspacedata/query/class/gp/format/csv"
    return configUsr, configPwd, uriBase, requestLogin, requestAllGP

def main():
    configUsr, configPwd, uriBase, requestLogin, requestAllGP = load_config()
    # --- EXECUÇÃO ---
    combined_df = get_spacetrack_data(configUsr, configPwd, uriBase, requestLogin, requestAllGP)

    if combined_df is not None:
        # Selecionar as colunas críticas para o teu 3D
        cols_interesse = [
            'OBJECT_NAME', 'NORAD_CAT_ID', 'INCLINATION', 'PERIOD', 
            'APOGEE', 'PERIGEE', 'RA_OF_ASC_NODE', 'ARG_OF_PERICENTER', 
            'MEAN_ANOMALY', 'ECCENTRICITY', 'MEAN_MOTION', 'EPOCH'
        ]
        # Filtramos apenas as que existem (segurança)
        cols_existentes = [c for c in cols_interesse if c in combined_df.columns]
        df_final = combined_df[cols_existentes].copy()
        
        # Guardar localmente para não teres de fazer request à API toda a hora (evita o ban)
        df_final.to_csv('../DATASETS_SATTELITES/spacetrack_last_data_tle.csv', index=False)
        print("Dados guardados em 'spacetrack_last_data_tle.csv'")