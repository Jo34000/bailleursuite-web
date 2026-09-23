/* Envoi des événements d'usage vers /api/track.
 *
 * sendBeacon plutôt que fetch : un clic sur un lien App Store change de
 * page dans la foulée, et une requête fetch en vol est annulée quand le
 * document se démonte. Le navigateur, lui, garde la charge d'un beacon
 * en file et la livre même après la navigation.
 *
 * L'appel à window.va est conservé : les événements personnalisés de
 * Vercel Analytics demandent l'offre Pro et ne remontent rien
 * aujourd'hui, mais le jour où le compte y passe, ils fonctionneront
 * sans qu'il faille repasser sur les 232 liens du site.
 */
(function () {
  'use strict';

  var POINT = '/api/track';

  window.track = function (evenement, donnees) {
    var charge = { event: evenement };
    if (donnees) {
      for (var k in donnees) {
        if (Object.prototype.hasOwnProperty.call(donnees, k)) charge[k] = donnees[k];
      }
    }

    /* Aligne le jeton sur celui que l'App Store recevra. L'attribut
     * onclick porte un ct figé à la génération de la page ;
     * source-tracking.js, lui, a déjà préfixé l'URL. Sans ce rattrapage,
     * les deux mesures d'un même clic porteraient des noms différents. */
    if (window.__bsAds && typeof charge.ct === 'string'
        && charge.ct.indexOf('ads_') !== 0) {
      charge.ct = 'ads_' + charge.ct;
    }

    // Vercel Analytics, pour le jour où l'offre le permettra.
    if (window.va) window.va('event', { name: evenement, data: donnees || {} });

    // Conversion Google Ads, si le consentement a été accordé.
    if (window.bsConversion) window.bsConversion(evenement);

    if (!navigator.sendBeacon) return;
    var texte = JSON.stringify(charge);
    try {
      // Un Blob typé application/json permet au serveur de désérialiser
      // directement ; une chaîne nue partirait en text/plain. Le repli
      // couvre les navigateurs qui refusent un Blob à sendBeacon.
      if (!navigator.sendBeacon(POINT, new Blob([texte], { type: 'application/json' }))) {
        navigator.sendBeacon(POINT, texte);
      }
    } catch (e) {
      try { navigator.sendBeacon(POINT, texte); } catch (e2) { /* tant pis */ }
    }
  };
})();
