#!/usr/bin/env python3
"""IndexNow : signaler à Bing et Yandex les URL modifiées.

IndexNow remplace l'attente passive du crawl par une notification
poussée : on annonce les URL qui ont changé, les moteurs partenaires
(Bing, Yandex, Seznam, Naver) se partagent le signal. Google n'y
participe pas — pour lui, le sitemap et la Search Console restent la
seule voie.

Preuve de propriété
-------------------
La clé n'est pas un secret : elle est publiée à la racine du site, et
c'est justement sa présence à cette adresse qui prouve qu'on contrôle
le domaine. La versionner est donc normal, et la faire tourner n'aurait
aucun intérêt.

Usage
-----
    python3 tools/indexnow.py                 # contrôle, rien d'envoyé
    python3 tools/indexnow.py --envoyer       # toutes les URL du sitemap
    python3 tools/indexnow.py --envoyer /aide /calculatrice-rendement-locatif

Après déploiement, préférer la seconde forme : annoncer 50 URL quand
deux ont bougé dilue le signal sans rien accélérer.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

SITE = "https://bailleursuite.fr"
CLE = "5659aa8f3b4633c256c7b090c75a2b10"
FICHIER_CLE = RACINE / f"{CLE}.txt"
SITEMAP = RACINE / "sitemap.xml"

POINT_DE_COLLECTE = "https://api.indexnow.org/indexnow"

# IndexNow plafonne à 10 000 URL par requête. Le site en compte 50 ;
# la borne est là pour que l'ajout d'un lot de pages ne fasse pas
# échouer l'envoi en silence.
MAX_URLS = 10_000


class Anomalie(Exception):
    """Erreur qui doit arrêter l'envoi plutôt que le laisser échouer côté moteur."""


def verifier() -> list[str]:
    """Contrôles préalables. Une clé absente ou désaccordée fait rejeter
    l'ensemble du lot par le moteur, sans message utile."""
    erreurs: list[str] = []

    if not FICHIER_CLE.exists():
        erreurs.append(f"{FICHIER_CLE.name} absent de la racine — le moteur "
                       "ne peut pas vérifier la propriété du domaine")
    else:
        contenu = FICHIER_CLE.read_text(encoding="utf-8").strip()
        if contenu != CLE:
            erreurs.append(f"{FICHIER_CLE.name} contient « {contenu[:40]} » "
                           f"au lieu de la clé « {CLE} »")

    if not SITEMAP.exists():
        erreurs.append("sitemap.xml absent")
    elif not urls_du_sitemap():
        erreurs.append("sitemap.xml ne contient aucune URL")

    return erreurs


def urls_du_sitemap() -> list[str]:
    if not SITEMAP.exists():
        return []
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    racine = ET.parse(SITEMAP).getroot()
    return [e.text.strip() for e in racine.findall(".//s:loc", ns) if e.text]


def normaliser(entrees: list[str]) -> list[str]:
    """Accepte aussi bien « /aide » que l'URL absolue."""
    out = []
    for e in entrees:
        e = e.strip()
        if not e:
            continue
        if e.startswith("http://") or e.startswith("https://"):
            if not e.startswith(SITE):
                raise Anomalie(f"{e} n'appartient pas à {SITE} — IndexNow "
                               "rejette le lot entier si une URL sort du domaine")
            out.append(e)
        else:
            out.append(SITE + "/" + e.lstrip("/"))
    return out


def envoyer(urls: list[str]) -> int:
    corps = json.dumps({
        "host": SITE.removeprefix("https://"),
        "key": CLE,
        "keyLocation": f"{SITE}/{CLE}.txt",
        "urlList": urls,
    }).encode("utf-8")

    requete = urllib.request.Request(
        POINT_DE_COLLECTE, data=corps, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            code = reponse.status
    except urllib.error.HTTPError as e:
        # 422 = URL hors domaine ou clé invalide ; 403 = clé non trouvée
        # à keyLocation. Les deux sont des erreurs de configuration, pas
        # des incidents passagers : inutile de réessayer.
        print(f"✗ HTTP {e.code} — {e.reason}", file=sys.stderr)
        detail = e.read().decode("utf-8", "replace").strip()
        if detail:
            print(f"  {detail[:300]}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"✗ envoi impossible : {e.reason}", file=sys.stderr)
        return 1

    # 200 = pris en compte, 202 = accepté, validation de la clé en attente.
    print(f"✓ HTTP {code} — {len(urls)} URL soumises à IndexNow")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*",
                    help="URL ou chemins à signaler (défaut : tout le sitemap)")
    ap.add_argument("--envoyer", action="store_true",
                    help="envoyer réellement (sinon, contrôle seul)")
    args = ap.parse_args()

    erreurs = verifier()
    for e in erreurs:
        print(f"✗ {e}", file=sys.stderr)
    if erreurs:
        print(f"\n{len(erreurs)} anomalie(s) — rien n'est envoyé.", file=sys.stderr)
        return 1

    try:
        urls = normaliser(args.urls) if args.urls else urls_du_sitemap()
    except Anomalie as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1

    if len(urls) > MAX_URLS:
        print(f"✗ {len(urls)} URL pour {MAX_URLS} au maximum par envoi",
              file=sys.stderr)
        return 1

    print(f"✓ clé {CLE} publiée dans {FICHIER_CLE.name}")
    print(f"✓ {len(urls)} URL prêtes :")
    for u in urls[:5]:
        print(f"    {u}")
    if len(urls) > 5:
        print(f"    … et {len(urls) - 5} autres")

    if not args.envoyer:
        print("\n  (contrôle seul, rien envoyé — ajouter --envoyer)")
        return 0

    return envoyer(urls)


if __name__ == "__main__":
    sys.exit(main())
