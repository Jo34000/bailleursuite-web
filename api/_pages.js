// Pages suivies par le compteur de visites (événement Page_Vue).
//
// Le navigateur envoie un jeton de page court, pas une URL : la liste
// est fermée, la base ne peut pas grossir de clés arbitraires, et
// aucune adresse saisie (paramètres, ancres) n'est jamais enregistrée.
// Le correspondant chemin → jeton vit dans scripts/track.js ; les deux
// listes sont comparées par tools/appstore.py.
//
// Les visites arrivées d'une campagne Google portent le préfixe ads_,
// comme les jetons ct des liens App Store.

import { PREFIXE_ADS } from './_ct.js';

export const PAGES_CONNUES = [
  'accueil', 'quittance', 'calculatrice', 'guide2044', 'guidelmnp',
  'loi_finances', 'comparatif', 'app', 'aide',
  'radar', 'radar_ville', 'radar_methodo', 'cgu', 'confidentialite',
];

export function pageValide(page) {
  if (typeof page !== 'string' || !page) return false;
  const base = page.startsWith(PREFIXE_ADS) ? page.slice(PREFIXE_ADS.length) : page;
  return PAGES_CONNUES.includes(base);
}
