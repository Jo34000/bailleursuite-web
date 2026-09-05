#!/usr/bin/env python3
"""Indices de référence des loyers (IRL) — table figée et publication.

L'app iOS s'en sert pour calculer des révisions de loyer. Une valeur
fausse produit une révision illégale : la table est donc saisie à la
main depuis la publication INSEE, jamais devinée ni interpolée, et
tout est vérifié avant écriture.

L'INSEE publie un nouvel indice à la mi-janvier, mi-avril, mi-juillet
et mi-octobre. Mise à jour : ajouter la ligne dans INDICES, relancer

    python3 tools/irl.py --ecrire

Le contrôle refuse un trimestre manquant, un doublon, un désordre
chronologique, une variation annuelle aberrante ou une couverture
inférieure à cinq ans.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "irl" / "v1" / "indices.json"

SCHEMA = "irl-1"
SOURCE = {
    "organisme": "INSEE",
    "libelle": "Indice de référence des loyers (IRL) — base 100 au 4e trimestre 1998",
    "identifiant_serie": "001515333",
    "page": "https://www.insee.fr/fr/statistiques/serie/001515333",
    "licence": "Licence Ouverte 2.0",
    "licence_url": "https://www.etalab.gouv.fr/licence-ouverte-open-licence/",
}

# (année, trimestre, valeur) — relevés sur la page INSEE ci-dessus.
# Ordre chronologique croissant. NE RIEN INTERPOLER : un trimestre
# non publié doit être absent, pas estimé.
INDICES: list[tuple[int, int, float]] = [
    # 2018
    (2018, 2, 127.77),
    (2018, 3, 128.45),
    (2018, 4, 129.03),
    # 2019
    (2019, 1, 129.38),
    (2019, 2, 129.72),
    (2019, 3, 129.99),
    (2019, 4, 130.26),
    # 2020
    (2020, 1, 130.57),
    (2020, 2, 130.57),
    (2020, 3, 130.59),
    (2020, 4, 130.52),
    # 2021
    (2021, 1, 130.69),
    (2021, 2, 131.12),
    (2021, 3, 131.67),
    (2021, 4, 132.62),
    # 2022
    (2022, 1, 133.93),
    (2022, 2, 135.84),
    (2022, 3, 136.27),
    (2022, 4, 137.26),
    # 2023
    (2023, 1, 138.61),
    (2023, 2, 140.59),
    (2023, 3, 141.03),
    (2023, 4, 142.06),
    # 2024
    (2024, 1, 143.46),
    (2024, 2, 145.17),
    (2024, 3, 144.51),
    (2024, 4, 144.64),
    # 2025
    (2025, 1, 145.47),
    (2025, 2, 146.68),
    (2025, 3, 145.77),
    (2025, 4, 145.78),
    # 2026
    (2026, 1, 146.60),
    (2026, 2, 148.37),
]

# Couverture minimale : une révision peut porter sur un indice ancien,
# le bail fixant le trimestre de référence à sa signature.
TRIMESTRES_MINIMUM = 20

# Garde-fou de saisie. L'IRL varie de quelques pour cent par an ; une
# variation annuelle au-delà de cette borne signale une coquille
# (chiffre transposé, virgule déplacée) bien avant qu'elle n'atterrisse
# dans un calcul de révision.
VARIATION_ANNUELLE_MAX_PCT = 8.0


class Anomalie(Exception):
    """Erreur qui doit arrêter la publication plutôt que produire un fichier faux."""


def cle(annee: int, trimestre: int) -> int:
    return annee * 4 + (trimestre - 1)


def verifier(indices: list[tuple[int, int, float]]) -> list[str]:
    erreurs: list[str] = []
    if not indices:
        return ["table vide : renseigner INDICES depuis la publication INSEE"]

    vus: dict[tuple[int, int], float] = {}
    for annee, trimestre, valeur in indices:
        if trimestre not in (1, 2, 3, 4):
            erreurs.append(f"{annee}-T{trimestre} : trimestre hors de 1-4")
        if (annee, trimestre) in vus:
            erreurs.append(f"{annee}-T{trimestre} : trimestre en double")
        if valeur <= 0:
            erreurs.append(f"{annee}-T{trimestre} : valeur {valeur} non positive")
        vus[(annee, trimestre)] = valeur

    # Ordre chronologique strict
    cles = [cle(a, t) for a, t, _ in indices]
    if cles != sorted(cles):
        erreurs.append("la table n'est pas en ordre chronologique croissant")

    # Aucun trou : l'app cherche un trimestre précis, un trou la ferait
    # échouer silencieusement ou retomber sur le mauvais indice.
    for precedent, suivant in zip(cles, cles[1:]):
        if suivant - precedent != 1:
            manquants = suivant - precedent - 1
            erreurs.append(
                f"{manquants} trimestre(s) manquant(s) entre "
                f"{precedent // 4}-T{precedent % 4 + 1} et "
                f"{suivant // 4}-T{suivant % 4 + 1}")

    if len(indices) < TRIMESTRES_MINIMUM:
        erreurs.append(f"{len(indices)} trimestres publiés pour "
                       f"{TRIMESTRES_MINIMUM} attendus au minimum "
                       f"({TRIMESTRES_MINIMUM // 4} ans)")

    # Variation d'une année sur l'autre, à trimestre égal
    for annee, trimestre, valeur in indices:
        ancien = vus.get((annee - 1, trimestre))
        if ancien is None:
            continue
        variation = (valeur - ancien) / ancien * 100
        if abs(variation) > VARIATION_ANNUELLE_MAX_PCT:
            erreurs.append(
                f"{annee}-T{trimestre} : {variation:+.2f} % sur un an "
                f"({ancien} → {valeur}), au-delà des "
                f"{VARIATION_ANNUELLE_MAX_PCT} % attendus — vérifier la saisie")
    return erreurs


def construire(indices: list[tuple[int, int, float]]) -> dict:
    maintenant = datetime.now(ZoneInfo("Europe/Paris")).replace(microsecond=0)
    dernier = indices[-1]
    return {
        "schema": SCHEMA,
        "genere_le": maintenant.isoformat(),
        "source": SOURCE,
        "avertissement": (
            "Indices publiés par l'INSEE, reproduits sans modification. "
            "La révision d'un loyer se calcule avec l'indice du trimestre "
            "de référence inscrit au bail."),
        "trimestre_le_plus_recent": {"annee": dernier[0], "trimestre": dernier[1]},
        "nb_indices": len(indices),
        "indices": [{"annee": a, "trimestre": t, "valeur": v} for a, t, v in indices],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ecrire", action="store_true",
                    help="écrire le fichier (sinon, contrôle seul)")
    ap.add_argument("--sortie", type=Path, default=SORTIE)
    args = ap.parse_args()

    erreurs = verifier(INDICES)
    for e in erreurs:
        print(f"✗ {e}", file=sys.stderr)
    if erreurs:
        print(f"\n{len(erreurs)} anomalie(s) — rien n'est écrit.", file=sys.stderr)
        return 1

    doc = construire(INDICES)
    premier, dernier = INDICES[0], INDICES[-1]
    print(f"✓ {len(INDICES)} trimestres, de {premier[0]}-T{premier[1]} "
          f"à {dernier[0]}-T{dernier[1]}")

    if args.ecrire:
        args.sortie.parent.mkdir(parents=True, exist_ok=True)
        # Idempotence : `genere_le` seul ne justifie pas une réécriture.
        # Sans cela, relancer l'export produirait un diff sans contenu,
        # et un commit qui ferait croire à une mise à jour d'indice.
        if args.sortie.exists():
            ancien = json.loads(args.sortie.read_text(encoding="utf-8"))
            if {k: v for k, v in ancien.items() if k != "genere_le"} == \
               {k: v for k, v in doc.items() if k != "genere_le"}:
                print(f"  inchangé : {args.sortie.relative_to(RACINE)}")
                return 0
        args.sortie.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  écrit : {args.sortie.relative_to(RACINE)} "
              f"({args.sortie.stat().st_size / 1024:.1f} Ko)")
    else:
        print("  (contrôle seul, rien écrit — ajouter --ecrire)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
