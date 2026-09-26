import { ctValide } from './_ct.js';
import { pipeline, jour, identifiants } from './_redis.js';

/* Compteur d'usage de première partie.
 *
 * Les événements personnalisés de Vercel Analytics sont réservés à
 * l'offre Pro : tous les window.va('event', …) du site étaient émis dans
 * le vide. Ce point de collecte les remplace.
 *
 * Il ne stocke que des compteurs. Pas d'adresse IP, pas d'agent
 * utilisateur, pas d'identifiant de session, pas de cookie : rien qui
 * permette de reconstituer un parcours individuel. C'est ce qui le
 * dispense de consentement, au même titre que la mesure d'audience
 * exemptée, et ce qui le distingue de la balise Google Ads.
 */

// Liste blanche stricte. Un événement inconnu est refusé plutôt
// qu'enregistré : sans cela, n'importe qui pourrait faire grossir la
// base avec des clés arbitraires.
const EVENEMENTS = new Set([
  'Calculatrice_Resultat',
  'Quittance_CTA_Hero',
  'Quittance_Generee',
  'AppStore_Click',
  'Email_Capture',
  'Home_MiniCalc',
]);

// Un corps légitime fait moins de cent octets. Au-delà, ce n'est pas
// notre client.
const TAILLE_MAX = 200;

// Les compteurs journaliers n'ont pas vocation à vivre éternellement :
// 400 jours couvrent une comparaison d'une année sur l'autre et bornent
// la base, qui tient dans l'offre gratuite.
const RETENTION_S = 400 * 24 * 3600;

function trop_gros(req) {
  const annonce = parseInt(req.headers['content-length'] || '0', 10);
  return Number.isFinite(annonce) && annonce > TAILLE_MAX;
}

/* sendBeacon envoie soit un Blob typé application/json, soit une chaîne
 * en text/plain — auquel cas Vercel ne la désérialise pas. Les deux
 * formes doivent être acceptées. */
function corps(req) {
  if (typeof req.body === 'string') {
    if (req.body.length > TAILLE_MAX) return null;
    try { return JSON.parse(req.body); } catch (e) { return null; }
  }
  if (req.body && typeof req.body === 'object') return req.body;
  return null;
}

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  if (trop_gros(req)) return res.status(413).end();

  const donnees = corps(req);
  if (!donnees) return res.status(400).json({ error: 'Corps illisible' });

  const evenement = donnees.event;
  if (typeof evenement !== 'string' || !EVENEMENTS.has(evenement)) {
    return res.status(400).json({ error: 'Événement inconnu' });
  }

  const ct = donnees.ct;
  if (ct !== undefined && !ctValide(ct)) {
    return res.status(400).json({ error: 'ct inconnu' });
  }

  if (!identifiants()) {
    console.error('Aucun identifiant Redis — comptage impossible');
    // 204 quand même : un compteur indisponible ne doit pas faire
    // remonter d'erreur dans le navigateur d'un visiteur, qui n'y peut
    // rien et à qui cela ne sert à rien.
    return res.status(204).end();
  }

  const j = jour();
  const cles = [`stats:${evenement}:${j}`];
  if (ct) cles.push(`stats:${evenement}:${ct}:${j}`);

  const commandes = [];
  for (const cle of cles) {
    commandes.push(['INCR', cle]);
    commandes.push(['EXPIRE', cle, String(RETENTION_S)]);
  }

  try {
    await pipeline(commandes);
  } catch (err) {
    console.error('Échec du comptage :', err.message);
  }

  return res.status(204).end();
}
