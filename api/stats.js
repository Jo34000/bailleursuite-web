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
  'Quittance_Modal_Vue',
  'Email_Capture',
  'Home_MiniCalc',
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

/* Totaux et détail journalier par événement, et clics App Store par ct
 * (variantes publicitaires comprises), sommés sur les jours donnés. */
async function lirePeriode(dates) {
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

  // Le croisement ct × jour donnerait des centaines de lignes pour peu
  // d'usage : les clics par ct sont sommés sur la période.
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
  return { evenements, parCt };
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

  // Période demandée, puis la période de même durée qui la précède :
  // c'est elle qui donne le sens d'une évolution (« +40 % » n'a de
  // valeur qu'à durée égale). Bornée à 90 jours pour garder la lecture
  // rapide : au-delà, le nombre de clés à lire double sans grand profit.
  const toutes = joursRecents(jours <= 90 ? jours * 2 : jours);
  const dates = toutes.slice(-jours);
  const avant = jours <= 90 ? toutes.slice(0, jours) : [];

  try {
    const periode = await lirePeriode(dates);
    const corps = {
      periode: { debut: dates[0], fin: dates[dates.length - 1], jours },
      evenements: periode.evenements,
      appstore_par_ct: periode.parCt,
      ct_connus: CT_CONNUS,
    };
    if (avant.length) {
      const p = await lirePeriode(avant);
      corps.precedent = {
        periode: { debut: avant[0], fin: avant[avant.length - 1], jours },
        evenements: Object.fromEntries(Object.entries(p.evenements).map(([e, v]) => [e, v.total])),
        appstore_par_ct: p.parCt,
      };
    }
    return res.status(200).json(corps);
  } catch (err) {
    console.error('Lecture des compteurs :', err.message);
    return res.status(500).json({ error: 'Lecture impossible' });
  }
}
