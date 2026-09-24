// Jetons de campagne acceptés par /api/track.
//
// Le préfixe « _ » exclut ce fichier du routage Vercel : c'est un module
// partagé, pas une route.
//
// Cette liste double celle de tools/appstore.py, et n'avait pas le choix :
// tools/ est exclu du déploiement par .vercelignore, une fonction
// serverless ne peut donc pas la lire. La divergence est rattrapée par un
// contrôle bloquant — appstore.py compare les deux listes et refuse le
// build si elles s'écartent.

export const CT_CONNUS = [
  'nav', 'footer', 'hero', 'cta_final', 'tarifs', 'sticky',
  'calculatrice', 'quittance', 'guide2044', 'guidelmnp',
  'comparatif', 'compariphone', 'radar', 'aide',
  'quittance_qr', 'calculatrice_qr',
];

// Posé au chargement par scripts/source-tracking.js quand la visite
// vient d'une campagne Google : ct=hero devient ct=ads_hero.
export const PREFIXE_ADS = 'ads_';

export function ctValide(ct) {
  if (typeof ct !== 'string' || !ct) return false;
  const base = ct.startsWith(PREFIXE_ADS) ? ct.slice(PREFIXE_ADS.length) : ct;
  return CT_CONNUS.includes(base);
}
