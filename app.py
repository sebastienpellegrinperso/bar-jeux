import os
import gspread
import pandas as pd
import streamlit as st

# Configuration de la page
st.set_page_config(
    page_title="Ludotrotter Bar", layout="wide", page_icon="🎲"
)

st.title("🎲 Ludotrotter Bar - Gestion de la Caisse et des Tables")


# Connexion directe et sécurisée (compatible local et Cloud Streamlit)
@st.cache_resource
def get_gsheet_client():
  if os.path.exists("service_account.json"):
    gc = gspread.service_account(filename="service_account.json")
  else:
    creds_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(creds_dict)

  sh = gc.open("Ludotrotter_Base_Donnees")
  return sh


try:
  sh = get_gsheet_client()
except Exception as e:
  st.error(
      f"Erreur de connexion au fichier Google Sheets (vérifie le partage avec"
      f" l'e-mail du robot) : {e}"
  )
  st.stop()

# --- CHARGEMENT DE LA CARTE DEPUIS GOOGLE SHEETS ---
try:
  worksheet_carte = sh.worksheet("Carte")
  data_carte = worksheet_carte.get_all_records()
  df_carte = pd.DataFrame(data_carte)
  carte_produits = {"": 0.0}
  for _, row in df_carte.iterrows():
    carte_produits[row["Produit"]] = row["Prix"]
except Exception as e:
  carte_produits = {
      "": 0.0,
      "Bière Blonde 33cl": 4.50,
      "Bière IPA 33cl": 5.00,
      "Sodas / Diabolo": 3.00,
      "Jus de fruits": 3.50,
      "Sirop à l'eau": 1.50,
      "Café / Thé": 2.20,
      "Paquet de chips": 2.00,
      "Planche apéro": 12.00,
  }

# --- CHARGEMENT DES TABLES ACTIVES DEPUIS GOOGLE SHEETS ---
if "tables" not in st.session_state:
  try:
    worksheet_tables = sh.worksheet("Tables_Actives")
    data_tables = worksheet_tables.get_all_records()

    tables_restaurees = {}
    for row in data_tables:
      nom = row.get("Table")
      prod = row.get("Produit", "")
      qte = int(row.get("QteCmd", 0) or 0)
      qte_reg = int(row.get("QteReglee", 0) or 0)

      if nom:
        if nom not in tables_restaurees:
          tables_restaurees[nom] = {"lignes": []}
        tables_restaurees[nom]["lignes"].append({
            "produit": prod,
            "qte": qte,
            "qte_reglee": qte_reg,
        })

    for nom in tables_restaurees:
      if not tables_restaurees[nom]["lignes"]:
        tables_restaurees[nom]["lignes"] = [
            {"produit": "", "qte": 0, "qte_reglee": 0} for _ in range(3)
        ]

    st.session_state.tables = tables_restaurees
  except Exception:
    st.session_state.tables = {}


# Fonction utilitaire pour sauvegarder l'état des tables dans Google Sheets
def sauvegarder_tables_dans_sheet():
  try:
    try:
      worksheet_tables = sh.worksheet("Tables_Actives")
    except Exception:
      worksheet_tables = sh.add_worksheet(
          title="Tables_Actives", rows=100, cols=5
      )

    lignes_a_sauver = [["Table", "Produit", "QteCmd", "QteReglee"]]
    for nom_table, table_data in st.session_state.tables.items():
      for ligne in table_data["lignes"]:
        lignes_a_sauver.append([
            nom_table,
            ligne["produit"],
            ligne["qte"],
            ligne["qte_reglee"],
        ])

    worksheet_tables.clear()
    worksheet_tables.update(lignes_a
