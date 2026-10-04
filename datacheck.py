from datetime import date

import pandas as pd


class DataCheck:
    """Contrôles qualité. Chaque contrôle renvoie les lignes valides
    et note les lignes rejetées avec la raison dans self.anomalies."""

    def __init__(self, aujourdhui=None):
        self.anomalies = []
        self.aujourdhui = aujourdhui or date.today()

    def _noter(self, df, source, regle, detail, gravite="erreur", cle=None):
        for idx, row in df.iterrows():
            ident = row[cle] if cle else idx
            self.anomalies.append({
                "source": source,
                "ligne": ident,
                "regle": regle,
                "detail": detail,
                "gravite": gravite,
            })

    def champ_obligatoire(self, df, source, colonne, cle=None):
        manquant = df[colonne].isna()
        self._noter(df[manquant], source, "champ obligatoire",
                    f"{colonne} manquant", cle=cle)
        return df[~manquant]

    def unicite(self, df, source, colonne):
        doublon = df.duplicated(subset=colonne, keep="first")
        self._noter(df[doublon], source, "unicité",
                    f"{colonne} en doublon", cle=colonne)
        return df[~doublon]

    def integrite(self, df, source, colonne, reference, nom_ref, cle=None):
        inconnu = ~df[colonne].isin(reference)
        for idx, row in df[inconnu].iterrows():
            self.anomalies.append({
                "source": source,
                "ligne": row[cle] if cle else idx,
                "regle": "intégrité référentielle",
                "detail": f"{colonne} '{row[colonne]}' absent de {nom_ref}",
                "gravite": "erreur",
            })
        return df[~inconnu]

    def positif(self, df, source, colonne, cle=None):
        negatif = df[colonne] < 0
        self._noter(df[negatif], source, "valeur invalide",
                    f"{colonne} négatif", cle=cle)
        return df[~negatif]

    def coherence(self, df, source, petit, grand, cle=None):
        """Vérifie que petit <= grand (ex. affectées <= capacité)."""
        incoherent = df[petit] > df[grand]
        self._noter(df[incoherent], source, "cohérence",
                    f"{petit} > {grand}", cle=cle)
        return df[~incoherent]

    def fraicheur(self, df, source, colonne_date, jours_max=30, cle=None):
        """Les lignes périmées sont gardées mais signalées (avertissement)."""
        age = (pd.Timestamp(self.aujourdhui) - pd.to_datetime(df[colonne_date])).dt.days
        perime = age > jours_max
        for idx, row in df[perime].iterrows():
            self.anomalies.append({
                "source": source,
                "ligne": row[cle] if cle else idx,
                "regle": "fraîcheur",
                "detail": f"dernière mise à jour il y a {age[idx]} jours (> {jours_max})",
                "gravite": "avertissement",
            })
        return df

    def rapport(self):
        return pd.DataFrame(self.anomalies,
                            columns=["source", "ligne", "regle", "detail", "gravite"])
