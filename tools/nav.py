#!/usr/bin/env python3
"""Navigation du site : une seule source pour la barre, le menu mobile et le
pied de page de toutes les pages.

    python3 tools/nav.py              # contrôle : pages et gabarits à jour ?
    python3 tools/nav.py --appliquer  # réécrit les blocs dans les pages

Les groupes sont définis ici, une fois : L'application, Outils gratuits,
Guides, puis le Centre d'aide en lien secondaire. Le script :

- remplace l'en-tête et le pied de page des pages statiques, entre les
  marqueurs <!-- nav:debut --> / <!-- nav:fin --> et
  <!-- pied:debut --> / <!-- pied:fin --> (posés au premier passage) ;
- écrit les gabarits Radar tools/templates/_header.j2 et _footer.j2 ;
- met aussi à jour les pages Radar déjà générées, en y rendant ces mêmes
  gabarits : elles restent identiques à ce que produira le prochain
  build, sans attendre la reconstruction ;
- s'assure que chaque page charge /styles/nav.css et /scripts/nav.js.

La page courante porte aria-current="page" (aria-current="true" pour les
pages de ville et la méthodologie du Radar, rattachées à « Radar
immobilier »). Aucune URL n'est modifiée : l'accueil garde ses liens
relatifs, les autres pages leurs liens absolus.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from jinja2 import Template

RACINE = Path(__file__).resolve().parent.parent
GABARITS = RACINE / "tools" / "templates"
SITE = "https://bailleursuite.fr"

# (titre du groupe, titre court pour la barre, [(chemin, libellé, sous-libellé)])
GROUPES = [
    ("L'application", "L'application", [
        ("/application-gestion-locative-iphone", "L'app BailleurSuite", "iPhone, iPad et Mac"),
        ("/comparatif-logiciel-gestion-locative", "Comparatif des logiciels", None),
    ]),
    ("Outils gratuits", "Outils", [
        ("/quittance-loyer-pdf-gratuit", "Quittance PDF gratuite", None),
        ("/calculatrice-rendement-locatif", "Calculatrice de rendement", None),
        ("/radar-immobilier", "Radar immobilier", None),
    ]),
    ("Guides", "Guides", [
        ("/declaration-2044-guide", "Déclaration 2044", None),
        ("/lmnp-guide-complet", "Guide LMNP", None),
        ("/loi-de-finances-bailleurs", "Loi de finances", None),
    ]),
]
AIDE = ("/aide", "Centre d'aide")
RADAR = "/radar-immobilier"

# Mention propre aux deux comparatifs, conservée dans leur pied de page.
NOTE_COMPARATIF = ("Informations à caractère général, non substituables à un "
                   "conseil fiscal personnalisé.")

# Page statique -> (base des liens, chemin courant[, note de bas de page])
PAGES = {
    "index.html": ("", "/"),
    "aide/index.html": (SITE, "/aide"),
    "application-gestion-locative-iphone/index.html": (SITE, "/application-gestion-locative-iphone", NOTE_COMPARATIF),
    "calculatrice-rendement-locatif/index.html": (SITE, "/calculatrice-rendement-locatif"),
    "comparatif-logiciel-gestion-locative/index.html": (SITE, "/comparatif-logiciel-gestion-locative", NOTE_COMPARATIF),
    "conditions-utilisation.html": (SITE, "/conditions-utilisation.html"),
    "declaration-2044-guide/index.html": (SITE, "/declaration-2044-guide"),
    "lmnp-guide-complet/index.html": (SITE, "/lmnp-guide-complet"),
    "loi-de-finances-bailleurs/index.html": (SITE, "/loi-de-finances-bailleurs"),
    "politique-confidentialite.html": (SITE, "/politique-confidentialite.html"),
    "quittance-loyer-pdf-gratuit/index.html": (SITE, "/quittance-loyer-pdf-gratuit"),
}

LOGO_SVG = '''      <svg width="30" height="30" viewBox="0 0 320 320" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <linearGradient id="eg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#2D6A4F"/><stop offset="1" stop-color="#3D8B68"/>
          </linearGradient>
        </defs>
        <rect width="320" height="320" rx="70" fill="url(#eg)"/>
        <g transform="scale(1.6)"><g transform="translate(-14,0.8)">
          <path d="M 66 150 L 66 70 L 90 44 L 120 44 Q 152 44 152 68 Q 152 92 120 92 Q 156 98 156 122 Q 156 150 120 150 Z M 96 64 L 96 91 L 113 91 Q 126 91 126 77.5 Q 126 64 113 64 Z M 96 99 L 96 130 L 117 130 Q 130 130 130 114.5 Q 130 99 117 99 Z" fill="#FFFFFF" fill-rule="evenodd"/>
        </g></g>
      </svg>'''
CHEVRON = ('<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
           'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
           '<path d="m6 9 6 6 6-6"/></svg>')
APPSTORE = "https://apps.apple.com/app/apple-store/id6772793420?pt=128946892&amp;ct={ct}&amp;mt=8"

# Marqueur du lien Radar dans les gabarits : sa valeur dépend de la page
# rendue (« page » sur le hub, « true » sur les villes et la méthodologie).
JINJA_RADAR = '{{ nav_radar | default("true") }}'


def _courant(chemin: str, courant: str | None) -> str:
    if courant == "jinja" and chemin == RADAR:
        return f' aria-current="{JINJA_RADAR}"'
    return ' aria-current="page"' if chemin == courant else ""


def _libelle(lib: str, sous: str | None) -> str:
    return f'{lib}<span class="nav-sous">{sous}</span>' if sous else lib


def entete(base: str, courant: str | None) -> str:
    """En-tête : barre (ordinateur) et menu mobile."""
    L = ["<!-- nav:debut — produit par tools/nav.py, ne pas modifier à la main -->",
         "<header>",
         '<nav class="site-nav" aria-label="Navigation principale">',
         f'  <a class="nav-logo" href="{base}/">',
         '    <div class="nav-logo-icon">', LOGO_SVG, "    </div>",
         '    Bailleur<span class="nav-logo-suite">Suite</span>',
         "  </a>",
         '  <ul class="nav-groupes">']
    for i, (_titre, court, liens) in enumerate(GROUPES):
        dedans = courant == "jinja" and any(c == RADAR for c, _, _ in liens) \
            or any(c == courant for c, _, _ in liens)
        classe = "nav-link nav-drop-trigger" + (" est-courant" if dedans else "")
        L += ['    <li class="nav-drop">',
              f'      <button type="button" class="{classe}" aria-expanded="false" '
              f'aria-controls="nav-groupe-{i}">{court} {CHEVRON}</button>',
              f'      <ul class="nav-drop-menu" id="nav-groupe-{i}">']
        for chemin, lib, sous in liens:
            L.append(f'        <li><a href="{base}{chemin}"{_courant(chemin, courant)}>'
                     f'{_libelle(lib, sous)}</a></li>')
        L += ["      </ul>", "    </li>"]
    L += ["  </ul>",
          f'  <a class="nav-cta" href="{APPSTORE.format(ct="nav")}" target="_blank" rel="noopener" '
          "onclick=\"track('AppStore_Click',{ct:'nav'})\">Essayer BailleurSuite</a>",
          '  <button type="button" class="nav-burger" id="nav-burger" aria-expanded="false" '
          'aria-controls="nav-mobile-menu" aria-label="Ouvrir le menu">',
          '    <span class="nav-burger-line"></span>',
          '    <span class="nav-burger-line"></span>',
          '    <span class="nav-burger-line"></span>',
          "  </button>",
          "</nav>",
          '<nav class="nav-mobile-menu" id="nav-mobile-menu" aria-label="Menu">']
    for i, (titre, _court, liens) in enumerate(GROUPES):
        L.append(f'  <p class="nav-groupe-titre" id="nav-mobile-titre-{i}">{titre}</p>')
        L.append(f'  <ul class="nav-groupe" aria-labelledby="nav-mobile-titre-{i}">')
        for chemin, lib, sous in liens:
            L.append(f'    <li><a href="{base}{chemin}"{_courant(chemin, courant)}>'
                     f'<span>{_libelle(lib, sous)}</span></a></li>')
        L.append("  </ul>")
    L += [f'  <a class="nav-aide" href="{base}{AIDE[0]}"{_courant(AIDE[0], courant)}>{AIDE[1]}</a>',
          "</nav>",
          "</header>",
          "<!-- nav:fin -->"]
    return "\n".join(L)


def pied(base: str, note: str | None = None) -> str:
    """Pied de page : trois colonnes, ligne d'aide et mentions, script."""
    L = ["<!-- pied:debut — produit par tools/nav.py, ne pas modifier à la main -->",
         '<footer class="site-footer">',
         '  <div class="site-footer-inner">',
         '    <nav class="site-footer-cols" aria-label="Plan du site">']
    for i, (titre, _court, liens) in enumerate(GROUPES):
        L += ['      <div class="site-footer-col">',
              f'        <p class="site-footer-titre" id="pied-titre-{i}">{titre}</p>',
              f'        <ul aria-labelledby="pied-titre-{i}">']
        for chemin, lib, _sous in liens:
            L.append(f'          <li><a href="{base}{chemin}">{lib}</a></li>')
        L += ["        </ul>", "      </div>"]
    L += ["    </nav>",
          '    <p class="site-footer-liens">'
          f'<a href="{base}{AIDE[0]}">{AIDE[1]}</a><span class="site-footer-sep">·</span>'
          f'<a href="{base}/conditions-utilisation.html">CGU</a><span class="site-footer-sep">·</span>'
          f'<a href="{base}/politique-confidentialite.html">Confidentialité</a></p>',
          '    <div class="site-footer-bottom">',
          "      <p>© 2026 BailleurSuite · Édité par Joachim ANTONA, EI · SIREN 104 828 579</p>",
          *([f"      <p>{note}</p>"] if note else []),
          "      <p>",
          f'        <a href="{APPSTORE.format(ct="footer")}" target="_blank" rel="noopener" '
          "onclick=\"track('AppStore_Click',{ct:'footer'})\">Télécharger sur l'App Store</a>",
          '        <button type="button" data-bs-consent="ouvrir">Gérer les cookies</button>',
          '        <a href="mailto:contact@bailleursuite.fr">Contact</a>',
          "      </p>",
          "    </div>",
          "  </div>",
          "</footer>",
          '<script defer src="/scripts/nav.js"></script>',
          "<!-- pied:fin -->"]
    return "\n".join(L)


# ── Remplacement dans les pages ────────────────────────────────────────
MARQ_NAV = re.compile(r"<!-- nav:debut.*?<!-- nav:fin -->", re.S)
MARQ_PIED = re.compile(r"<!-- pied:debut.*?<!-- pied:fin -->", re.S)
# Anciennes formes, remplacées au premier passage.
ANCIEN_NAV = [
    re.compile(r"<header>\s*<nav class=\"site-nav\".*?</header>", re.S),
    re.compile(r"<nav>\s*<a href=\"[^\"]*\" class=\"nav-logo\">.*?</nav>\s*"
               r"<div class=\"nav-mobile-menu\" id=\"nav-mobile-menu\">.*?\n</div>", re.S),
]
ANCIEN_PIED = re.compile(r"<footer(?: class=\"site-footer\")?>.*?</footer>", re.S)
ANCIEN_SCRIPT = re.compile(
    r"\n?<script>\s*\(function\(\)\{\s*var b=document\.getElementById\('nav-burger'\).*?\}\)\(\);\s*</script>",
    re.S)
LIEN_CSS = '<link rel="stylesheet" href="/styles/nav.css">'


def remplacer(texte: str, rel: str, nav: str, pied_html: str) -> str:
    if MARQ_NAV.search(texte):
        texte = MARQ_NAV.sub(lambda _: nav, texte, count=1)
    else:
        for motif in ANCIEN_NAV:
            if motif.search(texte):
                texte = motif.sub(lambda _: nav, texte, count=1)
                break
        else:
            raise SystemExit(f"{rel} : en-tête introuvable")
    if MARQ_PIED.search(texte):
        texte = MARQ_PIED.sub(lambda _: pied_html, texte, count=1)
    else:
        if not ANCIEN_PIED.search(texte):
            raise SystemExit(f"{rel} : pied de page introuvable")
        texte = ANCIEN_PIED.sub(lambda _: pied_html, texte, count=1)
        texte = ANCIEN_SCRIPT.sub("", texte, count=1)
    if LIEN_CSS not in texte:
        for ancre in ('<link rel="stylesheet" href="/styles/radar.css">',
                      '<link rel="stylesheet" href="/styles/design-system.css">',
                      '<link rel="stylesheet" href="/styles/fonts.css">'):
            if ancre in texte:
                texte = texte.replace(ancre, ancre + "\n" + LIEN_CSS, 1)
                break
        else:
            raise SystemExit(f"{rel} : aucune feuille de style d'ancrage pour nav.css")
    return texte


def gabarits() -> dict[Path, str]:
    """Contenu attendu des gabarits Radar."""
    return {
        GABARITS / "_header.j2": entete("{{ SITE }}", "jinja") + "\n",
        GABARITS / "_footer.j2": pied("{{ SITE }}") + "\n",
    }


def pages_radar() -> list[tuple[Path, str]]:
    """Pages Radar générées et valeur de aria-current du lien Radar."""
    out = []
    hub = RACINE / "radar-immobilier" / "index.html"
    if hub.exists():
        out.append((hub, "page"))
    for p in sorted((RACINE / "radar-immobilier").glob("*/index.html")):
        out.append((p, "true"))
    return out


def attendu_radar(valeur: str) -> tuple[str, str]:
    entete_j2, pied_j2 = gabarits().values()
    # Rendu comme le fait build_radar.py : l'inclusion d'un gabarit ne
    # garde pas son saut de ligne final.
    return (Template(entete_j2).render(SITE=SITE, nav_radar=valeur),
            Template(pied_j2).render(SITE=SITE))


def traiter(appliquer: bool) -> list[str]:
    ecarts: list[str] = []

    for fichier, contenu in gabarits().items():
        if not fichier.exists() or fichier.read_text(encoding="utf-8") != contenu:
            ecarts.append(str(fichier.relative_to(RACINE)))
            if appliquer:
                fichier.write_text(contenu, encoding="utf-8")

    cibles = [(RACINE / rel, entete(v[0], v[1]), pied(v[0], *v[2:]))
              for rel, v in PAGES.items()]
    cibles += [(p, *attendu_radar(v)) for p, v in pages_radar()]

    for fichier, nav, pied_html in cibles:
        rel = str(fichier.relative_to(RACINE))
        texte = fichier.read_text(encoding="utf-8")
        nouveau = remplacer(texte, rel, nav, pied_html)
        if nouveau != texte:
            ecarts.append(rel)
            if appliquer:
                fichier.write_text(nouveau, encoding="utf-8")
    return ecarts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--appliquer", action="store_true")
    args = ap.parse_args()
    ecarts = traiter(args.appliquer)
    if args.appliquer:
        print(f"✓ navigation écrite : {len(ecarts)} fichier(s) modifié(s)")
        return 0
    if ecarts:
        print(f"✗ navigation à régénérer ({len(ecarts)} fichier(s)) — lancer --appliquer :",
              file=sys.stderr)
        for e in ecarts[:20]:
            print(f"    {e}", file=sys.stderr)
        return 1
    print("✓ navigation à jour sur toutes les pages et les gabarits Radar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
