#!/usr/bin/env python3
"""Liens App Store : forme trackée dans les pages, canonique dans le JSON-LD.

Deux formes coexistent sur le site et ne sont pas interchangeables.

1. Les liens cliquables (<a href>) portent le jeton de campagne Apple.
   Sans lui, l'installation n'est rattachée à aucune source dans App
   Store Connect et la mesure d'acquisition est perdue.

       https://apps.apple.com/app/apple-store/id6772793420?pt=…&ct=…&mt=8

2. Les champs JSON-LD (sameAs, downloadUrl, installUrl, url) portent la
   forme canonique, sans paramètres. Ces champs servent à Google pour
   rattacher l'app à l'entité BailleurSuite : une URL paramétrée y
   désignerait une ressource distincte de la fiche App Store réelle et
   affaiblirait le rattachement.

Le contrôle échoue si l'une des deux formes migre vers l'autre camp —
typiquement lors d'un copier-coller entre un bloc JSON-LD et un bouton.

    python3 tools/appstore.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

APP_ID = "6772793420"
CANONIQUE = f"https://apps.apple.com/fr/app/bailleursuite/id{APP_ID}"
PROVIDER_TOKEN = "128946892"
BASE_SUIVI = f"https://apps.apple.com/app/apple-store/id{APP_ID}"

# Valeurs de `ct` autorisées. Une valeur hors liste est presque toujours
# une faute de frappe : Apple l'accepte sans broncher et crée une
# campagne fantôme qu'on ne rapproche plus jamais de son emplacement.
CT_CONNUS = {
    "nav", "footer", "hero", "cta_final", "tarifs", "sticky",
    "calculatrice", "quittance", "guide2044", "guidelmnp",
    "comparatif", "compariphone", "radar", "aide",
}

# Préfixe posé au chargement par scripts/source-tracking.js quand la
# visite vient d'une campagne Google : ct=hero devient ct=ads_hero.
#
# Ces valeurs sont acceptées mais ne sont pas attendues dans les pages :
# elles naissent dans le navigateur, jamais dans le HTML. Les inscrire
# dans CT_CONNUS aurait fait échouer le contrôle « valeur déclarée mais
# jamais posée » sur les quatorze variantes ads_*, à chaque build.
PREFIXE_ADS = "ads_"

SUFFIXES = (".html", ".j2")
BALISE_A = re.compile(r"<a\b[^>]*>")
LIEN_SUIVI = re.compile(
    re.escape(BASE_SUIVI) + r"\?pt=(\d+)&amp;ct=([a-z0-9_]+)&amp;mt=8")


def fichiers() -> list[Path]:
    out = []
    for p in sorted(RACINE.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        if p.suffix in SUFFIXES:
            out.append(p)
    return out


def verifier() -> list[str]:
    erreurs: list[str] = []
    cts: Counter[str] = Counter()
    nb_canonique = 0

    for p in fichiers():
        rel = p.relative_to(RACINE)
        texte = p.read_text(encoding="utf-8")

        for m in BALISE_A.finditer(texte):
            balise = m.group(0)
            if f"id{APP_ID}" not in balise:
                continue
            ligne = texte[:m.start()].count("\n") + 1

            if CANONIQUE in balise:
                erreurs.append(
                    f"{rel}:{ligne} : lien cliquable en forme canonique — "
                    "l'installation ne sera rattachée à aucune campagne")
                continue

            suivi = LIEN_SUIVI.search(balise)
            if not suivi:
                erreurs.append(
                    f"{rel}:{ligne} : lien App Store de forme inattendue "
                    f"— attendu {BASE_SUIVI}?pt=…&amp;ct=…&amp;mt=8")
                continue

            jeton, ct = suivi.groups()
            if jeton != PROVIDER_TOKEN:
                erreurs.append(
                    f"{rel}:{ligne} : pt={jeton} au lieu de "
                    f"{PROVIDER_TOKEN}")
            base = ct[len(PREFIXE_ADS):] if ct.startswith(PREFIXE_ADS) else ct
            if base not in CT_CONNUS:
                erreurs.append(
                    f"{rel}:{ligne} : ct={ct} hors de la liste connue")
            cts[ct] += 1

            if "target=\"_blank\"" not in balise or "rel=\"noopener\"" not in balise:
                erreurs.append(
                    f"{rel}:{ligne} : target=\"_blank\" rel=\"noopener\" manquant")
            if f"ct:'{ct}'" not in balise:
                erreurs.append(
                    f"{rel}:{ligne} : événement Vercel absent ou "
                    f"désaccordé du ct de l'URL")

        # Champs JSON-LD : la forme canonique et elle seule.
        for m in re.finditer(
                r'"(sameAs|downloadUrl|installUrl|url)"\s*:\s*\[?\s*"'
                r'(https://apps\.apple\.com[^"]*)"', texte):
            champ, url = m.groups()
            ligne = texte[:m.start()].count("\n") + 1
            if url != CANONIQUE:
                erreurs.append(
                    f"{rel}:{ligne} : {champ} vaut {url} — attendu la forme "
                    f"canonique sans paramètres")
            else:
                nb_canonique += 1

    if not cts:
        erreurs.append("aucun lien App Store tracké trouvé")

    # Une valeur déclarée mais jamais posée n'est pas un détail de
    # tenue de liste : elle signale un emplacement censé convertir qui
    # n'a aucun lien, et la campagne correspondante reste vide dans
    # App Store Connect sans que rien ne le dise.
    # Les variantes ads_* sont retirées du décompte : elles ne sont
    # jamais attendues dans les pages.
    poses = {c[len(PREFIXE_ADS):] if c.startswith(PREFIXE_ADS) else c
             for c in cts}
    manquants = CT_CONNUS - poses
    for ct in sorted(manquants):
        erreurs.append(f"ct={ct} déclaré mais utilisé nulle part — "
                       "emplacement sans lien, ou valeur à retirer de CT_CONNUS")

    return erreurs, cts, nb_canonique, manquants


def main() -> int:
    erreurs, cts, nb_canonique, manquants = verifier()
    for e in erreurs:
        print(f"✗ {e}", file=sys.stderr)
    if erreurs:
        print(f"\n{len(erreurs)} anomalie(s).", file=sys.stderr)
        return 1
    print(f"✓ {sum(cts.values())} liens trackés (pt={PROVIDER_TOKEN}), "
          f"{nb_canonique} références JSON-LD canoniques")
    for ct, n in sorted(cts.items(), key=lambda x: (-x[1], x[0])):
        print(f"    {n:4d}  ct={ct}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
