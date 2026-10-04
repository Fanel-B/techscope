import json
import os
import sqlite3

import pandas as pd

from datacheck import DataCheck

SEUIL_FAIBLE_USAGE = 0.30   # actifs / affectées en dessous de 30 %
JOURS_MAX_MAJ = 30

os.makedirs("output", exist_ok=True)
dc = DataCheck()

# 1. Chargement des 4 sources
with open("data/inventaire.json", encoding="utf-8") as f:
    serveurs = pd.DataFrame(json.load(f))

con = sqlite3.connect("data/referentiel.db")
services = pd.read_sql("SELECT * FROM services", con)
metiers = pd.read_sql("SELECT * FROM metiers", con)
usages = pd.read_sql("SELECT * FROM usages", con)
con.close()

licences = pd.read_csv("data/licences.csv")
historique = pd.read_csv("data/historique.csv")

nb_lignes = {"inventaire": len(serveurs), "usages": len(usages),
             "licences": len(licences), "historique": len(historique)}

# 2. Contrôles qualité
serveurs["ligne"] = [f"inventaire ligne {i}" for i in range(len(serveurs))]
serveurs = dc.champ_obligatoire(serveurs, "inventaire.json", "server_id", cle="ligne")
serveurs = dc.unicite(serveurs, "inventaire.json", "server_id")
serveurs = dc.integrite(serveurs, "inventaire.json", "service_id",
                        services["service_id"], "référentiel services", cle="server_id")
serveurs = dc.fraicheur(serveurs, "inventaire.json", "derniere_maj",
                        JOURS_MAX_MAJ, cle="server_id")

usages["ligne"] = usages["service_id"] + "/" + usages["metier_id"]
usages = dc.integrite(usages, "referentiel.db (usages)", "service_id",
                      services["service_id"], "référentiel services", cle="ligne")
usages = dc.integrite(usages, "referentiel.db (usages)", "metier_id",
                      metiers["metier_id"], "référentiel métiers", cle="ligne")
usages = dc.positif(usages, "referentiel.db (usages)", "volume_activite", cle="ligne")

licences["ligne"] = licences["produit"] + "/" + licences["metier_id"]
licences = dc.positif(licences, "licences.csv", "capacite", cle="ligne")
licences = dc.coherence(licences, "licences.csv", "affectees", "capacite", cle="ligne")
licences = dc.coherence(licences, "licences.csv", "actifs", "affectees", cle="ligne")

historique["ligne"] = historique["service_id"] + "/" + historique["mois"]
historique = dc.champ_obligatoire(historique, "historique.csv",
                                  "utilisateurs_actifs", cle="ligne")
historique = dc.integrite(historique, "historique.csv", "service_id",
                          services["service_id"], "référentiel services", cle="ligne")

anomalies = dc.rapport()

# 3. Indicateurs (calculés uniquement sur les données validées)
kpi_services = (serveurs.merge(services, on="service_id")
                .groupby(["service_id", "nom"])
                .agg(nb_serveurs=("server_id", "count"),
                     nb_prod=("environnement", lambda s: (s == "prod").sum()))
                .reset_index())
kpi_services["point_unique_defaillance"] = kpi_services["nb_serveurs"] == 1

kpi_licences = licences.copy()
kpi_licences["taux_affectation"] = (kpi_licences["affectees"] / kpi_licences["capacite"]).round(2)
kpi_licences["taux_utilisation"] = (kpi_licences["actifs"] / kpi_licences["affectees"]).round(2)
kpi_licences["licences_inutilisees"] = kpi_licences["affectees"] - kpi_licences["actifs"]
kpi_licences["faible_usage"] = kpi_licences["taux_utilisation"] < SEUIL_FAIBLE_USAGE

kpi_produits = (licences.groupby("produit")
                .agg(capacite=("capacite", "sum"), affectees=("affectees", "sum"),
                     actifs=("actifs", "sum"))
                .reset_index())
kpi_produits["taux_utilisation"] = (kpi_produits["actifs"] / kpi_produits["affectees"]).round(2)
kpi_produits["licences_inutilisees"] = kpi_produits["affectees"] - kpi_produits["actifs"]

kpi_evolution = (historique.groupby("mois")["utilisateurs_actifs"].sum()
                 .reset_index())

# 4. Chargement dans SQLite + exports pour Power BI
if os.path.exists("output/techscope.db"):
    os.remove("output/techscope.db")
sortie = sqlite3.connect("output/techscope.db")
tables = {
    "serveurs": serveurs.drop(columns="ligne"), "services": services, "metiers": metiers,
    "usages": usages.drop(columns="ligne"), "licences": licences.drop(columns="ligne"),
    "historique": historique.drop(columns="ligne"),
    "kpi_services": kpi_services, "kpi_licences": kpi_licences.drop(columns="ligne"),
    "kpi_produits": kpi_produits, "kpi_evolution": kpi_evolution,
    "anomalies": anomalies,
}
for nom, df in tables.items():
    df.to_sql(nom, sortie, index=False)
    df.to_csv(f"output/{nom}.csv", index=False, encoding="utf-8-sig")
sortie.close()

# 5. Petit rapport HTML
nb_rejetes = anomalies[anomalies["gravite"] == "erreur"]["ligne"].nunique()
faibles = kpi_licences[kpi_licences["faible_usage"]][
    ["produit", "metier_id", "affectees", "actifs", "taux_utilisation"]]
spof = kpi_services[kpi_services["point_unique_defaillance"]][["service_id", "nom"]]

html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>TechScope - rapport</title>
<style>body{{font-family:Arial,sans-serif;max-width:900px;margin:30px auto;color:#222}}
h1,h2{{color:#1f3864}}table{{border-collapse:collapse;margin-bottom:20px}}
td,th{{border:1px solid #ccc;padding:4px 10px;font-size:14px}}th{{background:#eef2f8}}</style>
</head><body>
<h1>TechScope - rapport d'exécution</h1>
<p>Données fictives générées pour la démonstration.</p>
<h2>Qualité des données</h2>
<p>{sum(nb_lignes.values())} lignes lues, {len(anomalies)} anomalies détectées
({nb_rejetes} lignes écartées des indicateurs).</p>
{anomalies.to_html(index=False)}
<h2>Constats métier (ce ne sont pas des erreurs de données)</h2>
<h3>Licences à faible usage (&lt; {int(SEUIL_FAIBLE_USAGE * 100)} % des licences affectées utilisées)</h3>
{faibles.to_html(index=False)}
<h3>Services sans redondance (un seul serveur)</h3>
{spof.to_html(index=False)}
<h2>Utilisation des licences par produit</h2>
{kpi_produits.to_html(index=False)}
</body></html>"""
with open("output/rapport.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"{sum(nb_lignes.values())} lignes lues, {len(anomalies)} anomalies, "
      f"{nb_rejetes} lignes écartées")
print("Exports dans output/ (CSV, techscope.db, rapport.html)")
