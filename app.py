import base64
import json
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
@st.cache_resource
def get_gsheet_client():
  if os.path.exists("service_account.json"):
    gc = gspread.service_account(filename="service_account.json")
  else:
    secrets = st.secrets["gcp_service_account"]
    
    # Reconstitution propre du dictionnaire de credentials à partir du tableau de lignes
    creds_dict = {
        "type": secrets["type"],
        "project_id": secrets["project_id"],
        "private_key_id": secrets["private_key_id"],
        "private_key": "\n".join(secrets["private_key_lines"]),
        "client_email": secrets["client_email"],
        "client_id": secrets["client_id"],
        "auth_uri": secrets["auth_uri"],
        "token_uri": secrets["token_uri"],
        "auth_provider_x509_cert_url": secrets["auth_provider_x509_cert_url"],
        "client_x509_cert_url": secrets["client_x509_cert_url"],
        "universe_domain": secrets["universe_domain"],
    }
    
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
    worksheet_tables.update(lignes_a_sauver)
  except Exception as e:
    st.warning(f"Impossible de sauvegarder les tables dans le cloud : {e}")


if "total_jour" not in st.session_state:
  st.session_state.total_jour = 0.0

if "mode_ajout_table" not in st.session_state:
  st.session_state.mode_ajout_table = False

# --- 2. BARRE LATÉRALE : CAISSE ET ACTIONS GLOBALES ---
with st.sidebar:
  st.header("📊 Caisse & Administration")
  st.metric(
      label="Total du jour", value=f"{st.session_state.total_jour:.2f} €"
  )

  st.divider()

  if st.button("➕ Ajouter une table", use_container_width=True):
    st.session_state.mode_ajout_table = True

  st.divider()
  confirmation_reset = st.checkbox("Je veux tout réinitialiser")
  if st.button("🔄 Reset Global de la journée"):
    if confirmation_reset:
      st.session_state.tables = {}
      st.session_state.total_jour = 0.0
      st.session_state.mode_ajout_table = False
      sauvegarder_tables_dans_sheet()
      st.success("Réinitialisation globale effectuée !")
      st.rerun()
    else:
      st.warning("Cochez la case pour valider.")

# --- 3. NAVIGATION PAR ONGLETS (Tables vs Carte) ---
onglet_tables, onglet_carte = st.tabs(
    ["🪑 Gestion des Tables", "📜 Gestion de la Carte & des Prix"]
)

# ==========================================
# ONGLET 1 : GESTION DES TABLES
# ==========================================
with onglet_tables:
  if st.session_state.mode_ajout_table:
    with st.container(border=True):
      st.subheader("Ouvrir une nouvelle table")
      nom_table_saisi = st.text_input(
          "Nom ou numéro de la table (ex: Table 1, Terrasse, Paul...) :"
      )

      c_ins1, c_ins2 = st.columns(2)
      with c_ins1:
        if st.button("Valider l'ajout", use_container_width=True):
          if nom_table_saisi.strip():
            if nom_table_saisi in st.session_state.tables:
              st.error("Cette table existe déjà !")
            else:
              st.session_state.tables[nom_table_saisi] = {
                  "lignes": [
                      {"produit": "", "qte": 0, "qte_reglee": 0} for _ in range(3)
                  ],
              }
              st.session_state.mode_ajout_table = False
              sauvegarder_tables_dans_sheet()
              st.rerun()
          else:
            st.error("Veuillez saisir un nom ou un numéro valide.")
      with c_ins2:
        if st.button("Annuler", use_container_width=True):
          st.session_state.mode_ajout_table = False
          st.rerun()

  noms_tables = list(st.session_state.tables.keys())
  produits_liste = list(carte_produits.keys())

  if not noms_tables and not st.session_state.mode_ajout_table:
    st.info(
        "📭 Aucune table active pour le moment. Cliquez sur **'➕ Ajouter une"
        " table'** dans la barre latérale pour commencer."
    )

  for i in range(0, len(noms_tables), 2):
    col1, col2 = st.columns(2)
    paire_tables = noms_tables[i : i + 2]

    for idx_col, nom_table in enumerate(paire_tables):
      col_actuelle = col1 if idx_col == 0 else col2
      table_data = st.session_state.tables[nom_table]

      with col_actuelle:
        with st.container(border=True):
          st.markdown(f"### 🪑 **{nom_table}**")

          h1, h2, h3, h4, h5 = st.columns([3, 1.2, 1.2, 1, 1])
          h1.caption("**Produit**")
          h2.caption("**Qté Cmd**")
          h3.caption("**Qté Payée**")
          h4.caption("**Prix U**")
          h5.caption("**Reste**")

          total_table_global = 0.0
          total_deja_regle = 0.0

          for idx, ligne in enumerate(table_data["lignes"]):
            cc1, cc2, cc3, cc4, cc5 = st.columns([3, 1.2, 1.2, 1, 1])

            with cc1:
              prod_actuel = ligne["produit"]
              if prod_actuel not in produits_liste:
                prod_actuel = ""

              produit_choisi = st.selectbox(
                  f"Produit {idx+1} ({nom_table})",
                  produits_liste,
                  index=produits_liste.index(prod_actuel)
                  if prod_actuel in produits_liste
                  else 0,
                  key=f"prod_{nom_table}_{idx}",
                  label_visibility="collapsed",
              )

            with cc2:
              qte_choisie = st.number_input(
                  f"Qté Cmd {idx+1} ({nom_table})",
                  min_value=0,
                  max_value=20,
                  value=ligne["qte"],
                  key=f"qte_{nom_table}_{idx}",
                  label_visibility="collapsed",
              )

            qte_reglee_max = max(0, qte_choisie)
            qte_reglee_actuelle = min(
                ligne.get("qte_reglee", 0), qte_reglee_max
            )

            with cc3:
              qte_reglee = st.number_input(
                  f"Qté Payée {idx+1} ({nom_table})",
                  min_value=0,
                  max_value=qte_reglee_max,
                  value=qte_reglee_actuelle,
                  key=f"qtereg_{nom_table}_{idx}",
                  label_visibility="collapsed",
              )

            table_data["lignes"][idx]["produit"] = produit_choisi
            table_data["lignes"][idx]["qte"] = qte_choisie
            table_data["lignes"][idx]["qte_reglee"] = qte_reglee

            prix_u = carte_produits.get(produit_choisi, 0.0)
            total_ligne = qte_choisie * prix_u
            paye_ligne = qte_reglee * prix_u
            reste_ligne = total_ligne - paye_ligne

            total_table_global += total_ligne
            total_deja_regle += paye_ligne

            with cc4:
              st.write(f"{prix_u:.2f}€")
            with cc5:
              st.write(f"**{reste_ligne:.2f}€**")

          sauvegarder_tables_dans_sheet()

          if len(table_data["lignes"]) < 10:
            if st.button(
                "➕ Ligne",
                key=f"add_line_{nom_table}",
                use_container_width=True,
            ):
              table_data["lignes"].append(
                  {"produit": "", "qte": 0, "qte_reglee": 0}
              )
              sauvegarder_tables_dans_sheet()
              st.rerun()

          reste_a_payer_total = total_table_global - total_deja_regle

          st.markdown("---")
          r1, r2, r3 = st.columns(3)
          r1.metric("Total Cmd", f"{total_table_global:.2f} €")
          r2.metric("Déjà Réglé", f"{total_deja_regle:.2f} €")
          r3.metric("Reste à Payer", f"{reste_a_payer_total:.2f} €")

          b1, b2 = st.columns(2)
          with b1:
            if st.button(
                "✅ Solder / Fermer table",
                key=f"payer_{nom_table}",
                use_container_width=True,
            ):
              st.session_state.total_jour += total_table_global
              del st.session_state.tables[nom_table]
              sauvegarder_tables_dans_sheet()
              st.rerun()

          with b2:
            if st.button(
                "🔄 Vider", key=f"vider_{nom_table}", use_container_width=True
            ):
              del st.session_state.tables[nom_table]
              sauvegarder_tables_dans_sheet()
              st.rerun()


# ==========================================
# ONGLET 2 : GESTION DE LA CARTE ET DES PRIX
# ==========================================
with onglet_carte:
  st.subheader("📜 Modifier la carte et les tarifs")
  st.markdown(
      "Les modifications faites ici sont enregistrées durablement dans la"
      " base Google Sheets."
  )

  produits_modifies = {
      k: v for k, v in carte_produits.items() if k != ""
  }
  produits_a_supprimer = []

  for prod, prix in list(produits_modifies.items()):
    col_p1, col_p2, col_p3 = st.columns([3, 2, 1])
    with col_p1:
      st.write(f"**{prod}**")
    with col_p2:
      nouveau_prix = st.number_input(
          f"Prix {prod}",
          min_value=0.0,
          max_value=100.0,
          value=float(prix),
          step=0.5,
          key=f"prix_mod_{prod}",
          label_visibility="collapsed",
      )
      produits_modifies[prod] = nouveau_prix
    with col_p3:
      if st.button("🗑️ Supprimer", key=f"del_prod_{prod}"):
        produits_a_supprimer.append(prod)

  if produits_a_supprimer:
    for p in produits_a_supprimer:
      del produits_modifies[p]

    df_to_save = pd.DataFrame(
        list(produits_modifies.items()), columns=["Produit", "Prix"]
    )
    worksheet_carte.clear()
    worksheet_carte.update(
        [df_to_save.columns.values.tolist()] + df_to_save.values.tolist()
    )
    st.success("Mise à jour enregistrée !")
    st.rerun()

  if st.button("💾 Enregistrer les modifications de prix"):
    df_to_save = pd.DataFrame(
        list(produits_modifies.items()), columns=["Produit", "Prix"]
    )
    worksheet_carte.clear()
    worksheet_carte.update(
        [df_to_save.columns.values.tolist()] + df_to_save.values.tolist()
    )
    st.success("Modifications de prix enregistrées avec succès dans le cloud !")
    st.rerun()

  st.divider()

  st.subheader("➕ Ajouter un nouveau produit")
  with st.form("form_ajout_produit"):
    c_np1, c_np2 = st.columns([3, 2])
    with c_np1:
      nouveau_nom = st.text_input("Nom du produit (ex: Cidre 33cl)")
    with c_np2:
      nouveau_tarif = st.number_input(
          "Prix (€)", min_value=0.0, max_value=100.0, value=3.00, step=0.5
      )

    submitted = st.form_submit_button("Ajouter à la carte")
    if submitted:
      if nouveau_nom.strip():
        nom_propre = nouveau_nom.strip()
        if nom_propre in produits_modifies:
          st.warning("Ce produit existe déjà.")
        else:
          produits_modifies[nom_propre] = nouveau_tarif
          df_to_save = pd.DataFrame(
              list(produits_modifies.items()), columns=["Produit", "Prix"]
          )
          worksheet_carte.clear()
          worksheet_carte.update(
              [df_to_save.columns.values.tolist()]
              + df_to_save.values.tolist()
          )
          st.success(f"Produit '{nom_propre}' ajouté et sauvegardé !")
          st.rerun()
      else:
        st.error("Veuillez indiquer un nom de produit valide.")
