import crypto from 'node:crypto';
import { CT_CONNUS, PREFIXE_ADS } from './_ct.js';
import { pipeline, jour, identifiants } from './_redis.js';

/* Lecture des compteurs d'usage.
 *
 * Protégé par STATS_TOKEN, une variable d'environnement. Ce n'est pas
 * une authentification — c'est un jeton porteur, qui transite dans
 * l'URL et peut se retrouver dans un historique de navigateur. Il
 * protège des chiffres d'usage agrégés, pas des données personnelles :
 * il n'y en a aucune derrière ce point de collecte.
 */

const EVENEMENTS = [
  'AppStore_Click',
  'Quittance_CTA_Hero',
  'Calculatrice_Resultat',
  'Quittance_Generee',
  'Email_Capture',
];

const JOURS_MAX = 365;
const JOURS_DEFAUT = 30;

// Upstash accepte de longs pipelines, mais une requête démesurée est
// plus lente à échouer qu'à réussir. On découpe.
const LOT = 200;

function jetonValide(fourni) {
  const attendu = process.env.STATS_TOKEN;
  if (!attendu) return false;
  const a = Buffer.from(String(attendu));
  const b = Buffer.from(String(fourni || ''));
  // timingSafeEqual exige des longueurs égales ; la comparaison de
  // longueur en amont fuit la taille du jeton, pas son contenu.
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function joursRecents(n) {
  const out = [];
  const maintenant = Date.now();
  for (let i = n - 1; i >= 0; i--) {
    out.push(jour(new Date(maintenant - i * 86400000)));
  }
  return out;
}

async function lire(cles) {
  const valeurs = [];
  for (let i = 0; i < cles.length; i += LOT) {
    const lot = cles.slice(i, i + LOT);
    const res = await pipeline(lot.map((c) => ['GET', c]));
    valeurs.push(...res.map((v) => (v === null ? 0 : parseInt(v, 10) || 0)));
  }
  return valeurs;
}

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

  // Ni cache navigateur ni cache CDN : ces chiffres bougent, et l'URL
  // porte un jeton qu'on ne veut pas voir mis en cache partagé.
  res.setHeader('Cache-Control', 'no-store');

  if (!jetonValide(req.query.token)) {
    return res.status(401).json({ error: 'Jeton absent ou invalide' });
  }

  if (!identifiants()) {
    return res.status(503).json({ error: 'Base de compteurs indisponible' });
  }

  let jours = parseInt(req.query.days, 10);
  if (!Number.isFinite(jours) || jours < 1) jours = JOURS_DEFAUT;
  jours = Math.min(jours, JOURS_MAX);

  const dates = joursRecents(jours);

  try {
    // 1. Totaux et détail journalier, par événement.
    const clesJour = [];
    for (const e of EVENEMENTS) for (const d of dates) clesJour.push(`stats:${e}:${d}`);
    const valeursJour = await lire(clesJour);

    const evenements = {};
    let i = 0;
    for (const e of EVENEMENTS) {
      const parJour = {};
      let total = 0;
      for (const d of dates) {
        const v = valeursJour[i++];
        parJour[d] = v;
        total += v;
      }
      evenements[e] = { total, par_jour: parJour };
    }

    // 2. Détail par ct pour AppStore_Click, variantes publicitaires
    //    comprises. Sommé sur la période : le croisement ct × jour
    //    donnerait des centaines de lignes pour peu d'usage.
    const tousCt = [...CT_CONNUS, ...CT_CONNUS.map((c) => PREFIXE_ADS + c)];
    const clesCt = [];
    for (const c of tousCt) for (const d of dates) clesCt.push(`stats:AppStore_Click:${c}:${d}`);
    const valeursCt = await lire(clesCt);

    const parCt = {};
    let k = 0;
    for (const c of tousCt) {
      let somme = 0;
      for (let d = 0; d < dates.length; d++) somme += valeursCt[k++];
      if (somme > 0) parCt[c] = somme;
    }

    return res.status(200).json({
      periode: { debut: dates[0], fin: dates[dates.length - 1], jours },
      evenements,
      appstore_par_ct: parCt,
    });
  } catch (err) {
    console.error('Lecture des compteurs :', err.message);
    return res.status(500).json({ error: 'Lecture impossible' });
  }
}
