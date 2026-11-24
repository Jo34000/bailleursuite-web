#!/usr/bin/env python3
"""Régénère l'image de partage og-image-<année>.png (1200×630) à la racine.

Rend tools/og/og-image-source.j2 dans Chrome (ou Chromium) sans interface,
avec les polices auto-hébergées du site, puis enregistre un PNG optimisé
sans perte. Le dépôt n'est pas modifié en dehors du fichier produit : la
page source est servie depuis la mémoire, la racine du site depuis le
disque (pour /fonts).

    python3 tools/og/render_og.py                 # og-image-<année en cours>.png
    python3 tools/og/render_og.py --annee 2027
    python3 tools/og/render_og.py --sortie /tmp/essai.png

Le navigateur est cherché dans $CHROME, puis aux emplacements habituels
(macOS, puis chrome-headless-shell et Chrome/Chromium sous Linux). Si
Chrome reste bloqué (délai de 90 s dépassé), pointer $CHROME vers
chrome-headless-shell. Prérequis : pip install jinja2 pillow.

Changer d'année ne met pas à jour les pages : l'adresse de l'image est
écrite en dur dans les pages, le gabarit Radar (_head.j2) et
build_radar.py, à remplacer partout, puis supprimer l'ancienne image.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import html
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent
LARGEUR, HAUTEUR = 1200, 630
POIDS_MAX = 100_000  # octets

SURTITRE = ["APP iPHONE", "iPAD", "MAC", "GESTION LOCATIVE"]
BAS = ["Déclaration 2044", "LMNP", "Quittances PDF"]

NAVIGATEURS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "chrome-headless-shell",
    "/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
    "google-chrome", "chromium", "chromium-browser",
]


def navigateur() -> str:
    for c in ([os.environ["CHROME"]] if os.environ.get("CHROME") else []) + NAVIGATEURS:
        if "*" in c:
            c = next(iter(sorted(glob.glob(c), reverse=True)), "")
        chemin = shutil.which(c) or (c if c and Path(c).is_file() else None)
        if chemin:
            return chemin
    sys.exit("Chrome ou Chromium introuvable : indiquer son chemin dans $CHROME.")


def page_source() -> bytes:
    env = Environment(loader=FileSystemLoader(ICI), autoescape=False)
    rendu = env.get_template("og-image-source.j2").render(
        surtitre=[html.escape(t) for t in SURTITRE],
        bas=[html.escape(t) for t in BAS],
    )
    return rendu.encode("utf-8")


def serveur(source: bytes) -> ThreadingHTTPServer:
    class Gestionnaire(SimpleHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/__og.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(source)))
                self.end_headers()
                self.wfile.write(source)
            else:
                super().do_GET()

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Gestionnaire, directory=str(RACINE)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--annee", type=int, default=dt.date.today().year)
    ap.add_argument("--sortie", type=Path)
    args = ap.parse_args()
    sortie = args.sortie or RACINE / f"og-image-{args.annee}.png"

    srv = serveur(page_source())
    url = f"http://127.0.0.1:{srv.server_address[1]}/__og.html"
    with tempfile.TemporaryDirectory() as tmp:
        brut = Path(tmp) / "brut.png"
        commande = [
            navigateur(), "--headless=new", "--no-sandbox", "--disable-gpu",
            "--hide-scrollbars", "--force-device-scale-factor=1",
            # Pas de trafic de fond (mises à jour, synchronisation…) :
            # sans réseau sortant, Chrome peut sinon rester bloqué.
            "--no-first-run", "--no-default-browser-check",
            "--disable-background-networking", "--disable-component-update",
            "--disable-sync",
            f"--window-size={LARGEUR},{HAUTEUR}",
            "--virtual-time-budget=5000",  # laisse aux polices le temps d'arriver
            f"--user-data-dir={tmp}/profil",
            f"--screenshot={brut}", url,
        ]
        try:
            subprocess.run(commande, check=True, capture_output=True, timeout=90)
        except subprocess.TimeoutExpired:
            sys.exit("✗ navigateur bloqué au-delà de 90 s : pointer $CHROME vers "
                     "chrome-headless-shell (npx @puppeteer/browsers install "
                     "chrome-headless-shell@stable).")
        srv.shutdown()
        img = Image.open(brut).convert("RGB")
        if img.size != (LARGEUR, HAUTEUR):
            sys.exit(f"Capture en {img.size[0]}×{img.size[1]}, attendu {LARGEUR}×{HAUTEUR}.")
        img.save(sortie, optimize=True)

    poids = sortie.stat().st_size
    print(f"✓ {sortie.relative_to(RACINE) if sortie.is_relative_to(RACINE) else sortie} : "
          f"{LARGEUR}×{HAUTEUR}, {poids / 1000:.1f} Ko")
    if poids >= POIDS_MAX:
        sys.exit(f"✗ poids {poids} o, au-delà de {POIDS_MAX} o")


if __name__ == "__main__":
    main()
