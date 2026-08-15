# Outils de génération — Radar Immobilier

Deux scripts Python, exécutés à la main. Rien n'est déclenché au déploiement :
Vercel sert les fichiers du dépôt tels quels.

## Prérequis

```bash
pip install jinja2
```

Et le jeu de données, **absent du dépôt** :

```bash
# depuis le dépôt radar-data
python -m radar_data enrichir
cp output/villes.json ../bailleursuite-web/data/villes.json
```

`data/` et `tools/` sont exclus du déploiement par `.vercelignore` : le dépôt
est public et Vercel sert les fichiers tels quels, `villes.json` ne doit pas
être téléchargeable sur `bailleursuite.fr/data/villes.json`.

## 1. `build_radar.py` — génération des pages

```bash
python3 tools/build_radar.py            # build complet
python3 tools/build_radar.py --check    # valider sans écrire
python3 tools/build_radar.py --data tools/fixtures/villes.example.json
```

Produit :

| Sortie | Contenu |
|---|---|
| `radar-immobilier/index.html` | hub, tableau triable, FAQ |
| `radar-immobilier/{slug}/index.html` | une page par ville |
| `radar-immobilier/methodologie/index.html` | sources, licences, formule, limites |
| `sitemap.xml` | régénéré intégralement (7 URL existantes + 42 nouvelles) |

**Rien n'est imputé.** Une donnée absente du JSON s'affiche « non disponible »
et l'indicateur qui en dépend n'est pas calculé — jamais de valeur de repli,
jamais de report d'une commune voisine.

### Contenu unique par ville

Six blocs éditoriaux, déclenchés par les données : rendement face à la médiane
du panel, niveau de prix, dynamique démographique (trois paliers), vacance,
évolution sur trois ans, structure des ménages. Un bloc dont la donnée manque
ne sort pas. Les 3 à 5 « points favorables » et 2 à 4 « points de vigilance »
dérivent des mêmes seuils, groupés en tête de fichier — aucun texte fixe.

Un même fait n'apparaît jamais des deux côtés du bilan : une hausse de prix
forte dégrade le point d'entrée, elle est donc en vigilance, jamais en
favorable.

### Fixture de développement

`tools/fixtures/villes.example.json` reproduit le schéma réel avec des valeurs
**synthétiques**. Elle sert à valider le rendu sans le vrai jeu de données ;
elle n'a aucune valeur documentaire et ne doit jamais être publiée.

## 2. `add_nav_link.py` — lien entrant vers le Radar

```bash
python3 tools/add_nav_link.py           # simulation (défaut)
python3 tools/add_nav_link.py --apply   # écrit
python3 tools/add_nav_link.py --revert --apply   # retire
```

Insère « Radar » dans `.nav-links`, `.nav-mobile-menu` et le pied de page des
9 pages existantes. Sans ce lien, un sitemap ne suffit pas : Google
n'indexerait pas 42 URL orphelines.

**Idempotent** — un second passage ne fait rien. Le script repère un lien
voisin connu (`/quittance-loyer-pdf-gratuit`) et insère le sien juste après, en
recopiant son indentation, sa classe et sa **forme d'URL** : `index.html`
référence ses pages en relatif, les guides en absolu.

La page `comparatif-logiciel-gestion-locative` ne charge pas le design system
et n'a pas de `.site-footer-nav` ; une zone de repli traite son `<footer>` nu.

## Ordre d'exécution

```bash
python3 tools/build_radar.py
python3 tools/add_nav_link.py --apply
```

Le premier ne touche jamais aux pages existantes, le second ne touche jamais
aux pages générées.
