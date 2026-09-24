#!/usr/bin/env python3
"""QR code App Store pour les visiteurs sur ordinateur.

Un visiteur derrière un écran d'ordinateur ne peut pas installer une
application iPhone d'un clic. Le QR code lui fait franchir l'écart
sans rompre le parcours.

Le fichier est généré une fois et versionné : la page ne dépend
d'aucune bibliothèque à l'exécution, et le rendu ne peut pas changer
sous nos pieds au gré d'une mise à jour de dépendance.

Régénérer après modification de l'URL :

    pip install segno
    python3 tools/qr_appstore.py --ecrire

Le contrôle de tools/appstore.py vérifie que le fichier publié encode
bien l'URL attendue, jeton de campagne compris.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BASE = ("https://apps.apple.com/app/apple-store/id6772793420"
        "?pt=128946892&ct={ct}&mt=8")

# Un QR par page de destination. Le jeton est distinct de celui du
# badge : un scan et un clic ne disent pas la même chose, et les
# confondre rendrait la mesure inexploitable.
CODES = {
    "quittance_qr": RACINE / "qr-appstore-quittance.svg",
    "calculatrice_qr": RACINE / "qr-appstore-calculatrice.svg",
}


def construire(ct: str) -> str:
    import segno
    import io
    # Correction d'erreur moyenne : l'affichage est petit et l'écran
    # peut refléter. « quiet zone » à 2 modules, la marge de silence
    # que la spécification impose pour qu'un lecteur accroche.
    qr = segno.make(BASE.format(ct=ct), error="m")
    # segno écrit des octets : le tampon doit être binaire.
    tampon = io.BytesIO()
    qr.save(tampon, kind="svg", scale=4, border=2,
            dark="#1C1C1E", light="#FFFFFF", svgclass=None, lineclass=None,
            omitsize=True, xmldecl=False, svgns=True)
    return tampon.getvalue().decode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ecrire", action="store_true")
    args = ap.parse_args()
    for ct, sortie in CODES.items():
        try:
            svg = construire(ct)
        except ImportError:
            print("✗ segno absent — pip install segno", file=sys.stderr)
            return 1
        print(f"✓ QR pour ct={ct}")
        if args.ecrire:
            sortie.write_text(svg, encoding="utf-8")
            print(f"  écrit : {sortie.name} ({len(svg)} octets)")
    if not args.ecrire:
        print("  (contrôle seul — ajouter --ecrire)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
