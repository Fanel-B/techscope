"""Vérifie que chaque anomalie volontaire est détectée, et que le faible usage n'est pas traité comme une erreur."""
import subprocess
import sys

import pandas as pd

subprocess.run([sys.executable, "generate_data.py"], check=True)
subprocess.run([sys.executable, "run_pipeline.py"], check=True)

a = pd.read_csv("output/anomalies.csv")


def present(source, regle, mot_detail=""):
    f = a[(a["source"].str.contains(source, regex=False)) & (a["regle"] == regle)
          & (a["detail"].str.contains(mot_detail, regex=False))]
    return len(f) >= 1


attendus = [
    ("inventaire", "champ obligatoire", "server_id"),
    ("inventaire", "unicité", ""),
    ("inventaire", "intégrité référentielle", "S99"),
    ("inventaire", "fraîcheur", ""),
    ("usages", "intégrité référentielle", "S99"),
    ("usages", "valeur invalide", "volume_activite"),
    ("licences", "valeur invalide", "capacite"),
    ("licences", "cohérence", "affectees > capacite"),
    ("licences", "cohérence", "actifs > affectees"),
    ("historique", "champ obligatoire", "utilisateurs_actifs"),
    ("historique", "intégrité référentielle", "S98"),
]

ko = [x for x in attendus if not present(*x)]
for x in attendus:
    print("OK " if x not in ko else "KO ", x)

fraicheur = a[a["regle"] == "fraîcheur"]
assert (fraicheur["gravite"] == "avertissement").all(), "la fraîcheur doit rester un avertissement"
assert len(fraicheur) == 2

k = pd.read_csv("output/kpi_licences.csv")
assert k["faible_usage"].sum() == 1, "un seul cas de faible usage attendu"
assert not a["ligne"].astype(str).str.contains("Outil ETL/M5").any(), \
    "le faible usage ne doit pas apparaître dans les anomalies"

s = pd.read_csv("output/kpi_services.csv")
assert set(s[s["point_unique_defaillance"]]["service_id"]) == {"S05", "S08"}

assert not ko, f"anomalies non détectées : {ko}"
print("Tous les tests passent")
