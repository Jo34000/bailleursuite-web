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

L'accroche du hero est elle aussi construite depuis les données : cinq
formulations déclenchées par seuils (rendement haut, marché cher, forte
appréciation, démographie porteuse, vacance élevée) plus un cas médian et deux
replis pour les communes sans prix ou sans loyer. Aucune page ne partage sa
phrase avec une autre.

### Calibrage des variantes

```bash
python3 tools/build_radar.py --stats     # répartition, sans rien écrire
```

Les deux variantes de rendement se déclenchent sur les **quintiles du panel**,
pas sur un écart en pourcentage figé. Un seuil du type « ±15 % autour de la
médiane » dépend entièrement de l'étalement de la distribution : mesuré sur
trois formes possibles d'un même panel (min 3,68 · médiane 6,06 · max 9,82),
il donnait 15/13/12 sur une distribution étalée mais **3/6/31** sur une
distribution resserrée — une variante avalant les trois quarts du panel. Les
quintiles donnent 9/9/22 dans les trois cas.

**Chaque seuil se calcule sur la population qui peut réellement l'atteindre**,
jamais sur le panel entier. Deux variantes s'étaient éteintes faute de ce
principe :

- `rendement_bas` était départagée de `marche_cher` par un seuil de prix du
  panel entier. Or rendement bas et prix élevé sont **mécaniquement corrélés**
  — le rendement est `loyer × 12 / prix`, et les loyers varient bien moins que
  les prix d'une ville à l'autre. Les neuf villes du quintile bas passaient
  toutes le seuil de prix, rendant la seconde variante inatteignable. Le
  partage se fait désormais sur la médiane des prix **à l'intérieur du
  quintile bas** : les deux variantes se déclenchent sur n'importe quel jeu de
  données.
- `repli` ne peut viser que les villes qui traversent les variantes de
  rendement sans être captées. Son seuil est le quantile de l'évolution
  calculé sur ce sous-groupe.

Enfin, **un seuil relatif ne décide jamais du sens d'une phrase.** Le seuil de
mouvement des prix suit les quantiles, mais la formulation suit le signe réel :
médiane des évolutions négative → on parle de repli et l'on retient la queue
basse ; positive → on parle d'appréciation et l'on retient la queue haute.
Sans cette règle, un panel entièrement en hausse déclenchait quand même le
quantile bas et annonçait « les prix ont reculé de 11 % » là où ils montaient.
`repli` et `appreciation` s'excluent donc par cycle — `--stats` les traite en
paire et alerte si aucune des deux ne vit, ou si les deux cohabitent.

Les variantes démographie et vacance restent sur des seuils absolus : 0,7 %
de croissance annuelle ou 10 % de vacance sont notables en soi. Le rapport
signale toute variante jamais déclenchée ou couvrant plus de 40 % du panel.

### Graphe d'entités JSON-LD

Les entités durables portent un `@id` stable et sont déclarées **une seule
fois**, sur la home :

| `@id` | Entité | Déclarée sur |
|---|---|---|
| `…/#organization` | `Organization` | `index.html` |
| `…/#software` | `SoftwareApplication` | `index.html` |
| `…/#website` | `WebSite` | `index.html` |
| `…/radar-immobilier#dataset` | `Dataset` | hub + méthodologie |

Partout ailleurs — `author`, `publisher`, `creator` — on **référence** par
`@id` au lieu de recopier un nœud anonyme. Avant, dix nœuds `Organization`
indistincts coexistaient sous trois formes d'URL différentes (avec et sans
slash final, un sans `url` du tout) : rien ne permettait à un moteur de
comprendre qu'il s'agissait de la même entité.

Le `SoftwareApplication` n'est **jamais dupliqué** : le hub Radar le
mentionne par `@id` depuis son nœud `WebPage`.

### Dataset

Construit par `construire_dataset()` **entièrement depuis `villes.json`** :
libellés, millésimes, licences et pages viennent du bloc `sources`, les
`variableMeasured` sont relevées sur les villes avec leurs unités. Un
changement de millésime côté `radar-data` se propage sans toucher au
générateur.

La licence vient du champ `licence_url` des sources — elle est une propriété
de la source, déclarée dans `radar_data/sources.py`, jamais réécrite ici. Si
les sources n'en portent pas (JSON antérieur au champ), le `Dataset` est
publié **sans** `license` et le build avertit : on ne devine pas une licence.

### Validation

Deux contrôles bloquants, sortie en code 1 :

| Contrôle | Périmètre |
|---|---|
| Liens internes absolus dans le corps | 42 pages Radar |
| JSON-LD parse, `@context` et `@type` présents | **51 pages** — 42 Radar + 9 historiques |

Le contrôle JSON-LD détecte spécifiquement les guillemets échappés en
`&#34;`, symptôme de l'autoescape Jinja non désactivé — le bug qui avait
rendu les 83 blocs du Radar illisibles sans que rien ne le signale. Vérifié
en le réintroduisant : 115 erreurs, code 1.

Il couvre les 9 pages historiques, qui ne passent par aucun outil et dont le
balisage n'était jusqu'ici relu par personne.

### Liens internes

Le corps des pages générées n'utilise **que des liens relatifs**
(`/radar-immobilier/{slug}`). Le domaine absolu est réservé au header, au
footer, au canonical, à `og:url` et au JSON-LD.

Le build échoue — code de sortie 1 — si un lien absolu apparaît dans le corps
d'une page. Sans ce garde-fou, un build servi en local renvoie le visiteur sur
la production, qui répond 404 tant que les pages ne sont pas déployées.

### Fixture de développement

`tools/fixtures/villes.example.json` reproduit le schéma réel avec des valeurs
**synthétiques**. Elle sert à valider le rendu sans le vrai jeu de données ;
elle n'a aucune valeur documentaire et ne doit jamais être publiée.

Ses rendements ET ses évolutions de prix sont calés sur le run réel — 3,68 % à
9,82 % de rendement, médiane ~6,1 % ; évolutions 3 ans de −12,5 % à +8 %, 37
villes sur 40 en baisse — afin que le calibrage mesuré en développement
corresponde à celui de la production. Sans cet alignement, un seuil réglé sur
une fixture optimiste passe pour sain et meurt en production.

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
