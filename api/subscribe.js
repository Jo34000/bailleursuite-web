export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', 'https://bailleursuite.fr');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { email } = req.body;

  // Validation basique
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Email invalide' });
  }

  const BREVO_API_KEY = process.env.BREVO_API_KEY;
  const LIST_ID = parseInt(process.env.BREVO_LIST_ID); // ex: 3

  try {
    // 1. Ajouter le contact à la liste Brevo
    const contactRes = await fetch('https://api.brevo.com/v3/contacts', {
      method: 'POST',
      headers: {
        'accept': 'application/json',
        'content-type': 'application/json',
        'api-key': BREVO_API_KEY,
      },
      body: JSON.stringify({
        email,
        listIds: [LIST_ID],
        updateEnabled: true, // si déjà inscrit, on l'ajoute quand même à la liste
      }),
    });

    // 202 = déjà existant mis à jour, 201 = créé
    if (!contactRes.ok && contactRes.status !== 204) {
      const err = await contactRes.json();
      // Code 'duplicate_parameter' = email déjà inscrit, on continue quand même
      if (err.code !== 'duplicate_parameter') {
        console.error('Brevo contact error:', err);
        return res.status(500).json({ error: 'Erreur ajout contact' });
      }
    }

    // 2. Envoyer l'email transactionnel avec le guide
    const emailRes = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: {
        'accept': 'application/json',
        'content-type': 'application/json',
        'api-key': BREVO_API_KEY,
      },
      body: JSON.stringify({
        sender: {
          name: 'BailleurSuite',
          email: process.env.BREVO_SENDER_EMAIL, // ex: bonjour@bailleursuite.fr
        },
        to: [{ email }],
        subject: '📋 Votre guide 2044 est ici — BailleurSuite',
        htmlContent: `
          <div style="font-family: 'DM Sans', Arial, sans-serif; max-width: 560px; margin: 0 auto; background: #F5F0E8; border-radius: 16px; overflow: hidden;">
            
            <!-- Header -->
            <div style="background: #2D6A4F; padding: 32px 36px; text-align: center;">
              <div style="font-size: 1.15rem; font-weight: 600; color: white; letter-spacing: -0.02em;">
                Bailleur<span style="color: #C9A84C;">Suite</span>
              </div>
            </div>

            <!-- Body -->
            <div style="padding: 36px 36px 28px;">
              <h1 style="font-size: 1.4rem; color: #1C1C1E; margin: 0 0 12px; font-weight: 600; line-height: 1.3;">
                Votre guide est prêt 🎉
              </h1>
              <p style="color: #4A4A44; font-size: 0.95rem; line-height: 1.65; margin: 0 0 24px;">
                Merci de rejoindre la liste d'attente BailleurSuite.<br>
                Voici votre guide <strong>« Comment remplir sa déclaration 2044 »</strong> — 12 pages pour déclarer vos revenus fonciers sans stress.
              </p>

              <!-- CTA PDF -->
              <div style="text-align: center; margin: 28px 0;">
                <a href="https://bailleursuite.fr/public/guide-2044.pdf"
                   style="display: inline-block; background: #2D6A4F; color: white; padding: 14px 28px; border-radius: 12px; text-decoration: none; font-weight: 600; font-size: 0.95rem;">
                  📋 Télécharger le guide PDF
                </a>
              </div>

              <!-- Séparateur -->
              <hr style="border: none; border-top: 1px solid #E0D9CC; margin: 28px 0;">

              <!-- Ce qui vous attend -->
              <p style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #2D6A4F; margin: 0 0 12px;">
                Ce qui vous attend au lancement
              </p>
              <ul style="color: #4A4A44; font-size: 0.88rem; line-height: 1.8; padding-left: 20px; margin: 0 0 24px;">
                <li>Accès prioritaire à la bêta TestFlight</li>
                <li>Quittances PDF automatiques chaque mois</li>
                <li>Déclaration 2044 pré-remplie depuis vos données</li>
                <li>Module LMNP avec configurateur d'amortissements</li>
              </ul>

              <p style="color: #8A8A84; font-size: 0.82rem; line-height: 1.6; margin: 0;">
                Vous recevrez un email au lancement — prévu <strong>septembre 2026</strong>.<br>
                En attendant, n'hésitez pas à partager BailleurSuite autour de vous.
              </p>
            </div>

            <!-- Footer -->
            <div style="background: #1C1C1E; padding: 20px 36px; text-align: center;">
              <p style="color: rgba(255,255,255,0.4); font-size: 0.72rem; margin: 0; line-height: 1.6;">
                BailleurSuite · Application iOS pour bailleurs particuliers français<br>
                <a href="https://bailleursuite.fr/politique-confidentialite.html" style="color: rgba(255,255,255,0.4);">Politique de confidentialité</a>
                · <a href="https://bailleursuite.fr/unsubscribe?email=${email}" style="color: rgba(255,255,255,0.4);">Se désabonner</a>
              </p>
            </div>

          </div>
        `,
      }),
    });

    if (!emailRes.ok) {
      const err = await emailRes.json();
      console.error('Brevo email error:', err);
      // On ne bloque pas — le contact est inscrit, l'email est le seul problème
      return res.status(200).json({ success: true, warning: 'Contact inscrit mais email non envoyé' });
    }

    return res.status(200).json({ success: true });

  } catch (err) {
    console.error('Unexpected error:', err);
    return res.status(500).json({ error: 'Erreur serveur' });
  }
}
