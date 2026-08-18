#!/usr/bin/env python3
"""Ancres des articles du centre d'aide — mapping figé.

`aide/index.html` est écrit à la main : rien ne recalcule ses `id` à
chaque build, et c'est délibéré. Une ancre est une URL publique. Dès
qu'un lien `/aide#modifier-supprimer-charge` est parti dans un mail de
support, dans une réponse App Store ou dans un signet, il doit
continuer de fonctionner — y compris si le titre de l'article est
reformulé un an plus tard.

D'où la règle : ANCRES fait foi, pas le titre.

Les slugs ont été dérivés une fois des titres (minuscules, sans
accent, tirets, mots vides retirés, six mots au plus), puis figés
ici. Six ont été repris à la main, la dérivation mécanique produisant
un libellé trompeur ou bancal.

Reformuler un titre déjà en ligne : changer la CLÉ, garder la VALEUR.
Le contrôle de build échoue tant que ce n'est pas fait, ce qui est
exactement le but — il force une décision explicite plutôt que de
casser des liens en silence.

Ajouter un article : ajouter son entrée ici. Le contrôle refuse un
article sans ancre.

    python3 tools/aide_ancres.py            # contrôle
    python3 tools/aide_ancres.py --appliquer # pose les id manquants
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PAGE = RACINE / "aide" / "index.html"

# `id` déjà pris ailleurs dans la page : une ancre d'article ne peut
# pas les réutiliser sans casser le JS ou la navigation.
ID_RESERVES = {
    "aide-main", "aide-no-results", "aide-search", "aide-toast", "eg",
    "nav-burger", "nav-mobile-menu",
}

# titre de l'article, tel qu'il figure dans le HTML  ->  ancre
ANCRES: dict[str, str] = {
    # ── premiers-pas ──
    'Ajouter mon premier bien':
        'ajouter-premier-bien',
    'Comprendre les plans (Gratuit / Gestion Zen / Pass Fiscal)':
        'comprendre-plans-gratuit-gestion-zen-pass',
    'Configurer mon profil':
        'configurer-profil',
    'Comment modifier mes informations de profil&nbsp;?':
        'modifier-informations-profil',

    # ── biens ──
    'Comment modifier un bien déjà enregistré (type de location, prix, valeur estimée)&nbsp;?':
        'modifier-bien-deja-enregistre-type-location',
    "Comment modifier les informations de crédit d'un bien&nbsp;?":
        'modifier-informations-credit-bien',
    'Comment modifier un loyer déjà saisi (montant, statut, date)&nbsp;?':
        'modifier-loyer-deja-saisi-montant-statut',
    'Comment modifier ou supprimer une charge&nbsp;?':
        'modifier-supprimer-charge',
    'Comment ajouter ou modifier un projet dans Projets &amp; Simulations&nbsp;?':
        'ajouter-modifier-projet-projets-simulations',

    # ── gestion ──
    'Encaisser un loyer':
        'encaisser-loyer',
    'Ajouter une charge':
        'ajouter-charge',
    'Générer une quittance':
        'generer-quittance',
    'Combien de quittances puis-je générer en plan gratuit&nbsp;?':
        'combien-quittances-generer-plan-gratuit',
    'Obtenir la checklist du bailleur':
        'obtenir-checklist-bailleur',
    'Relancer un locataire':
        'relancer-locataire',

    # ── locataire ──
    "Comment modifier les informations d'un locataire&nbsp;?":
        'modifier-informations-locataire',
    'Je génère une quittance pour un ancien locataire, comment faire&nbsp;?':
        'genere-quittance-ancien-locataire',
    'Comment ajouter un second locataire (bail joint, colocation, couple)&nbsp;?':
        'ajouter-second-locataire-bail-joint-colocation',
    'Un locataire perçoit une aide au logement (CAF, MSA) versée directement à moi (tiers-payant), comment le renseigner&nbsp;?':
        'locataire-percoit-aide-logement-caf-msa',
    'Comment gérer un loyer partiel ou un changement de locataire en cours de mois&nbsp;?':
        'gerer-loyer-partiel-changement-locataire-cours',

    # ── fiscalite ──
    "Comment fonctionne l'analyse fiscale&nbsp;?":
        'fonctionne-analyse-fiscale',
    'Comprendre la recommandation de régime':
        'comprendre-recommandation-regime',
    'Location nue : la déclaration 2044':
        'location-nue-declaration-2044',
    'LMNP : le régime réel BIC':
        'lmnp-regime-reel-bic',
    'Comment configurer mes amortissements (LMNP)&nbsp;?':
        'configurer-amortissements-lmnp',
    "Qu'est-ce que le seuil LMP (23&nbsp;000&nbsp;€)&nbsp;?":
        'seuil-lmp-23-000',
    "Qu'est-ce que le Pass Fiscal&nbsp;?":
        'pass-fiscal',
    'Comment obtenir ma synthèse fiscale en PDF&nbsp;?':
        'obtenir-synthese-fiscale-pdf',
    'Les calculs sont-ils officiels&nbsp;?':
        'calculs-officiels',
    "Ai-je besoin d'un SIRET pour louer en meublé&nbsp;?":
        'besoin-siret-louer-meuble',
    'Où déclarer mes revenus LMNP&nbsp;?':
        'declarer-revenus-lmnp',
    'Pourquoi dois-je payer un autre service pour ma déclaration LMNP au réel&nbsp;?':
        'payer-autre-service-declaration-lmnp-reel',
    "Comment fonctionne la préparation de ma déclaration fiscale dans l'app&nbsp;?":
        'fonctionne-preparation-declaration-fiscale-app',

    # ── patrimoine ──
    'Comment est calculée la projection&nbsp;?':
        'calcul-projection',
    'Pourquoi la valeur du bien est-elle constante&nbsp;?':
        'valeur-bien-constante',
    'Patrimoine net vs valeur brute':
        'patrimoine-net-vs-valeur-brute',
    'Comment est calculé le patrimoine net&nbsp;?':
        'calcul-patrimoine-net',
    'Comment est calculé le capital restant dû&nbsp;?':
        'calcul-capital-restant-du',
    "Mon crédit comporte un différé ou j'ai fait une pause de prêt. Le capital restant dû est-il exact&nbsp;?":
        'credit-comporte-differe-pause-pret-capital',
    "Les mensualités affichées incluent-elles l'assurance emprunteur&nbsp;?":
        'mensualites-affichees-incluent-assurance-emprunteur',
    'Les valeurs de mes biens sont-elles vérifiées&nbsp;?':
        'valeurs-biens-verifiees',
    'Générer le rapport patrimonial':
        'generer-rapport-patrimonial',

    # ── simulation-vente ──
    'Comment fonctionne la simulation de vente&nbsp;?':
        'fonctionne-simulation-vente',
    "Pourquoi l'app indique une «&nbsp;moins-value fiscale&nbsp;» alors que je vends plus cher que mon prix d'achat&nbsp;?":
        'app-indique-moins-value-fiscale-vends',
    'Quels sont les frais pris en compte dans le calcul&nbsp;?':
        'frais-pris-compte-calcul',
    "Qu'est-ce que l'abattement pour durée de détention&nbsp;?":
        'abattement-duree-detention',
    'La simulation est-elle un calcul définitif&nbsp;?':
        'simulation-calcul-definitif',
    'Et pour les biens en LMNP&nbsp;?':
        'plus-value-lmnp',
    'Cette fonctionnalité est-elle incluse dans le plan gratuit&nbsp;?':
        'simulation-vente-plan-gratuit',

    # ── abonnement ──
    "Comment s'abonner à Gestion Zen&nbsp;?":
        'abonner-gestion-zen',
    'Comment acheter le Pass Fiscal&nbsp;?':
        'acheter-pass-fiscal',
    'Restaurer mes achats':
        'restaurer-achats',
    'Résilier mon abonnement':
        'resilier-abonnement',

    # ── documents ──
    "Comment sauvegarder les documents PDF générés par l'app (quittances, rapports, synthèses fiscales)&nbsp;?":
        'sauvegarder-documents-pdf-generes-app-quittances',
    'Mes données (biens, loyers, charges) sont-elles sauvegardées et synchronisées entre mes appareils&nbsp;?':
        'donnees-biens-loyers-charges-sauvegardees-synchronisees',
    'Mon iCloud est plein, que faire&nbsp;?':
        'icloud-plein',

    # ── donnees ──
    'Où sont stockées mes données&nbsp;?':
        'stockage-donnees',
    'Synchronisation iCloud':
        'synchronisation-icloud',
    'Supprimer mes données':
        'supprimer-donnees',

    # ── faq ──
    "L'app fonctionne-t-elle sans connexion internet&nbsp;?":
        'app-fonctionne-sans-connexion-internet',
    'Puis-je gérer plusieurs biens&nbsp;?':
        'gerer-plusieurs-biens',
    "L'app gère-t-elle la location meublée (LMNP)&nbsp;?":
        'app-gere-location-meublee-lmnp',
    'Comment contacter le support&nbsp;?':
        'contacter-support',
}


_ARTICLE = re.compile(
    r'<div class="aide-item"(?P<attrs>[^>]*)>\s*'
    r'(?:<a class="aide-ancre"[^>]*>.*?</a>\s*)?'
    r'<button class="aide-item-trigger"[^>]*>\s*'
    r'(?P<titre>.*?)\s*<span class="aide-chevron"', re.S)


def articles(texte: str) -> list[tuple[str, str | None]]:
    """(titre, id posé) pour chaque article, dans l'ordre de la page."""
    trouves = []
    for m in _ARTICLE.finditer(texte):
        pose = re.search(r'\bid="([^"]*)"', m.group("attrs"))
        trouves.append((m.group("titre"), pose.group(1) if pose else None))
    return trouves


def verifier(texte: str | None = None) -> list[str]:
    """Contrôle bloquant. Retourne la liste des anomalies."""
    texte = PAGE.read_text(encoding="utf-8") if texte is None else texte
    erreurs: list[str] = []
    trouves = articles(texte)

    # 1. Unicité des ancres du mapping — une collision enverrait deux
    #    liens différents sur le même article, en silence.
    vus: dict[str, str] = {}
    for titre, ancre in ANCRES.items():
        if ancre in vus:
            erreurs.append(
                f"ancre en double : {ancre!r} sert à la fois pour "
                f"{vus[ancre]!r} et {titre!r}")
        vus[ancre] = titre
        if ancre in ID_RESERVES:
            erreurs.append(f"ancre {ancre!r} ({titre}) : id déjà pris par la page")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", ancre):
            erreurs.append(f"ancre {ancre!r} ({titre}) : forme invalide")

    # 2. Chaque article de la page a une ancre, et c'est la bonne.
    for titre, pose in trouves:
        attendue = ANCRES.get(titre)
        if attendue is None:
            erreurs.append(
                f"article sans ancre : {titre!r}. Si c'est un nouvel "
                f"article, ajouter son entrée dans ANCRES. Si c'est un "
                f"titre reformulé, changer la CLÉ de l'entrée existante "
                f"en gardant sa VALEUR, pour ne pas casser les liens.")
        elif pose is None:
            erreurs.append(f"id absent du HTML pour {titre!r} "
                           f"(attendu {attendue!r}) — lancer --appliquer")
        elif pose != attendue:
            erreurs.append(f"id {pose!r} ≠ ancre {attendue!r} pour {titre!r}")

    # 3. Pas d'entrée orpheline : un titre du mapping qui n'existe plus
    #    sur la page signale une reformulation non répercutée.
    presents = {t for t, _ in trouves}
    for titre in ANCRES:
        if titre not in presents:
            erreurs.append(f"entrée orpheline dans ANCRES : {titre!r} "
                           f"ne correspond à aucun article de la page")

    if len(trouves) != len(ANCRES):
        erreurs.append(f"{len(trouves)} articles pour {len(ANCRES)} ancres")
    return erreurs


def appliquer() -> int:
    """Pose les `id` manquants. Idempotent."""
    texte = PAGE.read_text(encoding="utf-8")
    poses = 0

    def remplacer(m: re.Match) -> str:
        nonlocal poses
        titre = m.group("titre")
        ancre = ANCRES.get(titre)
        if ancre is None or 'id="' in m.group("attrs"):
            return m.group(0)
        poses += 1
        return m.group(0).replace('<div class="aide-item"',
                                  f'<div class="aide-item" id="{ancre}"', 1)

    texte = _ARTICLE.sub(remplacer, texte)
    if poses:
        PAGE.write_text(texte, encoding="utf-8")
    return poses


def main() -> int:
    if "--appliquer" in sys.argv:
        print(f"{appliquer()} id posé(s)")
    erreurs = verifier()
    for e in erreurs:
        print("✗", e, file=sys.stderr)
    print(f"{len(ANCRES)} ancres · {len(erreurs)} anomalie(s)")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
