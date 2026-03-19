import pandas as pd
import os
from datetime import datetime

def main(path, path_cel, path_jon, new_file_name):
    df = pd.read_csv(path + "merged_dataset.csv")

    ######################################################
    # RETRIEVE UPDATED DATA FROM CELESTRACK AND SPACETRACK
    ######################################################
        #### CELESTRACK ####
    print("\n--- DOWNLOAD FROM CELESTRAK ---")
    needs_download = True
    if os.path.exists(path_cel):
        file_mod_time = os.path.getmtime(path_cel)
        file_date = datetime.fromtimestamp(file_mod_time).date()
        today = datetime.now().date()

        if file_date == today:
            print(f"File '{path_cel}' is up to date ({file_date}). Reading locally...")
            df_cel = pd.read_csv(path_cel)
            needs_download = False
        else:
            print(f"File '{path_cel}' is outdated ({file_date}).")
    else:
        print(f"File '{path_cel}' not found.")

    if needs_download:
        print("Downloading new data from Celestrak...")
        try:
            df_cel = pd.read_csv("https://celestrak.org/pub/satcat.csv")
            # Salva o CSV completo para garantir que temos todas as colunas no disco
            df_cel.to_csv(path_cel, index=False)
            print("Celestrak data downloaded and saved successfully.")
        except Exception as e:
            print(f"Error downloading data: {e}")
            return

        #### SPACETRACK ####
    # print("\n--- DOWNLOAD SPACETRACK ---")
    # df_spa = pd.read_csv(path + "spacetrack_Full_Catalog.csv")
    
    # if df_spa.empty:
    #     print("Error: Failed to download data from Spacetrack.")
    #     return
    # print("Spacetrack data downloaded successfully. Number of records:", len(df_spa))

    #######################################################
    ######## MERGE DATAFRAMES #############################
    #######################################################
    df_cel = df_cel[["NORAD_CAT_ID", "PERIOD", "INCLINATION", "APOGEE", "PERIGEE", "RCS", "DATA_STATUS_CODE", "ORBIT_CENTER", "ORBIT_TYPE"]]
    df["NORAD_CAT_ID"] = df["NORAD_CAT_ID"].astype('Int64')

    df_merged = df.merge(df_cel, left_on="NORAD_CAT_ID", right_on="NORAD_CAT_ID", how="left")
    # df_merged.drop(columns=["NORAD_CAT_ID"], inplace=True)
    # df_merged = df_merged.merge(df_jon, left_on="NORAD_CAT_ID", right_on="NORAD_CAT_ID", how="left")

    df_merged.to_csv(path + f"{new_file_name}.csv", index=False)
    print(f"\n--- Data merged and saved to '{new_file_name}.csv' ---")


if __name__ == "__main__":
    path = "../DATASETS_SATTELITES/"
    path_cel = os.path.join(path, "celestrack/celestrak_data_api.csv")
    path_jon = ""
    new_file_name = "merged_dataset_tle"
    main(path, path_cel, path_jon, new_file_name)