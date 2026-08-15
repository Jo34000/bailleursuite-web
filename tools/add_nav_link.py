#!/usr/bin/env python3
"""Insère le lien « Radar » dans la navigation des pages existantes.

    python3 tools/add_nav_link.py            # dry-run : montre le diff
    python3 tools/add_nav_link.py --apply    # écrit les fichiers
    python3 tools/add_nav_link.py --revert   # retire les liens insérés

Trois emplacements par page : `.nav-links` (barre desktop),
`.nav-mobile-menu` (menu déroulant) et `.site-footer-nav` (pied de page).

Sans lien entrant, Google ne découvrira jamais les pages du Radar : un
sitemap seul ne suffit pas à faire indexer 42 URL orphelines.

**Idempotent** : une page déjà traitée est laissée intacte. Le script se
contente de repérer un lien voisin connu et d'insérer le sien juste
après, en recopiant l'indentation et la forme du voisin — il ne
reconstruit aucun bloc de navigation et ne touche à rien d'autre.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SITE = "https://bailleursuite.fr"
URL_RADAR = f"{SITE}/radar-immobilier"

PAGES = [
    "index.html",
    "aide/index.html",
    "calculatrice-rendement-locatif/index.html",
    "comparatif-logiciel-gestion-locative/index.html",
    "declaration-2044-guide/index.html",
    "lmnp-guide-complet/index.html",
    "quittance-loyer-pdf-gratuit/index.html",
    "conditions-utilisation.html",
    "politique-confidentialite.html",
]

# Chaque insertion est ancrée sur un lien existant, repéré par son URL.
# On se place APRÈS « Quittance PDF » : c'est l'ordre retenu dans les
# templates du Radar, et il laisse « Aide » et « Comparatif » en fin de
# liste comme aujourd'hui.
ANCRE = "/quittance-loyer-pdf-gratuit"

LIBELLES = {
    "nav-links": "Radar",
    "nav-mobile-menu": "Radar immobilier",
    "site-footer-nav": "Radar immobilier",
    "footer-nu": "Radar immobilier",
}


class Zone:
    """Une zone de navigation dans un fichier HTML."""

    def __init__(self, nom: str, ouverture: re.Pattern, fermeture: str):
        self.nom = nom
        self.ouverture = ouverture
        self.fermeture = fermeture


ZONES = [
    Zone("nav-links", re.compile(r'<div class="nav-links"[^>]*>'), "</div>"),
    Zone("nav-mobile-menu",
         re.compile(r'<div class="nav-mobile-menu"[^>]*>'), "</div>"),
    Zone("site-footer-nav",
         re.compile(r'<nav class="site-footer-nav"[^>]*>'), "</nav>"),
    # La page comparatif ne charge pas le design system : son pied de page
    # est un <footer> nu, sans .site-footer-nav. Sans cette zone de repli
    # elle resterait la seule page sans lien Radar en pied.
    Zone("footer-nu", re.compile(r'<footer>\s*(?=\s*<a )'), "</footer>"),
]


def bloc(texte: str, zone: Zone) -> tuple[int, int] | None:
    """Bornes (début, fin) du contenu de la zone, ou None si absente."""
    m = zone.ouverture.search(texte)
    if not m:
        return None
    fin = texte.find(zone.fermeture, m.end())
    if fin == -1:
        return None
    return m.end(), fin


def inserer(texte: str, zone: Zone) -> tuple[str, str]:
    """Insère le lien Radar dans une zone. Retourne (texte, statut)."""
    bornes = bloc(texte, zone)
    if bornes is None:
        return texte, "zone absente"

    debut, fin = bornes
    contenu = texte[debut:fin]

    if "/radar-immobilier" in contenu:
        return texte, "déjà présent"

    # Repérer le lien d'ancrage avec sa ligne entière, pour en recopier
    # l'indentation et les attributs (class="nav-link" ou non).
    ancre = re.search(
        r'([ \t]*)(<a[^>]*href="[^"]*' + re.escape(ANCRE) + r'"[^>]*>.*?</a>)',
        contenu, re.S,
    )
    if not ancre:
        return texte, f"ancre {ANCRE} introuvable"

    indent, balise = ancre.group(1), ancre.group(2)
    classe = ' class="nav-link"' if 'class="nav-link"' in balise else ""

    # Recopier la forme d'URL du voisin : index.html référence ses pages
    # en relatif, les guides en absolu. Insérer systématiquement de
    # l'absolu rendrait chaque page incohérente avec elle-même.
    href = URL_RADAR if f'href="{SITE}' in balise else "/radar-immobilier"
    lien = f'{indent}<a{classe} href="{href}">{LIBELLES[zone.nom]}</a>'

    # Le pied de page sépare ses liens par un <span class="site-footer-sep">.
    # Ce séparateur SUIT chaque lien : on insère donc « séparateur + lien »
    # juste après l'ancre, et celui qui suivait l'ancre sépare désormais
    # notre lien du suivant. Insérer après lui en produirait deux.
    suite = contenu[ancre.end():]
    sep = re.match(r'\s*<span class="site-footer-sep">·</span>', suite)
    insertion = (sep.group(0) if sep else "") + "\n" + lien

    nouveau = contenu[:ancre.end()] + insertion + contenu[ancre.end():]
    return texte[:debut] + nouveau + texte[fin:], "inséré"


def retirer(texte: str, zone: Zone) -> tuple[str, str]:
    """Retire le lien Radar d'une zone (et le séparateur qui le précède)."""
    bornes = bloc(texte, zone)
    if bornes is None:
        return texte, "zone absente"

    debut, fin = bornes
    contenu = texte[debut:fin]
    if "/radar-immobilier" not in contenu:
        return texte, "absent"

    motif = re.compile(
        r'(\s*<span class="site-footer-sep">·</span>)?'
        r'\s*<a[^>]*href="[^"]*/radar-immobilier"[^>]*>.*?</a>',
        re.S,
    )
    nouveau, n = motif.subn("", contenu, count=1)
    if n == 0:
        return texte, "motif non reconnu"
    return texte[:debut] + nouveau + texte[fin:], "retiré"


def traiter(chemin: Path, action, appliquer: bool) -> dict[str, str]:
    original = chemin.read_text(encoding="utf-8")
    texte = original
    statuts: dict[str, str] = {}

    for zone in ZONES:
        # `footer-nu` n'est qu'un repli : si la page a déjà un
        # .site-footer-nav traité, on ne touche pas une seconde fois au
        # pied de page.
        if zone.nom == "footer-nu" and statuts.get("site-footer-nav") not in (
            None, "zone absente"
        ):
            statuts[zone.nom] = "sans objet"
            continue
        texte, statut = action(texte, zone)
        statuts[zone.nom] = statut

    if texte != original and appliquer:
        chemin.write_text(texte, encoding="utf-8")

    statuts["_modifie"] = "oui" if texte != original else "non"
    return statuts


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--apply", action="store_true",
                    help="écrire les fichiers (défaut : simulation)")
    ap.add_argument("--revert", action="store_true",
                    help="retirer les liens au lieu de les insérer")
    args = ap.parse_args()

    action = retirer if args.revert else inserer
    verbe = "Retrait" if args.revert else "Insertion"
    mode = "APPLIQUÉ" if args.apply else "SIMULATION (utiliser --apply pour écrire)"
    print(f"{verbe} du lien Radar — {mode}\n")

    absents = [p for p in PAGES if not (RACINE / p).exists()]
    if absents:
        print("✗ pages introuvables :", ", ".join(absents), file=sys.stderr)
        return 1

    modifies = 0
    problemes: list[str] = []

    for page in PAGES:
        statuts = traiter(RACINE / page, action, args.apply)
        marque = "●" if statuts.pop("_modifie") == "oui" else "○"
        if marque == "●":
            modifies += 1
        detail = "  ".join(f"{z}: {s}" for z, s in statuts.items())
        print(f"  {marque} {page:<52} {detail}")

        # Un statut « zone absente » n'est un problème que si AUCUNE
        # variante ne l'a couvert : la page comparatif n'a pas de
        # .site-footer-nav, mais son <footer> nu prend le relais.
        ok = ("inséré", "retiré", "déjà présent", "absent")
        for zone in ("nav-links", "nav-mobile-menu"):
            if statuts[zone] not in ok:
                problemes.append(f"{page} / {zone} : {statuts[zone]}")
        if not any(statuts[z] in ok for z in ("site-footer-nav", "footer-nu")):
            problemes.append(
                f"{page} / pied de page : aucune zone reconnue "
                f"(site-footer-nav: {statuts['site-footer-nav']}, "
                f"footer-nu: {statuts['footer-nu']})"
            )

    print(f"\n{modifies}/{len(PAGES)} page(s) à modifier.")

    if problemes:
        print("\n⚠ à vérifier :", file=sys.stderr)
        for p in problemes:
            print(f"  - {p}", file=sys.stderr)
        return 1

    if not args.apply and modifies:
        print("Relancer avec --apply pour écrire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
