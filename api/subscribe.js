import { lienDesinscription } from './_token.js';

// Sources acceptées, en correspondance avec l'attribut data-source des
// formulaires. La liste est fermée : une valeur libre finirait par
// polluer la segmentation Brevo de variantes non rapprochables.
const SOURCES = new Set([
  'guide2044', 'guidelmnp', 'calculatrice', 'radar', 'guide-2044-pdf',
]);

// Sources qui déclenchent l'envoi immédiat du guide PDF. Les autres
// formulaires ne promettent qu'un rappel avant la déclaration : leur
// envoyer un guide qu'ils n'ont pas demandé serait un email non sollicité.
const SOURCES_GUIDE = new Set(['guide-2044-pdf']);

const PIED = (email) => `
  <div style="background: #1C1C1E; padding: 20px 36px; text-align: center;">
    <p style="color: rgba(255,255,255,0.4); font-size: 0.72rem; margin: 0; line-height: 1.6;">
      BailleurSuite · Application iOS pour bailleurs particuliers français<br>
      <a href="https://bailleursuite.fr/politique-confidentialite.html" style="color: rgba(255,255,255,0.4);">Politique de confidentialité</a>
      · <a href="${lienDesinscription(email)}" style="color: rgba(255,255,255,0.4);">Se désabonner</a>
    </p>
  </div>`;

const ENVELOPPE = (corps, email) => `
  <div style="font-family: 'DM Sans', Arial, sans-serif; max-width: 560px; margin: 0 auto; background: #F5F0E8; border-radius: 16px; overflow: hidden;">
    <div style="background: #2D6A4F; padding: 32px 36px; text-align: center;">
      <div style="font-size: 1.15rem; font-weight: 600; color: white; letter-spacing: -0.02em;">
        Bailleur<span style="color: #C9A84C;">Suite</span>
      </div>
    </div>
    <div style="padding: 36px 36px 28px;">${corps}</div>
    ${PIED(email)}
  </div>`;

function emailRappel(email) {
  return {
    subject: 'C\'est noté — votre rappel déclaration 2027',
    htmlContent: ENVELOPPE(`
      <h1 style="font-size: 1.4rem; color: #1C1C1E; margin: 0 0 12px; font-weight: 600; line-height: 1.3;">
        Votre rappel est enregistré
      </h1>
      <p style="color: #4A4A44; font-size: 0.95rem; line-height: 1.65; margin: 0 0 20px;">
        Vous recevrez un email en avril 2027, avant l'ouverture de la déclaration
        de revenus : la marche à suivre pour vos revenus fonciers, et les dates
        limites selon votre département.
      </p>
      <p style="color: #4A4A44; font-size: 0.95rem; line-height: 1.65; margin: 0 0 24px;">
        D'ici là, nous ne vous écrirons pas. C'est le seul email que vous avez demandé.
      </p>
      <hr style="border: none; border-top: 1px solid #E0D9CC; margin: 28px 0;">
      <p style="color: #8A8A84; font-size: 0.82rem; line-height: 1.6; margin: 0;">
        BailleurSuite est disponible sur l'App Store : quittances automatiques,
        suivi du rendement et préparation de la déclaration, directement sur iPhone.
      </p>`, email),
  };
}

function emailGuide(email) {
  return {
    subject: '📋 Votre guide 2044 est ici — BailleurSuite',
    htmlContent: ENVELOPPE(`
      <h1 style="font-size: 1.4rem; color: #1C1C1E; margin: 0 0 12px; font-weight: 600; line-height: 1.3;">
        Votre guide est prêt 🎉
      </h1>
      <p style="color: #4A4A44; font-size: 0.95rem; line-height: 1.65; margin: 0 0 24px;">
        Voici votre guide <strong>« Comment remplir sa déclaration 2044 »</strong> —
        12 pages pour déclarer vos revenus fonciers sans stress.
      </p>
      <div style="text-align: center; margin: 28px 0;">
        <a href="https://bailleursuite.fr/public/guide-2044.pdf"
           style="display: inline-block; background: #2D6A4F; color: white; padding: 14px 28px; border-radius: 12px; text-decoration: none; font-weight: 600; font-size: 0.95rem;">
          📋 Télécharger le guide PDF
        </a>
      </div>
      <hr style="border: none; border-top: 1px solid #E0D9CC; margin: 28px 0;">
      <p style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #2D6A4F; margin: 0 0 12px;">
        Dans l'application
      </p>
      <ul style="color: #4A4A44; font-size: 0.88rem; line-height: 1.8; padding-left: 20px; margin: 0 0 24px;">
        <li>Quittances PDF automatiques chaque mois</li>
        <li>Déclaration 2044 pré-remplie depuis vos données</li>
        <li>Module LMNP avec configurateur d'amortissements</li>
      </ul>
      <p style="color: #8A8A84; font-size: 0.82rem; line-height: 1.6; margin: 0;">
        BailleurSuite est disponible sur l'App Store.
      </p>`, email),
  };
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', 'https://bailleursuite.fr');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { email } = req.body || {};
  const brut = (req.body && req.body.source ? String(req.body.source) : '').trim();
  const source = SOURCES.has(brut) ? brut : 'inconnu';

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Email invalide' });
  }

  const BREVO_API_KEY = process.env.BREVO_API_KEY;
  const LIST_ID = parseInt(process.env.BREVO_LIST_ID);

  if (!BREVO_API_KEY || Number.isNaN(LIST_ID)) {
    console.error('BREVO_API_KEY ou BREVO_LIST_ID absente');
    return res.status(500).json({ error: 'Service indisponible' });
  }

  const entetes = {
    'accept': 'application/json',
    'content-type': 'application/json',
    'api-key': BREVO_API_KEY,
  };

  async function creerContact(avecAttributs) {
    const corps = { email, listIds: [LIST_ID], updateEnabled: true };
    if (avecAttributs) corps.attributes = { SOURCE: source };
    return fetch('https://api.brevo.com/v3/contacts', {
      method: 'POST', headers: entetes, body: JSON.stringify(corps),
    });
  }

  try {
    let contactRes = await creerContact(true);

    // Brevo rejette un attribut qui n'existe pas dans le compte. Plutôt
    // que de perdre l'inscription, on réessaie sans l'attribut et on
    // laisse une trace explicite : l'attribut SOURCE est à créer dans
    // Brevo (Contacts → Attributs) pour que la segmentation fonctionne.
    if (contactRes.status === 400) {
      const err = await contactRes.clone().json().catch(() => ({}));
      if (err.code === 'invalid_parameter') {
        console.warn('Attribut SOURCE inconnu de Brevo — inscription sans segmentation. '
                     + 'Créer un attribut texte « SOURCE » dans Brevo.');
        contactRes = await creerContact(false);
      }
    }

    if (!contactRes.ok && contactRes.status !== 204) {
      const err = await contactRes.json().catch(() => ({}));
      // duplicate_parameter = déjà inscrit : ce n'est pas une erreur.
      if (err.code !== 'duplicate_parameter') {
        console.error('Brevo contact error:', err);
        return res.status(500).json({ error: 'Erreur ajout contact' });
      }
    }

    const modele = SOURCES_GUIDE.has(source) ? emailGuide(email) : emailRappel(email);

    const emailRes = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: entetes,
      body: JSON.stringify({
        sender: { name: 'BailleurSuite', email: process.env.BREVO_SENDER_EMAIL },
        to: [{ email }],
        // En-tête normalisé : les clients mail affichent leur propre
        // bouton de désinscription et les filtres anti-spam le lisent.
        headers: { 'List-Unsubscribe': `<${lienDesinscription(email)}>` },
        ...modele,
      }),
    });

    if (!emailRes.ok) {
      const err = await emailRes.json().catch(() => ({}));
      console.error('Brevo email error:', err);
      // Le contact est inscrit : l'échec d'envoi ne doit pas être
      // présenté comme un échec d'inscription, sinon le visiteur
      // resoumet et se retrouve inscrit deux fois.
      return res.status(200).json({ success: true, warning: 'Contact inscrit mais email non envoyé' });
    }

    return res.status(200).json({ success: true });

  } catch (err) {
    console.error('Unexpected error:', err);
    return res.status(500).json({ error: 'Erreur serveur' });
  }
}
