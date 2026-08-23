#!/usr/bin/env python3
"""Export allégé du Radar pour le bundle iOS.

Le fichier de production répète, sur chaque indicateur de chaque ville,
les six mêmes chaînes de métadonnée : source, millesime, page, fichier,
licence, licence_url. Quinze indicateurs × quarante villes, soit six
cents répétitions de cinq chaînes distinctes. C'est près des trois
quarts du poids du fichier, pour zéro information supplémentaire.

Cet export les sort dans l'en-tête et les référence par clé. Le registre
`sources` est déjà indexé (`dvf`, `loyers`, `insee`, `cog`) : il suffit
de rattacher chaque indicateur à sa clé. L'unité et le millésime, eux,
sont constants pour un indicateur donné — le contrôle ci-dessous le
vérifie plutôt que de le supposer, et refuse d'écrire si ce n'est pas
le cas. Dédoublonner une valeur qui varie la ferait disparaître en
silence.

    python3 tools/exporter_app.py                       # data/villes.json
    python3 tools/exporter_app.py --source chemin.json  # autre entrée
    python3 tools/exporter_app.py --sortie app.json     # autre sortie
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "data" / "villes.json"
SORTIE = RACINE / "data" / "villes-app.json"

SCHEMA = "radar-app-1"

# Arrondissements municipaux de Paris, Lyon et Marseille (COG INSEE).
# Le fichier de production ne porte que leur NOMBRE
# (`fiabilite.loyer_arrondissements_attendus`), pas leurs codes : la
# table est donc explicite ici, et confrontée à ce nombre à chaque
# export. Une divergence arrête le programme — c'est le seul garde-fou
# possible contre une table qui vieillirait sans qu'on le voie.
ARRONDISSEMENTS = {
    "75056": [f"751{n:02d}" for n in range(1, 21)],   # Paris, 20
    "69123": [f"693{n:02d}" for n in range(81, 90)],  # Lyon, 9 (69381–69389)
    "13055": [f"132{n:02d}" for n in range(1, 17)],   # Marseille, 16
}

# Métadonnée transportée par chaque indicateur dans le fichier source,
# et qu'on remonte dans l'en-tête.
CLES_META = ("source", "millesime", "page", "fichier", "licence", "licence_url")


class Anomalie(Exception):
    """Erreur qui doit arrêter l'export plutôt que produire un fichier douteux."""


def cle_de_source(doc: dict) -> dict[str, str]:
    """libellé de source -> clé du registre `sources`."""
    return {s["libelle"]: k for k, s in doc["sources"].items() if "libelle" in s}


def construire_meta(doc: dict) -> dict[str, dict]:
    """Signature de chaque indicateur, vérifiée constante sur toutes les villes."""
    lib2cle = cle_de_source(doc)
    vues: dict[str, set] = {}
    meta: dict[str, dict] = {}

    for ville in doc["villes"]:
        for nom, ind in ville.get("indicateurs", {}).items():
            signature = tuple(ind.get(c) for c in CLES_META) + (ind.get("unite"),)
            vues.setdefault(nom, set()).add(signature)

    for nom, signatures in sorted(vues.items()):
        if len(signatures) > 1:
            raise Anomalie(
                f"indicateur {nom!r} : {len(signatures)} signatures différentes "
                f"selon la ville — la métadonnée n'est pas dédoublonnable sans "
                f"perte. Signatures : {sorted(signatures)}")
        src, millesime, page, fichier, licence, licence_url, unite = next(iter(signatures))
        entree: dict = {}
        if unite:
            entree["unite"] = unite
        if src in lib2cle:
            entree["source"] = lib2cle[src]
        else:
            # Indicateur calculé : pas de source externe, donc pas de
            # licence. On garde la formule, qui est l'information utile.
            entree["source"] = None
            entree["calcul"] = src
        entree["millesime"] = millesime
        meta[nom] = entree
    return meta


def alleger_ville(ville: dict, meta: dict[str, dict]) -> dict:
    valeurs: dict[str, object] = {}
    notes: dict[str, str] = {}
    for nom, ind in ville.get("indicateurs", {}).items():
        valeurs[nom] = ind.get("valeur")
        if ind.get("note"):
            notes[nom] = ind["note"]

    sortie = {
        "code_insee": ville["code_insee"],
        "nom": ville["nom"],
        "slug": ville["slug"],
        "departement": ville["departement"],
        "region": ville["region"],
        "region_nom": ville.get("region_nom"),
    }

    arr = ARRONDISSEMENTS.get(ville["code_insee"])
    if arr:
        attendus = ville.get("fiabilite", {}).get("loyer_arrondissements_attendus")
        if attendus is not None and attendus != len(arr):
            raise Anomalie(
                f"{ville['nom']} ({ville['code_insee']}) : la table interne "
                f"déclare {len(arr)} arrondissements, le fichier source en "
                f"attend {attendus}. Mettre la table à jour avant d'exporter.")
        sortie["arrondissements"] = arr

    sortie["indicateurs"] = valeurs
    if notes:
        sortie["notes"] = notes
    sortie["fiabilite"] = ville.get("fiabilite", {})
    sortie["referentiel"] = ville.get("referentiel", {})
    return sortie


def exporter(doc: dict) -> dict:
    meta = construire_meta(doc)
    villes = [alleger_ville(v, meta) for v in doc["villes"]]

    if doc.get("nb_villes") not in (None, len(villes)):
        raise Anomalie(f"en-tête nb_villes={doc['nb_villes']} pour "
                       f"{len(villes)} villes exportées")

    return {
        "schema": SCHEMA,
        "genere_le": doc.get("genere_le"),
        "panel": doc.get("panel"),
        "nb_villes": len(villes),
        "avertissement": doc.get("avertissement"),
        "sources": doc.get("sources", {}),
        "indicateurs_meta": meta,
        "villes": villes,
    }


def controler(origine: dict, allege: dict) -> list[str]:
    """Aucune valeur ne doit avoir bougé entre les deux fichiers."""
    ecarts = []
    par_code = {v["code_insee"]: v for v in allege["villes"]}
    for ville in origine["villes"]:
        a = par_code.get(ville["code_insee"])
        if a is None:
            ecarts.append(f"{ville['code_insee']} absente de l'export")
            continue
        for nom, ind in ville.get("indicateurs", {}).items():
            if a["indicateurs"].get(nom) != ind.get("valeur"):
                ecarts.append(f"{ville['code_insee']}.{nom} : "
                              f"{ind.get('valeur')!r} → {a['indicateurs'].get(nom)!r}")
            if ind.get("note") and a.get("notes", {}).get(nom) != ind["note"]:
                ecarts.append(f"{ville['code_insee']}.{nom} : note perdue")
        for champ in ("nom", "slug", "departement", "region", "region_nom"):
            if a.get(champ) != ville.get(champ):
                ecarts.append(f"{ville['code_insee']}.{champ} altéré")
    return ecarts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, default=SOURCE)
    ap.add_argument("--sortie", type=Path, default=SORTIE)
    ap.add_argument("--indent", action="store_true",
                    help="sortie indentée (lisible, ~2× plus lourde)")
    args = ap.parse_args()

    if not args.source.exists():
        print(f"✗ introuvable : {args.source}\n"
              f"  Le dataset n'est pas versionné (data/ est dans .gitignore).\n"
              f"  Lancer cet export depuis la machine qui porte le fichier.",
              file=sys.stderr)
        return 1

    origine = json.loads(args.source.read_text(encoding="utf-8"))
    try:
        allege = exporter(origine)
    except Anomalie as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1

    ecarts = controler(origine, allege)
    if ecarts:
        print(f"✗ {len(ecarts)} valeur(s) altérée(s) par l'allègement :", file=sys.stderr)
        for e in ecarts[:10]:
            print(f"    {e}", file=sys.stderr)
        return 1

    texte = json.dumps(allege, ensure_ascii=False,
                       indent=2 if args.indent else None,
                       separators=None if args.indent else (",", ":"))
    args.sortie.write_text(texte, encoding="utf-8")

    avant = args.source.stat().st_size
    apres = args.sortie.stat().st_size
    print(f"✓ {args.sortie}")
    print(f"  {allege['nb_villes']} villes · {len(allege['indicateurs_meta'])} indicateurs "
          f"· données du {allege['genere_le']}")
    print(f"  {avant/1024:.1f} Ko → {apres/1024:.1f} Ko "
          f"({100 * (1 - apres / avant):.0f} % de moins)")
    arr = sum(1 for v in allege["villes"] if "arrondissements" in v)
    print(f"  {arr} commune(s) avec leurs arrondissements rattachés")
    print(f"  toutes les valeurs vérifiées identiques à la source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
