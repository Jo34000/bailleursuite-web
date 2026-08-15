#!/usr/bin/env python3
"""Génère la section Radar Immobilier à partir de data/villes.json.

    python3 tools/build_radar.py                 # build complet
    python3 tools/build_radar.py --check         # ne rien écrire, vérifier
    python3 tools/build_radar.py --data autre.json

Produit :
    radar-immobilier/index.html                  hub + tableau triable
    radar-immobilier/{slug}/index.html           une page par ville
    radar-immobilier/methodologie/index.html     sources, limites, formule
    sitemap.xml                                  régénéré intégralement

Aucune page existante n'est modifiée ici — l'insertion du lien de
navigation est le travail de `tools/add_nav_link.py`.

Principe directeur, hérité du pipeline radar-data : **rien n'est
imputé**. Une donnée absente du JSON produit une mention « non
disponible » explicite, jamais une valeur de repli, jamais une phrase
qui ferait croire à une mesure. Les blocs éditoriaux se déclenchent sur
les données présentes ; ceux qui n'ont pas leur donnée ne sortent pas.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
from datetime import date
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:  # pragma: no cover
    sys.exit("Jinja2 requis : pip install jinja2")

RACINE = Path(__file__).resolve().parent.parent
DIR_TEMPLATES = Path(__file__).resolve().parent / "templates"
DIR_SORTIE = RACINE / "radar-immobilier"
FICHIER_DATA = RACINE / "data" / "villes.json"
FICHIER_SITEMAP = RACINE / "sitemap.xml"

SITE = "https://bailleursuite.fr"

# Les 7 URL déjà en ligne. Elles sont conservées telles quelles : le
# sitemap est régénéré intégralement, pas complété à l'aveugle.
URLS_EXISTANTES = [
    ("/",                                  "2026-08-02", "weekly",  "1.0"),
    ("/calculatrice-rendement-locatif",    "2026-07-14", "monthly", "0.9"),
    ("/declaration-2044-guide",            "2026-06-29", "monthly", "0.8"),
    ("/quittance-loyer-pdf-gratuit",       "2026-06-29", "monthly", "0.8"),
    ("/lmnp-guide-complet",                "2026-07-14", "monthly", "0.8"),
    ("/comparatif-logiciel-gestion-locative", "2026-07-14", "monthly", "0.8"),
    ("/aide",                              "2026-06-29", "monthly", "0.7"),
]

AVERTISSEMENT = (
    "Les indicateurs présentés sont des estimations territoriales issues "
    "de données publiques. Ils ne constituent ni un conseil en "
    "investissement, ni une garantie de rendement, et ne se substituent "
    "pas à l'analyse d'un bien précis."
)


# ══════════════════════════════════════════════════════════════════
# Formatage
# ══════════════════════════════════════════════════════════════════
def slugifier(nom: str) -> str:
    base = unicodedata.normalize("NFKD", nom).lower()
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def entier(valeur) -> str:
    """1234567 -> « 1 234 567 » (espace insécable fine)."""
    if valeur is None:
        return ""
    return f"{round(valeur):,}".replace(",", " ")


def decimal(valeur, n: int = 2) -> str:
    """4.77 -> « 4,77 » — virgule décimale française."""
    if valeur is None:
        return ""
    return f"{valeur:.{n}f}".replace(".", ",")


def signe(valeur, n: int = 1) -> str:
    """0.81 -> « +0,8 » — le signe est porteur de sens, on le garde."""
    if valeur is None:
        return ""
    return ("+" if valeur >= 0 else "−") + decimal(abs(valeur), n)


# ══════════════════════════════════════════════════════════════════
# Accès aux données
# ══════════════════════════════════════════════════════════════════
def val(ville: dict, champ: str):
    """Valeur d'un indicateur, ou None. Jamais de repli."""
    return (ville.get("indicateurs", {}).get(champ) or {}).get("valeur")


def note(ville: dict, champ: str) -> str | None:
    return (ville.get("indicateurs", {}).get(champ) or {}).get("note")


def jsonld_dump(obj: dict) -> str:
    """Sérialise un bloc JSON-LD pour insertion directe dans <script>.

    Le template l'injecte avec `|safe` — sans quoi l'autoescape de Jinja
    transformerait les guillemets en `&#34;` et Google ne lirait rien.
    En contrepartie, « < » est neutralisé en `\u003c` : c'est la seule
    séquence par laquelle une donnée pourrait fermer le <script> et
    injecter du balisage.
    """
    return json.dumps(
        obj, ensure_ascii=False, separators=(",", ":")
    ).replace("<", "\\u003c")


def mediane(villes: list[dict], champ: str) -> float | None:
    valeurs = [v for v in (val(x, champ) for x in villes) if v is not None]
    return statistics.median(valeurs) if valeurs else None


def quantile(villes: list[dict], champ: str, part: float) -> float | None:
    """Valeur au rang `part` (0–1) de la distribution du panel.

    Sert à caler les variantes éditoriales sur la forme réelle des
    données plutôt que sur un écart en pourcentage choisi à l'avance.
    """
    valeurs = sorted(v for v in (val(x, champ) for x in villes) if v is not None)
    if not valeurs:
        return None
    rang = min(int(round(part * (len(valeurs) - 1))), len(valeurs) - 1)
    return valeurs[rang]


# ══════════════════════════════════════════════════════════════════
# Seuils éditoriaux
# ══════════════════════════════════════════════════════════════════
# Chaque seuil est explicite et unique : un lecteur doit pouvoir
# reconstituer pourquoi une phrase est apparue sur telle ville.
ECART_MEDIANE_NET = 0.15       # 15 % d'écart au panel = écart signalé
CROISSANCE_FORTE = 0.7         # %/an
CROISSANCE_MOLLE = 0.1
DECROISSANCE = -0.1
VACANCE_ELEVEE = 10.0          # %
VACANCE_FAIBLE = 6.0
EVOL3_FORTE = 12.0             # % sur 3 ans
EVOL3_BAISSE = -2.0
TENSION_MENAGES = 0.52         # part de petits ménages -> tension locative


def position_rendement(rdt: float | None, med: float | None) -> str | None:
    """Situe un rendement par rapport à la médiane du panel, en clair.

    Affiché sous le chiffre : « médiane du panel : 6,06 % » laissait le
    lecteur faire la comparaison lui-même. On la fait pour lui.
    """
    if rdt is None or not med:
        return None
    ecart = (rdt - med) / med
    if ecart >= ECART_MEDIANE_NET:
        rang = "nettement supérieur à"
    elif ecart >= 0.02:
        rang = "supérieur à"
    elif ecart <= -ECART_MEDIANE_NET:
        rang = "nettement inférieur à"
    elif ecart <= -0.02:
        rang = "inférieur à"
    else:
        rang = "au niveau de"
    return f"{rang} la médiane du panel ({decimal(med)} %)"


def accroche(ville: dict, ctx: dict) -> tuple[str, str]:
    """Sous-titre du hero. Retourne (nom de la variante, texte).

    Cinq formulations déclenchées par seuils, plus un cas médian et deux
    replis pour les communes dont le prix ou le loyer manque. Une phrase
    identique sur 40 pages serait un motif dupliqué ; elle serait surtout
    une promesse générique là où la donnée permet de dire quelque chose.

    Les deux premières variantes se déclenchent sur les **quantiles du
    panel**, pas sur un écart en pourcentage figé. Un seuil du type
    « ±15 % autour de la médiane » dépend entièrement de l'étalement de
    la distribution : sur un panel resserré il ne se déclencherait
    jamais, sur un panel étalé il absorberait tout le monde. Les
    quantiles garantissent une répartition stable quel que soit le jeu de
    données — c'est `--stats` qui permet de le vérifier.
    """
    nom = ville["nom"]
    prix = val(ville, "prix_m2")
    loyer = val(ville, "loyer_m2")
    rdt = val(ville, "rendement_brut_pct")
    evol3 = val(ville, "evolution_3ans_pct")
    evol_pop = val(ville, "evolution_pop_pct")
    vacance = val(ville, "taux_vacance_pct")
    med_rdt, med_prix = ctx["med_rendement"], ctx["med_prix"]

    chiffres = (
        f"Prix médian de {entier(prix)} €/m², loyer de marché à "
        f"{decimal(loyer)} €/m² et rendement brut de {decimal(rdt)} %."
    ) if prix is not None and rdt is not None else None

    # ── Communes sans rendement calculable ────────────────────────
    if chiffres is None:
        if prix is not None:
            return "sans_loyer", (
                f"Prix médian de {entier(prix)} €/m² d'après les ventes "
                "réellement signées. Le loyer de marché n'est pas publiable "
                "ici, faute d'annonces en nombre suffisant."
            )
        return "sans_prix", (
            "Population, vacance et dynamique du marché locatif d'après les "
            "données publiques. Le prix médian n'est pas disponible pour "
            "cette commune sur ce millésime."
        )

    # ── 1. Haut de panel pour le rendement (quintile supérieur) ───
    if ctx["rdt_haut"] is not None and rdt >= ctx["rdt_haut"]:
        return "rendement_haut", chiffres + (
            f" {nom} se situe dans le haut du panel pour le rendement, "
            f"contre {decimal(med_rdt)} % en médiane — un écart qui tient "
            "davantage au prix d'achat qu'au niveau des loyers."
        )

    # ── 2. Bas de panel (quintile inférieur) ──────────────────────
    if ctx["rdt_bas"] is not None and rdt <= ctx["rdt_bas"]:
        if med_prix and prix >= ctx["prix_haut"]:
            return "marche_cher", chiffres + (
                " Un marché cher, où le rendement passe après la valeur du "
                f"bien : {decimal(med_rdt)} % en médiane sur le panel."
            )
        return "rendement_bas", chiffres + (
            f" Le rendement reste en retrait des {decimal(med_rdt)} % "
            "médians du panel."
        )

    # ── 3. Marché qui s'est fortement apprécié ────────────────────
    if evol3 is not None and evol3 >= EVOL3_FORTE:
        return "appreciation", chiffres + (
            f" Les prix ont pris {signe(evol3)} % en trois ans : le point "
            "d'entrée n'est plus celui d'hier."
        )

    # ── 4. Démographie porteuse ───────────────────────────────────
    if evol_pop is not None and evol_pop >= CROISSANCE_FORTE:
        return "demographie", chiffres + (
            f" Une commune qui gagne des habitants ({signe(evol_pop)} % par "
            "an), ce qui soutient la demande locative."
        )

    # ── 5. Parc largement vacant ──────────────────────────────────
    if vacance is not None and vacance >= VACANCE_ELEVEE:
        return "vacance", chiffres + (
            f" Avec {decimal(vacance, 1)} % de logements vacants, la "
            "continuité de la location mérite d'être vérifiée."
        )

    # ── 6. Milieu de panel : rien ne dépasse ──────────────────────
    return "milieu_panel", chiffres + (
        f" Des niveaux proches de la médiane du panel ({entier(med_prix)} "
        f"€/m² pour {decimal(med_rdt)} %), sans écart marquant."
    )


def blocs_editoriaux(ville: dict, ctx: dict) -> list[dict]:
    """Blocs de commentaire déclenchés par les données de la ville.

    Retourne une liste de {titre, corps}. Une ville dont un indicateur
    manque n'obtient tout simplement pas le bloc correspondant : rien
    n'est comblé par une formule passe-partout.
    """
    nom = ville["nom"]
    blocs: list[dict] = []

    rdt = val(ville, "rendement_brut_pct")
    prix = val(ville, "prix_m2")
    loyer = val(ville, "loyer_m2")
    evol_pop = val(ville, "evolution_pop_pct")
    vacance = val(ville, "taux_vacance_pct")
    evol3 = val(ville, "evolution_3ans_pct")
    pop = val(ville, "population")
    menages = val(ville, "menages")
    revenu = val(ville, "revenu_median")

    med_rdt, med_prix = ctx["med_rendement"], ctx["med_prix"]

    # ── 1. Rendement brut face à la médiane du panel ──────────────
    if rdt is not None and med_rdt:
        ecart = (rdt - med_rdt) / med_rdt
        if ecart >= ECART_MEDIANE_NET:
            corps = (
                f"À {decimal(rdt)} %, le rendement brut de {nom} dépasse "
                f"nettement la médiane du panel ({decimal(med_rdt)} %). "
                "Ce type d'écart traduit le plus souvent des prix d'achat "
                "contenus davantage que des loyers élevés — c'est le "
                "rapport entre les deux qu'il faut regarder, pas le "
                "rendement seul."
            )
        elif ecart <= -ECART_MEDIANE_NET:
            corps = (
                f"À {decimal(rdt)} %, le rendement brut de {nom} se situe "
                f"sous la médiane du panel ({decimal(med_rdt)} %). Les "
                "marchés tendus se paient : le prix au mètre carré y "
                "progresse généralement plus vite que les loyers, que "
                "l'encadrement ou la solvabilité des locataires plafonnent."
            )
        else:
            corps = (
                f"À {decimal(rdt)} %, le rendement brut de {nom} reste "
                f"proche de la médiane du panel ({decimal(med_rdt)} %). "
                "L'arbitrage se joue alors sur des critères que ces "
                "indicateurs ne captent pas : quartier, état du bien, "
                "charges de copropriété, fiscalité applicable."
            )
        blocs.append({"titre": "Ce que dit le rendement", "corps": corps})

    # ── 2. Prix au m² face à la médiane du panel ──────────────────
    if prix is not None and med_prix:
        ecart = (prix - med_prix) / med_prix
        if ecart >= ECART_MEDIANE_NET:
            corps = (
                f"Le prix médian s'établit à {entier(prix)} €/m², au-dessus "
                f"de la médiane du panel ({entier(med_prix)} €/m²). Le "
                "ticket d'entrée est donc plus élevé : à surface égale, "
                "l'apport et la mensualité de crédit pèsent davantage sur "
                "l'équilibre de l'opération."
            )
        elif ecart <= -ECART_MEDIANE_NET:
            corps = (
                f"Le prix médian s'établit à {entier(prix)} €/m², sous la "
                f"médiane du panel ({entier(med_prix)} €/m²). Un ticket "
                "d'entrée modéré laisse plus de marge pour financer des "
                "travaux, mais impose de regarder de près l'état du parc "
                "et la demande locative réelle."
            )
        else:
            corps = (
                f"Le prix médian s'établit à {entier(prix)} €/m², dans le "
                f"voisinage de la médiane du panel ({entier(med_prix)} €/m²)."
            )
        if loyer is not None:
            corps += (
                f" Au loyer d'annonce de {decimal(loyer)} €/m², il faut "
                f"environ {decimal(prix / loyer / 12, 1)} années de loyer "
                "brut pour couvrir le prix d'achat, hors charges et "
                "fiscalité."
            )
        blocs.append({"titre": "Le niveau de prix", "corps": corps})

    # ── 3. Dynamique démographique — trois paliers ────────────────
    if evol_pop is not None:
        if evol_pop >= CROISSANCE_FORTE:
            corps = (
                f"La population progresse de {signe(evol_pop)} % par an. "
                "Une croissance de cet ordre alimente mécaniquement la "
                "demande de logements, et soutient à la fois les loyers et "
                "les prix — c'est le facteur le plus structurant du marché "
                "local à horizon dix ans."
            )
        elif evol_pop >= CROISSANCE_MOLLE:
            corps = (
                f"La population progresse de {signe(evol_pop)} % par an, "
                "une croissance modérée. Le marché n'est ni porté ni "
                "pénalisé par la démographie : la demande locative dépend "
                "davantage du tissu économique local et de la présence "
                "d'étudiants ou d'actifs mobiles."
            )
        elif evol_pop >= DECROISSANCE:
            corps = (
                "La population est stable. Sans moteur démographique, la "
                "valorisation à long terme repose sur d'autres leviers : "
                "arrivée d'équipements, desserte, renouvellement du parc."
            )
        else:
            corps = (
                f"La population recule de {decimal(abs(evol_pop))} % par "
                "an. Une démographie orientée à la baisse pèse durablement "
                "sur la demande locative et sur la revente : c'est le "
                "signal qui mérite le plus d'attention avant d'investir."
            )
        # La phrase de cadrage est autonome : chaque branche ci-dessus est
        # déjà une phrase complète, on préfixe sans jamais la réécrire.
        if pop is not None:
            corps = f"{nom} compte {entier(pop)} habitants. " + corps
        blocs.append({"titre": "La dynamique démographique", "corps": corps})

    # ── 4. Taux de vacance ────────────────────────────────────────
    if vacance is not None:
        if vacance >= VACANCE_ELEVEE:
            corps = (
                f"{decimal(vacance, 1)} % des logements sont vacants, un "
                "niveau élevé. Un parc partiellement inoccupé signale une "
                "offre supérieure à la demande, ou un parc ancien "
                "difficile à louer en l'état. Le rendement affiché suppose "
                "une location continue : cette hypothèse est ici la plus "
                "fragile."
            )
        elif vacance <= VACANCE_FAIBLE:
            corps = (
                f"{decimal(vacance, 1)} % des logements sont vacants, un "
                "niveau bas. Un parc peu vacant traduit une demande qui "
                "absorbe l'offre, et limite le risque de périodes sans "
                "locataire entre deux baux."
            )
        else:
            corps = (
                f"{decimal(vacance, 1)} % des logements sont vacants, dans "
                "la moyenne des villes françaises. Ce niveau n'appelle ni "
                "inquiétude ni optimisme particulier."
            )
        blocs.append({"titre": "La vacance du parc", "corps": corps})

    # ── 5. Évolution des prix sur 3 ans ───────────────────────────
    if evol3 is not None:
        if evol3 >= EVOL3_FORTE:
            corps = (
                f"Les prix ont progressé de {signe(evol3)} % sur trois "
                "ans. Une hausse de cette ampleur récompense les acquéreurs "
                "déjà en place, mais dégrade le rendement accessible "
                "aujourd'hui : on achète le marché après la hausse, pas "
                "avant."
            )
        elif evol3 <= EVOL3_BAISSE:
            corps = (
                f"Les prix ont reculé de {decimal(abs(evol3), 1)} % sur "
                "trois ans. Un marché en repli améliore mécaniquement le "
                "rendement à l'achat, à condition que la baisse traduise un "
                "ajustement et non un décrochage durable de la demande."
            )
        else:
            corps = (
                f"Les prix ont évolué de {signe(evol3)} % sur trois ans, "
                "soit une relative stabilité. Un marché sans à-coup facilite "
                "l'estimation d'un bien, et rend le rendement d'entrée plus "
                "prévisible."
            )
        blocs.append({"titre": "L'évolution sur trois ans", "corps": corps})

    # ── 6. Structure des ménages (bonus si la donnée est là) ──────
    if pop and menages:
        taille = pop / menages
        # « 1,97 personne » : en français le pluriel ne s'installe qu'à 2.
        unite = "personne" if taille < 2 else "personnes"
        constat = (
            f"On compte {entier(menages)} ménages pour {entier(pop)} "
            f"habitants, soit {decimal(taille, 2)} {unite} par ménage en "
            "moyenne."
        )
        if taille <= 1 / TENSION_MENAGES:
            corps = constat + (
                " Cette structure de petits ménages — étudiants, jeunes "
                "actifs, personnes seules — oriente la demande vers les "
                "studios et deux-pièces."
            )
        else:
            corps = constat + (
                " La demande porte davantage sur des logements familiaux "
                "que sur des petites surfaces."
            )
        if revenu is not None:
            corps += (
                f" Le revenu médian local est de {entier(revenu)} € par an, "
                "ce qui borne en pratique le loyer soutenable."
            )
        blocs.append({"titre": "Qui habite ici", "corps": corps})

    return blocs


def points_favorables(ville: dict, ctx: dict) -> list[str]:
    """3 à 5 points favorables, dérivés des seuils. Jamais de texte fixe."""
    p: list[str] = []
    rdt = val(ville, "rendement_brut_pct")
    prix = val(ville, "prix_m2")
    evol_pop = val(ville, "evolution_pop_pct")
    vacance = val(ville, "taux_vacance_pct")
    evol3 = val(ville, "evolution_3ans_pct")
    tx = val(ville, "nb_transactions_12m")
    revenu = val(ville, "revenu_median")
    med_rdt, med_prix = ctx["med_rendement"], ctx["med_prix"]

    if rdt is not None and med_rdt and rdt >= med_rdt:
        p.append(
            f"Rendement brut de {decimal(rdt)} %, au-dessus de la médiane "
            f"du panel ({decimal(med_rdt)} %)."
        )
    if prix is not None and med_prix and prix <= med_prix:
        p.append(
            f"Ticket d'entrée contenu : {entier(prix)} €/m², sous la "
            f"médiane du panel ({entier(med_prix)} €/m²)."
        )
    if evol_pop is not None and evol_pop >= CROISSANCE_FORTE:
        p.append(
            f"Population en croissance de {signe(evol_pop)} % par an, qui "
            "soutient la demande locative."
        )
    elif evol_pop is not None and evol_pop >= CROISSANCE_MOLLE:
        p.append(f"Population en légère progression ({signe(evol_pop)} % par an).")
    if vacance is not None and vacance <= VACANCE_FAIBLE:
        p.append(
            f"Vacance basse ({decimal(vacance, 1)} % du parc) : le risque "
            "de logement inoccupé est limité."
        )
    # Une hausse forte n'est PAS portée au crédit de la ville : elle
    # dégrade le point d'entrée, et figure à ce titre en vigilance. Seule
    # une progression mesurée — marché qui tient sans s'emballer — est un
    # point favorable. Un même fait ne doit pas apparaître des deux côtés.
    if evol3 is not None and 2.0 <= evol3 < EVOL3_FORTE:
        p.append(
            f"Marché qui tient sans s'emballer : {signe(evol3)} % sur trois "
            "ans, une progression mesurée."
        )
    elif evol3 is not None and evol3 <= EVOL3_BAISSE:
        p.append(
            f"Prix en repli de {decimal(abs(evol3), 1)} % sur trois ans, ce "
            "qui améliore le rendement à l'achat."
        )
    if tx and tx >= 400:
        p.append(
            f"Marché liquide : {entier(tx)} transactions sur douze mois, "
            "ce qui facilite l'achat comme la revente."
        )
    if revenu is not None and revenu >= 24000:
        p.append(
            f"Revenu médian de {entier(revenu)} € par an, favorable à la "
            "solvabilité des locataires."
        )

    # Garantir un minimum de 3 points sans jamais inventer : on retombe
    # sur des constats factuels tirés des données présentes. Chaque repli
    # est conditionné à ce que le fait n'ait PAS déjà servi plus haut —
    # sans quoi le même chiffre apparaîtrait deux fois dans la liste.
    if len(p) < 3 and tx and tx < 400:
        p.append(
            f"{entier(tx)} transactions recensées sur douze mois : le prix "
            "médian repose sur un échantillon réel."
        )
    if len(p) < 3 and prix is not None and not (med_prix and prix <= med_prix):
        p.append(f"Prix médian mesuré sur données notariales : {entier(prix)} €/m².")
    if len(p) < 3 and val(ville, "population") is not None:
        p.append(
            f"Commune de {entier(val(ville, 'population'))} habitants, dont "
            "le marché locatif est suffisamment large pour être mesuré."
        )
    return p[:5]


def points_vigilance(ville: dict, ctx: dict) -> list[str]:
    """2 à 4 points de vigilance, dérivés des seuils."""
    p: list[str] = []
    rdt = val(ville, "rendement_brut_pct")
    prix = val(ville, "prix_m2")
    evol_pop = val(ville, "evolution_pop_pct")
    vacance = val(ville, "taux_vacance_pct")
    evol3 = val(ville, "evolution_3ans_pct")
    tx = val(ville, "nb_transactions_12m")
    fi = ville.get("fiabilite", {})
    med_rdt, med_prix = ctx["med_rendement"], ctx["med_prix"]

    if rdt is not None and med_rdt and rdt < med_rdt:
        p.append(
            f"Rendement brut de {decimal(rdt)} %, sous la médiane du panel "
            f"({decimal(med_rdt)} %)."
        )
    if prix is not None and med_prix and prix > med_prix:
        p.append(
            f"Ticket d'entrée élevé : {entier(prix)} €/m², au-dessus de la "
            f"médiane du panel ({entier(med_prix)} €/m²)."
        )
    if evol_pop is not None and evol_pop < DECROISSANCE:
        p.append(
            f"Population en recul de {decimal(abs(evol_pop))} % par an, ce "
            "qui pèse sur la demande à long terme."
        )
    if vacance is not None and vacance >= VACANCE_ELEVEE:
        p.append(
            f"Vacance élevée : {decimal(vacance, 1)} % du parc est inoccupé."
        )
    if evol3 is not None and evol3 >= EVOL3_FORTE:
        p.append(
            f"Prix déjà en forte hausse ({signe(evol3)} % sur trois ans) : "
            "le point d'entrée est moins favorable qu'il y a trois ans."
        )
    if tx is not None and tx < 150:
        p.append(
            f"Marché étroit : {entier(tx)} transactions sur douze mois. Le "
            "prix médian y est plus sensible aux biens atypiques."
        )
    if fi.get("loyer_observations_insuffisantes"):
        p.append(
            "Le loyer de marché repose sur trop peu d'annonces pour être "
            "publié : le rendement n'est pas calculable ici."
        )
    if fi.get("loyer_agrege_depuis_arrondissements"):
        p.append(
            "Le loyer est une moyenne d'arrondissements : il masque des "
            "écarts internes importants selon les quartiers."
        )
    if fi.get("dvf_donnees_insuffisantes"):
        p.append(
            "Le volume de transactions est faible : le prix médian est à "
            "prendre comme un ordre de grandeur."
        )

    if len(p) < 2:
        p.append(
            "Les indicateurs sont communaux : ils lissent des écarts de "
            "prix parfois considérables d'un quartier à l'autre."
        )
    if len(p) < 2:
        p.append(
            "Le rendement affiché est brut : ni charges, ni taxe foncière, "
            "ni vacance, ni fiscalité n'y sont déduites."
        )
    return p[:4]


def villes_comparables(ville: dict, toutes: list[dict], n: int = 4) -> list[dict]:
    """4 communes proches : même département d'abord, puis prix voisins.

    Le département prime — c'est la comparaison qu'un lecteur fait
    spontanément. On complète par proximité de prix au m² pour atteindre
    4 liens, en écartant les villes sans prix mesuré.
    """
    autres = [v for v in toutes if v["code_insee"] != ville["code_insee"]]
    prix = val(ville, "prix_m2")

    meme_dep = [v for v in autres if v["departement"] == ville["departement"]]
    meme_dep.sort(key=lambda v: v["nom"])
    retenues = meme_dep[:n]

    if len(retenues) < n and prix is not None:
        deja = {v["code_insee"] for v in retenues}
        candidats = [
            v for v in autres
            if v["code_insee"] not in deja and val(v, "prix_m2") is not None
        ]
        candidats.sort(key=lambda v: abs(val(v, "prix_m2") - prix))
        retenues += candidats[: n - len(retenues)]

    if len(retenues) < n:  # dernier recours : compléter alphabétiquement
        deja = {v["code_insee"] for v in retenues}
        retenues += [v for v in autres if v["code_insee"] not in deja][: n - len(retenues)]

    return retenues[:n]


# ══════════════════════════════════════════════════════════════════
# Assemblage d'une ville
# ══════════════════════════════════════════════════════════════════
def preparer_ville(ville: dict, toutes: list[dict], ctx: dict) -> dict:
    nom = ville["nom"]
    slug = ville.get("slug") or slugifier(nom)
    prix = val(ville, "prix_m2")
    rdt = val(ville, "rendement_brut_pct")
    loyer = val(ville, "loyer_m2")

    # Title et description construits depuis les données : deux villes
    # ne peuvent pas produire la même balise.
    if prix is not None and rdt is not None:
        titre = f"Investir à {nom} : {entier(prix)} €/m², {decimal(rdt)} % de rendement brut"
        desc = (
            f"Prix médian {entier(prix)} €/m², loyer {decimal(loyer)} €/m² et "
            f"rendement brut {decimal(rdt)} % à {nom}. Population, vacance, "
            "évolution des prix : les chiffres officiels DVF et INSEE, "
            "analysés pour les bailleurs."
        )
    elif prix is not None:
        titre = f"Investir à {nom} : {entier(prix)} €/m² — prix, population, vacance"
        desc = (
            f"Prix médian {entier(prix)} €/m² à {nom}, évolution des prix, "
            "population et taux de vacance. Données officielles DVF et INSEE "
            "pour les bailleurs."
        )
    else:
        titre = f"Investir à {nom} : population, vacance et marché locatif"
        desc = (
            f"Population, vacance et dynamique du marché locatif à {nom}, "
            "d'après les données officielles INSEE. Prix médian non "
            "disponible sur ce millésime."
        )

    canonical = f"{SITE}/radar-immobilier/{slug}"

    breadcrumb = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "Radar immobilier",
             "item": f"{SITE}/radar-immobilier"},
            {"@type": "ListItem", "position": 3, "name": nom, "item": canonical},
        ],
    }
    article = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": titre, "description": desc,
        "image": f"{SITE}/og-image.png",
        "datePublished": f"{ctx['build_date']}T09:00:00+02:00",
        "dateModified": f"{ctx['build_date']}T09:00:00+02:00",
        "inLanguage": "fr",
        "about": {"@type": "Place", "name": nom,
                  "address": {"@type": "PostalAddress",
                              "addressRegion": ville.get("region_nom") or "",
                              "addressCountry": "FR"}},
        "author": {"@type": "Organization", "name": "BailleurSuite", "url": f"{SITE}/"},
        "publisher": {"@type": "Organization", "name": "BailleurSuite", "url": SITE},
    }

    return {
        "v": ville, "nom": nom, "slug": slug, "canonical": canonical,
        "page_title": f"{titre} | BailleurSuite",
        "meta_description": desc[:300],
        "og_title": titre, "og_description": desc[:300],
        "jsonld": [jsonld_dump(article),
                   jsonld_dump(breadcrumb)],
        "accroche": accroche(ville, ctx)[1],
        "variante_accroche": accroche(ville, ctx)[0],
        "position_rendement": position_rendement(rdt, ctx["med_rendement"]),
        "blocs": blocs_editoriaux(ville, ctx),
        "favorables": points_favorables(ville, ctx),
        "vigilance": points_vigilance(ville, ctx),
        "comparables": [
            {"nom": c["nom"], "slug": c.get("slug") or slugifier(c["nom"]),
             "departement": c["departement"],
             "region_nom": c.get("region_nom"),
             "prix": val(c, "prix_m2"), "rdt": val(c, "rendement_brut_pct")}
            for c in villes_comparables(ville, toutes)
        ],
        "note_loyer": note(ville, "loyer_m2"),
        "manquants": ville.get("fiabilite", {}).get("indicateurs_manquants", []),
    }


# ══════════════════════════════════════════════════════════════════
# Vérification des liens
# ══════════════════════════════════════════════════════════════════
# Le header, le footer et le <head> portent légitimement le domaine
# absolu : nav commune à tout le site, canonical, og:url, JSON-LD. Le
# corps de page, lui, doit être entièrement relatif — sinon un build
# servi en local renvoie le visiteur sur la production.
_ZONES_ABSOLU_AUTORISE = (
    re.compile(r"<head>.*?</head>", re.S),
    re.compile(r"<header>.*?</header>", re.S),
    re.compile(r"<footer class=\"site-footer\">.*?</footer>", re.S),
)


def liens_absolus_internes(html_page: str) -> list[str]:
    """Liens du CORPS pointant vers le domaine en absolu. Doit être vide."""
    corps = html_page
    for zone in _ZONES_ABSOLU_AUTORISE:
        corps = zone.sub("", corps)
    return re.findall(rf'href="({re.escape(SITE)}[^"]*)"', corps)


def verifier_liens(pages: list[Path]) -> list[str]:
    """Contrôle bloquant : aucun lien interne absolu hors zones communes."""
    fautifs: list[str] = []
    for page in pages:
        for lien in liens_absolus_internes(page.read_text(encoding="utf-8")):
            fautifs.append(f"{page.relative_to(RACINE)} -> {lien}")
    return fautifs


# ══════════════════════════════════════════════════════════════════
# Sitemap
# ══════════════════════════════════════════════════════════════════
def ecrire_sitemap(villes: list[dict], jour: str) -> int:
    """Régénère le sitemap : 7 URL existantes + hub + méthodo + villes."""
    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    def url(chemin: str, lastmod: str, freq: str, prio: str) -> None:
        lignes.extend([
            "  <url>",
            f"    <loc>{SITE}{chemin}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
            f"    <changefreq>{freq}</changefreq>",
            f"    <priority>{prio}</priority>",
            "  </url>",
        ])

    for chemin, lastmod, freq, prio in URLS_EXISTANTES:
        url(chemin, lastmod, freq, prio)

    url("/radar-immobilier", jour, "weekly", "0.9")
    url("/radar-immobilier/methodologie", jour, "yearly", "0.5")
    for v in sorted(villes, key=lambda x: x["slug"]):
        url(f"/radar-immobilier/{v['slug']}", jour, "monthly", "0.7")

    lignes.append("</urlset>")
    FICHIER_SITEMAP.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return len(URLS_EXISTANTES) + 2 + len(villes)


# ══════════════════════════════════════════════════════════════════
# Build
# ══════════════════════════════════════════════════════════════════
VARIANTES_ACCROCHE = (
    "rendement_haut", "marche_cher", "rendement_bas",
    "appreciation", "demographie", "vacance", "milieu_panel",
    "sans_loyer", "sans_prix",
)


def rapport_distribution(villes: list[dict], ctx: dict) -> int:
    """Répartition des variantes d'accroche sur le jeu de données réel.

    Sert à vérifier qu'aucune variante n'est morte, et qu'aucune n'avale
    la moitié du panel. Retourne le nombre d'alertes.
    """
    rdts = sorted(v for v in (val(x, "rendement_brut_pct") for x in villes)
                  if v is not None)
    print("\n" + "─" * 66)
    print("DISTRIBUTION DES RENDEMENTS")
    print("─" * 66)
    if rdts:
        print(f"  {len(rdts)} villes avec rendement · "
              f"min {decimal(rdts[0])} % · médiane "
              f"{decimal(ctx['med_rendement'])} % · max {decimal(rdts[-1])} %")
        print(f"  quintile bas  ≤ {decimal(ctx['rdt_bas'])} %"
              f"   ·   quintile haut ≥ {decimal(ctx['rdt_haut'])} %")

    compte: dict[str, int] = {v: 0 for v in VARIANTES_ACCROCHE}
    exemples: dict[str, str] = {}
    for ville in villes:
        variante, _ = accroche(ville, ctx)
        compte[variante] += 1
        exemples.setdefault(variante, ville["nom"])

    total = len(villes)
    print("\n" + "─" * 66)
    print("RÉPARTITION DES ACCROCHES")
    print("─" * 66)
    alertes = 0
    for variante in VARIANTES_ACCROCHE:
        n = compte[variante]
        # Les deux replis peuvent légitimement être vides : ils ne
        # concernent que les communes sans loyer ou sans prix.
        repli = variante in ("sans_loyer", "sans_prix")
        if n == 0 and not repli:
            etat, alertes = "✗ jamais déclenchée", alertes + 1
        elif n > total * 0.40:
            etat, alertes = f"✗ absorbe {n / total:.0%} du panel", alertes + 1
        elif n == 0:
            etat = "— sans objet"
        else:
            etat = f"✓ {n / total:.0%}"
        barre = "█" * n
        print(f"  {variante:<16} {n:>3}  {barre:<20} {etat}"
              + (f"   ex. {exemples[variante]}" if n else ""))

    print("─" * 66)
    if alertes:
        print(f"  ⚠ {alertes} variante(s) à recalibrer — ajuster les seuils "
              "en tête de build_radar.py")
    else:
        print("  Répartition saine : aucune variante morte ni dominante.")
    return alertes


def construire(chemin_data: Path, ecrire: bool = True) -> int:
    if not chemin_data.exists():
        print(f"✗ {chemin_data} est absent.", file=sys.stderr)
        print("  Générer villes.json depuis le dépôt radar-data :", file=sys.stderr)
        print("    python -m radar_data enrichir", file=sys.stderr)
        print("  puis copier output/villes.json vers data/villes.json", file=sys.stderr)
        return 1

    doc = json.loads(chemin_data.read_text(encoding="utf-8"))
    villes = doc["villes"]
    jour = date.today().isoformat()

    # Quintiles : les 20 % de villes aux rendements les plus hauts et les
    # 20 % les plus bas basculent sur une variante d'accroche dédiée. Le
    # découpage suit la distribution réelle du panel — il reste équilibré
    # que les rendements s'étalent de 3 à 10 % ou se resserrent sur 5 à 7 %.
    ctx = {
        "med_rendement": mediane(villes, "rendement_brut_pct"),
        "med_prix": mediane(villes, "prix_m2"),
        "med_loyer": mediane(villes, "loyer_m2"),
        "rdt_haut": quantile(villes, "rendement_brut_pct", 0.80),
        "rdt_bas": quantile(villes, "rendement_brut_pct", 0.20),
        "prix_haut": quantile(villes, "prix_m2", 0.70),
        "build_date": jour,
    }
    print(f"→ {len(villes)} villes | médiane prix {entier(ctx['med_prix'])} €/m² "
          f"| médiane rendement {decimal(ctx['med_rendement'])} %")

    env = Environment(
        loader=FileSystemLoader(DIR_TEMPLATES),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True, lstrip_blocks=True,
    )
    env.filters.update(entier=entier, decimal=decimal, signe=signe)
    env.globals.update(SITE=SITE, AVERTISSEMENT=AVERTISSEMENT, val=val)

    preparees = [preparer_ville(v, villes, ctx) for v in villes]

    slugs = [p["slug"] for p in preparees]
    if len(set(slugs)) != len(slugs):
        collisions = sorted({s for s in slugs if slugs.count(s) > 1})
        print(f"✗ slugs en collision : {collisions}", file=sys.stderr)
        return 1

    if ecrire == "stats":
        rapport_distribution(villes, ctx)
        return 0

    if not ecrire:
        rapport_distribution(villes, ctx)
        print(f"\n✓ {len(preparees)} villes vérifiées, aucune écriture (--check)")
        return 0

    DIR_SORTIE.mkdir(parents=True, exist_ok=True)

    # ── Pages villes ──────────────────────────────────────────────
    tpl_ville = env.get_template("ville.html.j2")
    for p in preparees:
        cible = DIR_SORTIE / p["slug"] / "index.html"
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(tpl_ville.render(**p, ctx=ctx, doc=doc), encoding="utf-8")
    print(f"✓ {len(preparees)} pages villes")

    # ── Hub ───────────────────────────────────────────────────────
    lignes = sorted(
        preparees,
        key=lambda p: (val(p["v"], "rendement_brut_pct") is None,
                       -(val(p["v"], "rendement_brut_pct") or 0)),
    )
    faq = [
        {"q": "Comment le rendement brut est-il calculé ?",
         "r": "Loyer mensuel au m² × 12 ÷ prix de vente au m², × 100. C'est un "
              "rendement brut : il n'intègre ni charges de copropriété, ni taxe "
              "foncière, ni fiscalité, ni vacance locative. Le rendement net "
              "d'un bien réel est toujours inférieur."},
        {"q": "D'où viennent les prix affichés ?",
         "r": "Des Demandes de Valeurs Foncières (DVF), le fichier des ventes "
              "immobilières publié par la DGFiP sous Licence Ouverte 2.0. Ce "
              "sont des prix réellement signés chez le notaire, pas des prix "
              "d'annonce."},
        {"q": "Pourquoi les prix diffèrent-ils de ceux des portails immobiliers ?",
         "r": "Deux raisons. Les portails affichent des prix d'annonce, avant "
              "négociation ; le DVF enregistre le prix signé. Et nous publions "
              "une médiane, moins sensible aux biens d'exception qu'une moyenne."},
        {"q": "Toutes les communes françaises sont-elles couvertes ?",
         "r": "Non. Ce panel V1 couvre 40 villes. L'Alsace-Moselle "
              "(Bas-Rhin, Haut-Rhin, Moselle) est structurellement absente du "
              "DVF : ces départements relèvent du Livre foncier et non du "
              "fichier immobilier, et ne transmettent donc pas leurs mutations."},
        {"q": "À quelle fréquence ces données sont-elles mises à jour ?",
         "r": "À chaque nouvelle publication des sources : le DVF paraît deux "
              "fois par an, la carte des loyers et le recensement INSEE une fois "
              "par an. La date de mise à jour figure en bas de chaque page."},
        {"q": "Ces indicateurs suffisent-ils pour décider d'un investissement ?",
         "r": "Non. Ce sont des indicateurs communaux : ils lissent les écarts "
              "entre quartiers, ignorent l'état du bien, les charges, la "
              "copropriété et votre situation fiscale. Ils servent à comparer "
              "des villes entre elles, pas à valider un bien précis."},
    ]
    faq_ld = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": f["q"],
             "acceptedAnswer": {"@type": "Answer", "text": f["r"]}}
            for f in faq
        ],
    }
    breadcrumb_hub = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "Radar immobilier",
             "item": f"{SITE}/radar-immobilier"},
        ],
    }
    titre_hub = (
        f"Radar immobilier : {len(villes)} villes comparées — prix au m² et "
        "rendement locatif"
    )
    desc_hub = (
        f"Prix au m², loyers et rendement brut dans {len(villes)} villes "
        f"françaises. Médiane du panel : {entier(ctx['med_prix'])} €/m² et "
        f"{decimal(ctx['med_rendement'])} % de rendement. Données DVF et INSEE, "
        "tableau triable."
    )
    (DIR_SORTIE / "index.html").write_text(
        env.get_template("index_radar.html.j2").render(
            villes=lignes, ctx=ctx, doc=doc, faq=faq,
            canonical=f"{SITE}/radar-immobilier",
            page_title=f"{titre_hub} | BailleurSuite",
            meta_description=desc_hub[:300],
            og_title=titre_hub, og_description=desc_hub[:300],
            jsonld=[jsonld_dump(faq_ld),
                    jsonld_dump(breadcrumb_hub)],
        ),
        encoding="utf-8",
    )
    print("✓ hub")

    # ── Méthodologie ──────────────────────────────────────────────
    breadcrumb_meth = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "Radar immobilier",
             "item": f"{SITE}/radar-immobilier"},
            {"@type": "ListItem", "position": 3, "name": "Méthodologie",
             "item": f"{SITE}/radar-immobilier/methodologie"},
        ],
    }
    titre_meth = "Méthodologie du Radar immobilier : sources, calculs et limites"
    desc_meth = (
        "Comment sont calculés les prix au m² et le rendement brut du Radar "
        "immobilier : sources DVF et INSEE, millésimes, licences, et les "
        "limites qu'il faut connaître avant d'interpréter ces chiffres."
    )
    cible = DIR_SORTIE / "methodologie" / "index.html"
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(
        env.get_template("methodologie.html.j2").render(
            doc=doc, ctx=ctx, nb_villes=len(villes),
            canonical=f"{SITE}/radar-immobilier/methodologie",
            page_title=f"{titre_meth} | BailleurSuite",
            meta_description=desc_meth[:300],
            og_title=titre_meth, og_description=desc_meth[:300],
            jsonld=[jsonld_dump(breadcrumb_meth)],
        ),
        encoding="utf-8",
    )
    print("✓ méthodologie")

    # ── Contrôle des liens ────────────────────────────────────────
    pages = sorted(DIR_SORTIE.rglob("index.html"))
    fautifs = verifier_liens(pages)
    if fautifs:
        print(f"\n✗ {len(fautifs)} lien(s) interne(s) en absolu dans le corps "
              "des pages :", file=sys.stderr)
        for f in fautifs[:20]:
            print(f"    {f}", file=sys.stderr)
        if len(fautifs) > 20:
            print(f"    … et {len(fautifs) - 20} autre(s)", file=sys.stderr)
        print("\n  Un lien absolu renvoie le visiteur sur la production, y "
              "compris depuis un build local.\n  Les liens du corps doivent "
              "être relatifs : href=\"/radar-immobilier/…\".\n  Seuls le "
              "header, le footer, le canonical et le JSON-LD portent le "
              "domaine.", file=sys.stderr)
        return 1
    print(f"✓ liens vérifiés : {len(pages)} pages, aucun absolu dans le corps")

    total = ecrire_sitemap(preparees, jour)
    print(f"✓ sitemap régénéré : {total} URL ({len(URLS_EXISTANTES)} existantes "
          f"+ {total - len(URLS_EXISTANTES)} nouvelles)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=FICHIER_DATA,
                    help=f"JSON source (défaut : {FICHIER_DATA.relative_to(RACINE)})")
    ap.add_argument("--check", action="store_true",
                    help="valider les données sans rien écrire")
    ap.add_argument("--stats", action="store_true",
                    help="répartition des variantes d'accroche, sans écriture")
    args = ap.parse_args()
    if args.stats:
        return construire(args.data, ecrire="stats")
    return construire(args.data, ecrire=not args.check)


if __name__ == "__main__":
    sys.exit(main())
