import json
import os
import random
import sqlite3
from datetime import date, timedelta

import pandas as pd

random.seed(42)
os.makedirs("data", exist_ok=True)

metiers = {"M1": "Finance", "M2": "RH", "M3": "Risques",
           "M4": "Marketing", "M5": "Conformité", "M6": "Logistique"}
services = {"S01": "ETL Core", "S02": "Datalake", "S03": "Reporting BI", "S04": "API Gateway",
            "S05": "Data Catalog", "S06": "Scheduler", "S07": "Data Quality", "S08": "Archivage"}

# inventaire des serveurs (JSON)
aujourdhui = date.today()
serveurs = []
n = 1
for sid in services:
    # S05 et S08 n'ont qu'un seul serveur (point de défaillance unique)
    nb = 1 if sid in ("S05", "S08") else random.randint(2, 3)
    for _ in range(nb):
        serveurs.append({
            "server_id": f"SRV{n:03d}",
            "environnement": random.choice(["prod", "prod", "preprod", "dev"]),
            "etat": random.choice(["actif", "actif", "actif", "maintenance"]),
            "service_id": sid,
            "derniere_maj": (aujourdhui - timedelta(days=random.randint(0, 20))).isoformat(),
        })
        n += 1

# anomalies volontaires (ajoutées en plus, pour ne pas fausser les services réels)
modele = dict(serveurs[2])
serveurs.append({**modele, "server_id": None})       # identifiant manquant
serveurs.append(dict(serveurs[4]))                   # doublon
serveurs.append({**modele, "server_id": "SRV900", "service_id": "S99"})  # service inexistant
for i in (8, 9):                                     # sources pas à jour
    serveurs[i]["derniere_maj"] = (aujourdhui - timedelta(days=75)).isoformat()

with open("data/inventaire.json", "w", encoding="utf-8") as f:
    json.dump(serveurs, f, ensure_ascii=False, indent=2)

# référentiel des usages (SQLite)
if os.path.exists("data/referentiel.db"):
    os.remove("data/referentiel.db")
con = sqlite3.connect("data/referentiel.db")
con.execute("CREATE TABLE services (service_id TEXT PRIMARY KEY, nom TEXT)")
con.execute("CREATE TABLE metiers (metier_id TEXT PRIMARY KEY, nom TEXT)")
con.execute("CREATE TABLE usages (service_id TEXT, metier_id TEXT, volume_activite INTEGER)")
con.executemany("INSERT INTO services VALUES (?, ?)", services.items())
con.executemany("INSERT INTO metiers VALUES (?, ?)", metiers.items())

usages = []
for sid in services:
    for mid in random.sample(list(metiers), random.randint(2, 4)):
        usages.append([sid, mid, random.randint(100, 5000)])
usages.append(["S99", "M2", 800])                    # service inexistant
usages[3][2] = -50                                   # volume négatif
con.executemany("INSERT INTO usages VALUES (?, ?, ?)", usages)
con.commit()
con.close()

# licences (CSV), modèle simple : licences par utilisateur
produits = ["Outil ETL", "Suite BI", "Catalogue de données"]
lignes = []
for produit in produits:
    for mid in metiers:
        capacite = random.choice([20, 30, 50, 80, 100])
        affectees = int(capacite * random.uniform(0.6, 1.0))
        actifs = int(affectees * random.uniform(0.3, 0.95))
        lignes.append({"produit": produit, "metier_id": mid, "capacite": capacite,
                       "affectees": affectees, "actifs": actifs})

lignes[2]["affectees"] = lignes[2]["capacite"] + 15  # affectations > capacité
lignes[7]["capacite"] = -10                          # valeur négative
lignes[11]["actifs"] = lignes[11]["affectees"] + 5   # plus d'actifs que d'affectées
lignes[4]["actifs"] = int(lignes[4]["affectees"] * 0.15)  # faible usage : pas une erreur
pd.DataFrame(lignes).to_csv("data/licences.csv", index=False)

# historique d'usage mensuel (CSV)
mois = [f"2026-{m:02d}" for m in range(4, 10)]
hist = []
for sid in services:
    base = random.randint(60, 300)
    for i, m in enumerate(mois):
        hist.append({"mois": m, "service_id": sid,
                     "utilisateurs_actifs": base + i * random.randint(0, 15)})
hist[10]["utilisateurs_actifs"] = None               # valeur manquante
hist.append({"mois": "2026-09", "service_id": "S98", "utilisateurs_actifs": 40})  # service inexistant
pd.DataFrame(hist).to_csv("data/historique.csv", index=False)

print("Données générées dans data/")
