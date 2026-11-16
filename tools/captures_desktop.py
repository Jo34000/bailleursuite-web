#!/usr/bin/env python3
"""Captures iPad → images desktop du site.

Les sources sont des captures du simulateur iPad Pro 13" en paysage,
2752×2064 à 2x. Deux traitements seulement sont faits ici :

1. Le haut est recadré pour retirer la barre d'état iOS (heure, Wi-Fi,
   batterie). Un relevé ligne par ligne sur les quatre captures place
   l'encre de la barre entre y=19 et y=44, la première ligne vierge
   étant y=45. RECADRAGE_HAUT est fixé plus haut que ce minimum : la
   marge ne coûte que du fond uni, alors qu'un pixel d'heure oublié se
   verrait sur toutes les pages.

2. L'image est réduite à LARGEUR_CIBLE. La fenêtre ne dépasse jamais
   1080 px de large dans la page (hero : max-width 1080 ; cartes : une
   colonne plus étroite encore). 2160 px est donc exactement le 2x de
   la plus grande taille d'affichage — au-delà, on téléchargerait des
   pixels que personne ne voit.

Le recadrage BAS n'est pas fait ici : il masque la barre d'onglets et
la poignée de redimensionnement, et c'est la CSS qui s'en charge, pour
que la hauteur visible puisse varier d'un emplacement à l'autre sans
regénérer les fichiers.

    python3 tools/captures_desktop.py          # contrôle seul
    python3 tools/captures_desktop.py --ecrire
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ECRANS = ("index", "gerer", "declarer", "projeter")

RECADRAGE_HAUT = 80
LARGEUR_CIBLE = 2160
QUALITE_WEBP = 85

# Au-delà de cette ligne, plus aucun pixel de barre d'état ne doit
# subsister. Mesuré, pas supposé — voir verifier_barre_etat().
DERNIERE_LIGNE_BARRE = 44


def charger():
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        print("✗ Pillow absent ou cassé pour cet interpréteur.", file=sys.stderr)
        print("  Essayer : /usr/bin/python3 tools/captures_desktop.py", file=sys.stderr)
        raise SystemExit(1)
    return Image


def verifier_barre_etat(Image, source: Path) -> int:
    """Dernière ligne portant de l'encre dans la bande haute.

    Le fond de la capture est uni ; tout ce qui s'en écarte dans les
    300 premières lignes est soit la barre d'état, soit le début du
    contenu. On s'arrête au premier blanc durable pour ne mesurer que
    la barre.
    """
    im = Image.open(source).convert("RGB")
    W, _ = im.size
    px = im.load()
    fond = px[5, 5]
    premier, dernier = None, -1
    for y in range(300):
        encre = any(
            sum(abs(a - b) for a, b in zip(px[x, y], fond)) > 40
            for x in range(0, W, 2)
        )
        if encre:
            if premier is None:
                premier = y
            dernier = y
        elif premier is not None and y - dernier > 40:
            break
    return dernier


def traiter(Image, nom: str, ecrire: bool) -> list[str]:
    src = RACINE / f"screen-{nom}-ipad.png"
    if not src.exists():
        return [f"{src.name} absent"]

    dernier = verifier_barre_etat(Image, src)
    if dernier >= RECADRAGE_HAUT:
        return [f"{src.name} : encre jusqu'à y={dernier}, au-delà du "
                f"recadrage de {RECADRAGE_HAUT} px — la barre d'état "
                "resterait visible"]
    if dernier > DERNIERE_LIGNE_BARRE:
        return [f"{src.name} : encre jusqu'à y={dernier}, attendu "
                f"≤ {DERNIERE_LIGNE_BARRE} — capture d'un autre gabarit ?"]

    im = Image.open(src)
    W, H = im.size
    im = im.crop((0, RECADRAGE_HAUT, W, H))
    hauteur = round(im.size[1] * LARGEUR_CIBLE / im.size[0])
    im = im.convert("RGB").resize((LARGEUR_CIBLE, hauteur), Image.LANCZOS)

    webp = RACINE / f"screen-{nom}-desktop.webp"
    png = RACINE / f"screen-{nom}-desktop.png"
    if ecrire:
        im.save(webp, "WEBP", quality=QUALITE_WEBP, method=6)
        im.save(png, "PNG", optimize=True)
        print(f"  {webp.name:30} {webp.stat().st_size/1024:7.1f} Ko")
        print(f"  {png.name:30} {png.stat().st_size/1024:7.1f} Ko   (repli)")
    print(f"✓ {nom:9} barre d'état jusqu'à y={dernier} · recadré {RECADRAGE_HAUT} px "
          f"· {W}×{H} → {LARGEUR_CIBLE}×{hauteur}")
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ecrire", action="store_true",
                    help="écrire les fichiers (sinon, contrôle seul)")
    args = ap.parse_args()

    Image = charger()
    erreurs: list[str] = []
    for nom in ECRANS:
        erreurs += traiter(Image, nom, args.ecrire)
    for e in erreurs:
        print(f"✗ {e}", file=sys.stderr)
    if erreurs:
        return 1
    if not args.ecrire:
        print("  (contrôle seul, rien écrit — ajouter --ecrire)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
