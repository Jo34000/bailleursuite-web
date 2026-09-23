#!/usr/bin/env python3
"""Consentement cookies : le tag Google ne doit exister nulle part en statique.

La conformité tient à une seule chose : gtag.js n'est jamais chargé
avant un choix explicite. C'est vrai tant que le tag n'existe que dans
scripts/consent.js, injecté après acceptation.

Il suffirait qu'un jour quelqu'un colle l'extrait fourni par Google
dans le <head> d'une page — c'est l'usage normal, c'est ce que
l'interface de Google propose de copier — pour que le bandeau devienne
décoratif et le site non conforme, sans que rien ne change à l'écran.
Ce contrôle refuse ce collé.

Il vérifie aussi que les deux scripts et la feuille de style sont
chargés partout, et que le moyen de revenir sur son choix existe sur
chaque page : une page qui n'aurait pas le bandeau laisserait un
visiteur sans choix, une page sans lien « Gérer les cookies » le
laisserait sans retour possible.

    python3 tools/consentement.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

CONSENT_JS = RACINE / "scripts" / "consent.js"
SOURCE_JS = RACINE / "scripts" / "source-tracking.js"

# Marqueurs interdits dans les pages. Le tag Google sous toutes les
# formes que son interface propose de copier.
INTERDITS = [
    ("googletagmanager.com", "chargement direct du tag Google"),
    ("gtag(", "appel gtag en dur"),
    ("dataLayer", "file dataLayer en dur"),
    ("AW-", "identifiant de conversion Google Ads en dur"),
]

REQUIS = [
    ('<script defer src="/scripts/consent.js"></script>', "script de consentement"),
    ('<script defer src="/scripts/source-tracking.js"></script>', "script de source"),
    ('<link rel="stylesheet" href="/styles/consent.css">', "feuille du bandeau"),
    ('data-bs-consent="ouvrir"', "lien « Gérer les cookies »"),
]

ID_ADS = "AW-18454674623"


# Un libellé de conversion : l'identifiant du compte, puis un jeton
# opaque. Le jeton doit contenir au moins une minuscule ou un chiffre —
# c'est ce qui sépare un vrai libellé d'un marque-place en capitales,
# que gtag accepterait avant que Google ne le jette en silence.
FORME_LIBELLE = re.compile(r"^AW-\d{9,12}/[A-Za-z0-9_-]{8,32}$")
# Certains marque-places ont toutes les apparences d'un vrai jeton —
# à commencer par l'exemple de la documentation. Seule une liste
# explicite les écarte.
JETONS_FACTICES = ("LIBELLE", "REMPLACER", "PLACEHOLDER", "TODO",
                   "XXX", "EXEMPLE", "EXAMPLE", "ABCD")
BLOC_CONVERSIONS = re.compile(
    r"var CONVERSIONS = \{(.*?)\};", re.S)
LIGNE_LIBELLE = re.compile(r"(\w+)\s*:\s*'([^']*)'")


def verifier_libelles(consent: str) -> list[str]:
    """Une conversion est soit vide — donc inactive et assumée — soit
    d'une forme plausible. Jamais entre les deux."""
    bloc = BLOC_CONVERSIONS.search(consent)
    if not bloc:
        return ["bloc CONVERSIONS introuvable dans scripts/consent.js"]

    erreurs = []
    for nom, valeur in LIGNE_LIBELLE.findall(bloc.group(1)):
        if valeur == "":
            continue  # non encore renseignée, aucun envoi
        jeton = valeur.split("/")[-1]
        factice = any(f in jeton.upper() for f in JETONS_FACTICES)
        if (not FORME_LIBELLE.match(valeur)
                or not re.search(r"[a-z0-9]", jeton)
                or factice):
            erreurs.append(
                f"scripts/consent.js : libellé de conversion invalide pour "
                f"{nom} — « {valeur} ». Attendu la forme "
                f"AW-18454674623/<jeton>, copiée depuis Google Ads ; "
                f"un marque-place enverrait les conversions dans le vide")
    return erreurs


# Outillage interne : hors du site public, exclu de l'indexation par
# robots.txt et par une balise noindex, sans lien App Store ni tag
# publicitaire. Lui imposer le bandeau n'aurait rien protégé.
HORS_SITE = ("admin",)


def pages() -> list[Path]:
    """Pages livrées et gabarits qui les produisent."""
    out = [p for p in sorted(RACINE.rglob("*.html"))
           if ".git" not in p.parts
           and not any(d in p.parts for d in HORS_SITE)]
    out += [RACINE / "tools" / "templates" / "_head.j2",
            RACINE / "tools" / "templates" / "_footer.j2"]
    return [p for p in out if p.exists()]


def verifier() -> list[str]:
    erreurs: list[str] = []

    if not CONSENT_JS.exists():
        return [f"{CONSENT_JS.relative_to(RACINE)} absent"]
    if not SOURCE_JS.exists():
        erreurs.append(f"{SOURCE_JS.relative_to(RACINE)} absent")

    consent = CONSENT_JS.read_text(encoding="utf-8")
    if ID_ADS not in consent:
        erreurs.append(f"identifiant {ID_ADS} absent de scripts/consent.js")
    erreurs += verifier_libelles(consent)
    # Le tag ne doit pas partir au chargement : le seul appel à
    # chargerGtag() hors d'une fonction est celui gardé par l'état.
    if "granted" not in consent:
        erreurs.append("scripts/consent.js ne teste pas l'état « granted »")

    for p in pages():
        rel = p.relative_to(RACINE)
        texte = p.read_text(encoding="utf-8")

        for motif, quoi in INTERDITS:
            if motif in texte:
                ligne = texte[:texte.index(motif)].count("\n") + 1
                erreurs.append(
                    f"{rel}:{ligne} : {quoi} — le tag doit rester injecté "
                    "par scripts/consent.js, après consentement")

        # Les gabarits n'ont pas à tout porter : _head.j2 les scripts et
        # la feuille, _footer.j2 le lien.
        if p.suffix == ".j2":
            attendus = REQUIS[:3] if p.name == "_head.j2" else REQUIS[3:]
        else:
            attendus = REQUIS
        for marqueur, quoi in attendus:
            if marqueur not in texte:
                erreurs.append(f"{rel} : {quoi} absent")

    return erreurs


def main() -> int:
    erreurs = verifier()
    for e in erreurs:
        print(f"✗ {e}", file=sys.stderr)
    if erreurs:
        print(f"\n{len(erreurs)} anomalie(s).", file=sys.stderr)
        return 1
    n = len(pages())
    print(f"✓ consentement vérifié : {n} pages et gabarits, aucun tag Google "
          "en statique, bandeau et retour en arrière présents partout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
