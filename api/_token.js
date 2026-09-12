import crypto from 'node:crypto';

// Le préfixe « _ » exclut ce fichier du routage Vercel : c'est un module
// partagé entre subscribe et unsubscribe, pas une route publique.

// Sans jeton, /api/unsubscribe?e=… désinscrirait n'importe qui à partir
// de la seule adresse, devinable. Le jeton lie l'adresse à un secret que
// seul le serveur détient. UNSUBSCRIBE_SECRET est préférable — une clé
// dédiée se remplace sans toucher à Brevo — mais la clé d'API fait un
// repli acceptable, sinon la désinscription cesserait de fonctionner au
// premier déploiement sans nouvelle variable.
function secret() {
  const s = process.env.UNSUBSCRIBE_SECRET || process.env.BREVO_API_KEY;
  if (!s) throw new Error('Aucun secret disponible pour signer le lien de désinscription');
  return s;
}

export function jeton(email) {
  return crypto
    .createHmac('sha256', secret())
    .update(String(email).trim().toLowerCase())
    .digest('hex')
    .slice(0, 32);
}

// Comparaison à temps constant : une comparaison naïve laisse filtrer,
// par le temps de réponse, combien de caractères de tête sont corrects.
export function jetonValide(email, fourni) {
  const attendu = jeton(email);
  const a = Buffer.from(attendu);
  const b = Buffer.from(String(fourni || ''));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

export function lienDesinscription(email) {
  const base = 'https://bailleursuite.fr/api/unsubscribe';
  return `${base}?e=${encodeURIComponent(email)}&t=${jeton(email)}`;
}
