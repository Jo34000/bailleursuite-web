// Accès Upstash par son API REST, sans dépendance npm.
//
// Vercel injecte les identifiants sous deux noms selon la façon dont la
// base a été rattachée au projet : UPSTASH_REDIS_REST_* quand elle vient
// de l'intégration Upstash, KV_REST_API_* quand elle vient du Marketplace.
// Les deux désignent la même base ; on prend ce qui est présent.

export function identifiants() {
  const url = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
  if (!url || !token) return null;
  return { url: url.replace(/\/+$/, ''), token };
}

/* Exécute plusieurs commandes en un aller-retour.
 * `commandes` : [['INCR', 'cle'], ['EXPIRE', 'cle', '3456000'], …]
 * Renvoie le tableau des résultats, ou lève. */
export async function pipeline(commandes) {
  const id = identifiants();
  if (!id) throw new Error('Aucun identifiant Redis dans l\'environnement');

  const r = await fetch(`${id.url}/pipeline`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${id.token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(commandes),
  });

  if (!r.ok) {
    throw new Error(`Redis HTTP ${r.status} : ${(await r.text()).slice(0, 200)}`);
  }
  const reponses = await r.json();
  // Upstash renvoie [{result}|{error}, …] dans l'ordre des commandes.
  return reponses.map((x) => {
    if (x && x.error) throw new Error(`Redis : ${x.error}`);
    return x ? x.result : null;
  });
}

// Jour au format AAAA-MM-JJ, en heure de Paris. Les fonctions Vercel
// tournent en UTC : sans ce décalage, tout ce qui se passe entre minuit
// et 2 h du matin l'été serait compté la veille.
export function jour(date = new Date()) {
  return new Intl.DateTimeFormat('fr-CA', {
    timeZone: 'Europe/Paris',
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(date);
}
