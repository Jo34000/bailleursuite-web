import { jetonValide } from './_token.js';

// Désinscription en un clic, depuis le pied de chaque email envoyé.
// Le lien doit fonctionner sans compte, sans formulaire et sans étape
// intermédiaire : c'est ce que promet le texte du formulaire, et ce
// qu'impose un envoi commercial.

function page(titre, message, ton = 'ok') {
  const accent = ton === 'ok' ? '#2D6A4F' : '#8A6100';
  return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>${titre} — BailleurSuite</title>
<style>
  body { margin:0; background:#F7F4EE; color:#1C1A14;
         font-family:'DM Sans',-apple-system,BlinkMacSystemFont,sans-serif;
         display:flex; align-items:center; justify-content:center;
         min-height:100vh; padding:24px; }
  .carte { background:#fff; border:1px solid rgba(28,26,20,.1); border-radius:14px;
           padding:36px 32px; max-width:440px; text-align:center; }
  h1 { font-size:1.3rem; margin:0 0 12px; color:${accent}; font-weight:600; }
  p { font-size:.92rem; line-height:1.65; color:#4A4A44; margin:0 0 20px; }
  a { display:inline-block; background:#1C1A14; color:#fff; text-decoration:none;
      padding:12px 24px; border-radius:999px; font-size:.86rem; font-weight:600; }
</style>
</head>
<body>
  <div class="carte">
    <h1>${titre}</h1>
    <p>${message}</p>
    <a href="https://bailleursuite.fr/">Retour à BailleurSuite</a>
  </div>
</body>
</html>`;
}

export default async function handler(req, res) {
  res.setHeader('Content-Type', 'text/html; charset=utf-8');

  if (req.method !== 'GET') {
    return res.status(405).send(page('Méthode non autorisée',
      'Ce lien s\'ouvre depuis un email.', 'warn'));
  }

  const email = (req.query.e || '').toString().trim();
  const token = (req.query.t || '').toString();

  if (!email || !jetonValide(email, token)) {
    // Message identique qu'il s'agisse d'une adresse inconnue ou d'un
    // jeton faux : rien ne doit permettre de tester si une adresse est
    // inscrite.
    return res.status(400).send(page('Lien invalide',
      'Ce lien de désinscription est incomplet ou a expiré. '
      + 'Répondez simplement au dernier email reçu et nous vous retirons de la liste.',
      'warn'));
  }

  const BREVO_API_KEY = process.env.BREVO_API_KEY;
  if (!BREVO_API_KEY) {
    console.error('BREVO_API_KEY absente — désinscription impossible');
    return res.status(500).send(page('Erreur temporaire',
      'Nous n\'avons pas pu traiter votre demande. Réessayez dans quelques minutes.',
      'warn'));
  }

  try {
    const r = await fetch(
      `https://api.brevo.com/v3/contacts/${encodeURIComponent(email)}`,
      {
        method: 'PUT',
        headers: {
          'accept': 'application/json',
          'content-type': 'application/json',
          'api-key': BREVO_API_KEY,
        },
        // emailBlacklisted vaut pour tous les envois, pas seulement la
        // liste d'origine : une désinscription doit être définitive.
        body: JSON.stringify({ emailBlacklisted: true }),
      });

    // 204 = mis à jour. 404 = adresse inconnue : du point de vue du
    // visiteur le résultat est le même, il ne recevra rien.
    if (!r.ok && r.status !== 404) {
      const detail = await r.text();
      console.error('Brevo unsubscribe error:', r.status, detail);
      return res.status(500).send(page('Erreur temporaire',
        'Nous n\'avons pas pu traiter votre demande. Réessayez dans quelques minutes.',
        'warn'));
    }
  } catch (err) {
    console.error('Unexpected error:', err);
    return res.status(500).send(page('Erreur temporaire',
      'Nous n\'avons pas pu traiter votre demande. Réessayez dans quelques minutes.',
      'warn'));
  }

  return res.status(200).send(page('Vous êtes désinscrit',
    'Vous ne recevrez plus aucun email de BailleurSuite. '
    + 'Aucune action supplémentaire n\'est nécessaire.'));
}
