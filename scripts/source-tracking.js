/* Propagation de la source publicitaire jusqu'à l'App Store.
 *
 * App Store Connect ne voit qu'un jeton de campagne (`ct`). Sans
 * distinction, une installation venue d'une annonce Google et une venue
 * du référencement naturel se confondent sous le même `ct=hero`. Ce
 * script préfixe le jeton par `ads_` quand la visite provient d'une
 * campagne Google, et laisse le jeton intact sinon.
 *
 * Aucun cookie, aucun tiers : les paramètres UTM sont conservés en
 * sessionStorage, c'est-à-dire une mesure de première partie limitée à
 * l'onglet en cours. Le script fonctionne donc sans consentement, et
 * doit rester indépendant de consent.js.
 *
 * La réécriture a lieu au chargement, pas au clic. Un lien n'est pas
 * toujours activé par un clic gauche : molette, Cmd-clic, « ouvrir dans
 * un nouvel onglet » du menu contextuel ou touche Entrée produisent des
 * événements différents, dont certains ne déclenchent aucun `click`.
 * Réécrire l'attribut une fois pour toutes couvre tous ces chemins.
 */
(function () {
  'use strict';

  var CLE = 'bs_utm';
  var CHAMPS = ['utm_source', 'utm_medium', 'utm_campaign'];
  var SOURCE_ADS = 'google';
  var PREFIXE = 'ads_';

  function lire() {
    try { return JSON.parse(sessionStorage.getItem(CLE) || '{}'); }
    catch (e) { return {}; }
  }

  function ecrire(valeurs) {
    try { sessionStorage.setItem(CLE, JSON.stringify(valeurs)); }
    catch (e) { /* navigation privée : la session vaut pour la page */ }
  }

  // ── Capture ─────────────────────────────────────────────────────
  var params;
  try { params = new URLSearchParams(window.location.search); }
  catch (e) { return; }

  var vus = {};
  CHAMPS.forEach(function (champ) {
    var v = params.get(champ);
    if (v) vus[champ] = v;
  });

  // On n'écrase la session que si la page porte effectivement des UTM :
  // sinon une navigation interne, qui n'en a pas, effacerait l'origine
  // de la visite dès la deuxième page.
  var stock = Object.keys(vus).length ? vus : lire();
  if (Object.keys(vus).length) ecrire(vus);

  var source = (stock.utm_source || '').toLowerCase();
  if (source !== SOURCE_ADS) return;

  /* Drapeau lu par scripts/track.js. Le jeton de campagne existe en deux
   * exemplaires pour un même clic : dans l'URL App Store, réécrite
   * ci-dessous, et dans l'attribut onclick du lien, qui porte un ct figé
   * au moment de la génération de la page. Sans ce drapeau, App Store
   * Connect verrait ads_nav et le compteur de première partie nav — deux
   * chiffres qu'on ne pourrait plus rapprocher. */
  window.__bsAds = true;

  // ── Réécriture ──────────────────────────────────────────────────
  var liens = document.querySelectorAll('a[href*="apple-store"]');
  for (var i = 0; i < liens.length; i++) {
    var a = liens[i];
    var url;
    try { url = new URL(a.href); } catch (e) { continue; }

    var ct = url.searchParams.get('ct');
    // Idempotent : un second passage ne produit pas ads_ads_hero.
    if (!ct || ct.indexOf(PREFIXE) === 0) continue;

    url.searchParams.set('ct', PREFIXE + ct);
    a.href = url.toString();
  }
})();
