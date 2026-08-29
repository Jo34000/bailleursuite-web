#!/usr/bin/env python3
"""FAQPage : le HTML visible fait foi, le JSON-LD en découle.

Google exige que le contenu balisé en `FAQPage` soit visible sur la
page. Le comparatif balisait deux questions qui n'existaient nulle
part dans le corps, pendant que les cinq questions réellement
affichées n'étaient pas balisées du tout — perte du rich result d'un
côté, risque d'action manuelle de l'autre. Rien dans le build ne
l'aurait signalé.

Deux niveaux de rigueur, parce que les deux pages ne se maintiennent
pas de la même façon :

  GENERE  — le JSON-LD est produit mot pour mot depuis le HTML. Toute
            divergence est une erreur, corrigible par --appliquer.
  PARITE  — les intitulés du JSON-LD sont des reformulations SEO
            assumées des titres d'accordéon (cas de /aide, 63
            questions écrites à la main). On ne compare donc que le
            NOMBRE : une question ajoutée au HTML sans son pendant
            balisé, ou l'inverse, reste détectée.

    python3 tools/faq_jsonld.py             # contrôle
    python3 tools/faq_jsonld.py --appliquer # régénère les pages GENERE
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

GENERE, PARITE = "genere", "parite"

# page -> (mode, motif d'extraction des questions visibles)
PAGES: dict[str, tuple[str, re.Pattern]] = {
    "comparatif-logiciel-gestion-locative/index.html": (
        GENERE,
        re.compile(
            r'<button class="faq-q"[^>]*>\s*(?P<q>.*?)\s*<span class="faq-icon">.*?'
            r'<div class="faq-a">\s*(?P<r>.*?)\s*</div>', re.S),
    ),
    "application-gestion-locative-iphone/index.html": (
        GENERE,
        re.compile(
            r'<button class="faq-q"[^>]*>\s*(?P<q>.*?)\s*<span class="faq-icon">.*?'
            r'<div class="faq-a">\s*(?P<r>.*?)\s*</div>', re.S),
    ),
    "aide/index.html": (
        PARITE,
        re.compile(
            r'<button class="aide-item-trigger"[^>]*>\s*(?P<q>.*?)\s*'
            r'<span class="aide-chevron".*?<div class="aide-item-content">\s*'
            r'(?P<r>.*?)\s*</div>', re.S),
    ),
}

_BLOC_FAQ = re.compile(
    r'(<script type="application/ld\+json">\s*)'
    r'(\{"@context":"https://schema\.org","@type":"FAQPage".*?\})'
    r'(\s*</script>)', re.S)


def texte_brut(fragment: str) -> str:
    """Texte lisible d'un fragment HTML : le JSON-LD ne porte pas de balises."""
    t = re.sub(r"<br\s*/?>", " ", fragment)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", html.unescape(t).replace(" ", " ")).strip()


def questions_visibles(texte: str, motif: re.Pattern) -> list[tuple[str, str]]:
    return [(texte_brut(m.group("q")), texte_brut(m.group("r")))
            for m in motif.finditer(texte)]


def bloc_faq(texte: str) -> re.Match | None:
    return _BLOC_FAQ.search(texte)


def construire(paires: list[tuple[str, str]]) -> str:
    return json.dumps(
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": r}}
                        for q, r in paires]},
        ensure_ascii=False, separators=(",", ":"))


def verifier() -> list[str]:
    erreurs: list[str] = []
    for rel, (mode, motif) in PAGES.items():
        page = RACINE / rel
        if not page.exists():
            erreurs.append(f"{rel} : fichier introuvable")
            continue
        texte = page.read_text(encoding="utf-8")
        visibles = questions_visibles(texte, motif)
        m = bloc_faq(texte)
        if not m:
            erreurs.append(f"{rel} : aucun bloc JSON-LD FAQPage")
            continue
        balisees = json.loads(m.group(2))["mainEntity"]

        if not visibles:
            erreurs.append(f"{rel} : aucune question visible détectée")
            continue

        if len(visibles) != len(balisees):
            erreurs.append(
                f"{rel} : {len(balisees)} question(s) balisée(s) pour "
                f"{len(visibles)} affichée(s)")

        if mode is GENERE:
            attendu = construire(visibles)
            if m.group(2) != attendu:
                inconnues = [e["name"] for e in balisees
                             if e["name"] not in {q for q, _ in visibles}]
                detail = (f" — balisé sans être affiché : {inconnues}"
                          if inconnues else "")
                erreurs.append(
                    f"{rel} : le FAQPage diverge du HTML{detail}. "
                    f"Google exige que le contenu balisé soit visible sur "
                    f"la page. Lancer --appliquer.")
    return erreurs


def appliquer() -> int:
    """Régénère le JSON-LD des pages GENERE. Idempotent."""
    reecrites = 0
    for rel, (mode, motif) in PAGES.items():
        if mode is not GENERE:
            continue
        page = RACINE / rel
        texte = page.read_text(encoding="utf-8")
        m = bloc_faq(texte)
        if not m:
            continue
        nouveau = construire(questions_visibles(texte, motif))
        if nouveau != m.group(2):
            page.write_text(texte[:m.start(2)] + nouveau + texte[m.end(2):],
                            encoding="utf-8")
            reecrites += 1
    return reecrites


def main() -> int:
    if "--appliquer" in sys.argv:
        print(f"{appliquer()} page(s) régénérée(s)")
    erreurs = verifier()
    for e in erreurs:
        print("✗", e, file=sys.stderr)
    for rel, (mode, motif) in PAGES.items():
        n = len(questions_visibles((RACINE / rel).read_text(encoding="utf-8"), motif))
        print(f"{rel} : {n} questions ({mode})")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
