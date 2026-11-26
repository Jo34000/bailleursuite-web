# Règles de travail — bailleursuite.fr

## Git
- Avant chaque push : `git show --stat HEAD` et vérifier que la liste
  des fichiers correspond aux modifications. Si un fichier manque,
  corriger le commit AVANT de pousser, jamais de commit de rattrapage.
- Respecter la consigne de merge donnée dans chaque demande (« merge si
  tout est vert » ou « ne merge pas avant validation »).

## Ce que je fais moi-même (ne pas le faire à ma place)
- Le rebuild du Radar : `data/villes.json` est privé et absent de ton
  environnement. Tu modifies gabarits et `build_radar.py`, tu vérifies
  sur la fixture, tu restaures les pages publiées, puis tu me rappelles
  le rebuild.
- Les envois IndexNow (bloqués dans ton environnement) : donne-moi la
  commande, limitée aux pages dont le CONTENU a changé.

## Contrôles
- Pas de captures d'écran ni de simulateur sauf demande explicite :
  contrôles par mesures (DOM, réseau, CLS, scrollWidth).
- Toujours : les 6 contrôles bloquants de tools/, JSON-LD valides,
  parité FAQ visible / FAQPage mot pour mot, aucun débordement à 360,
  390 et 1440 px, CLS < 0,1.
- Le mobile ne change pas quand une demande porte sur le desktop, et
  inversement.

## Contenu et formulation
- Registre informatif : l'app prépare et calcule, l'utilisateur décide.
  Interdits : conseil, « optimiser », « optimal », « recommandé »
  appliqué à un régime, « gain fiscal », « pilotage », « piloter »,
  « copilote », prédictions, exclusivité (« seul », « unique »,
  « premier »).
- Pass Fiscal : « valable 6 mois ». Dossier IA : « données
  personnelles masquées par défaut », jamais « anonymiser », jamais
  « BailleurSuite analyse votre patrimoine ». IRL : montant présenté
  comme un plafond. Quittances : l'app les PRÉPARE chaque mois,
  l'utilisateur les envoie (aucun envoi automatique). Prêt : « capital
  restant dû calculé depuis le prêt saisi », jamais « synchronisé ».
- Plateformes : iPhone, iPad et Mac (puce Apple). Données sur les
  appareils de l'utilisateur et son iCloud, aucun serveur BailleurSuite.
- Chiffres fiscaux et cellules concurrentes : uniquement depuis une
  source officielle, avec l'URL et la date. Si une source est
  inaccessible, lister les valeurs à me faire vérifier ; ne jamais
  inventer ni compléter de mémoire.
- Toute page modifiée : dateModified à jour + mention visible de mise
  à jour quand la page en a une.

## Liens App Store
- Format : `https://apps.apple.com/app/apple-store/id6772793420?pt=128946892&ct=<ct>&mt=8`,
  target="_blank", rel="noopener", `track('AppStore_Click',{ct:'<ct>'})`.
- Tout nouveau ct s'ajoute dans tools/appstore.py ET api/_ct.js.
- Tout nouvel événement de suivi s'ajoute à la liste blanche de
  api/track.js.

## Navigation
- Source unique : tools/nav.py (`--appliquer` pour réécrire).
