/* Consentement cookies et conversions Google Ads.
 *
 * gtag.js dépose des cookies : rien de lui ne doit atteindre le
 * navigateur avant un choix explicite. Le tag n'est donc pas dans le
 * HTML — il est injecté ici, et seulement après acceptation. Un contrôle
 * bloquant (tools/consentement.py) refuse toute trace de
 * googletagmanager dans les pages, pour que ce chemin reste le seul.
 *
 * Vercel Analytics, lui, reste chargé dans tous les cas : sans cookie et
 * sans donnée personnelle, il relève de la mesure d'audience exemptée.
 *
 * Le bandeau est construit en JavaScript plutôt que posé dans les
 * cinquante-deux pages : en `position: fixed`, il ne participe pas au
 * flux et n'induit aucun décalage de mise en page, et une seule
 * définition évite que les pages divergent.
 */
(function () {
  'use strict';

  var CLE = 'bs_consent';
  var ACCORDE = 'granted';
  var REFUSE = 'denied';
  var ID_ADS = 'AW-18454674623';

  /* Libellés de conversion Google Ads.
   *
   * À copier depuis l'interface après création des actions de
   * conversion. Un vrai libellé est une chaîne opaque, par exemple
   * 'AW-18454674623/7d2QCMSm1rEDEP-x4v8o'.
   *
   * Vide tant qu'il n'est pas renseigné : gtag accepte n'importe quel
   * `send_to`, y compris vide ou factice, puis Google le jette en
   * silence. Rien dans l'interface ne distinguerait alors « aucune
   * conversion » de « conversions envoyées à une adresse inexistante ».
   * D'où la validation ci-dessous, doublée d'un contrôle bloquant dans
   * tools/consentement.py. */
  var CONVERSIONS = {
    AppStore_Click: 'AW-18454674623/jQgGCKOK2f0cEL_5799E',        // principale
    Email_Capture: 'AW-18454674623/oePrCNH56v0cEL_5799E',         // secondaire
    Calculatrice_Resultat: 'AW-18454674623/At7LCL6t8f0cEL_5799E', // secondaire
  };

  /* Un libellé plausible : l'identifiant du compte, une barre oblique,
   * puis un jeton contenant au moins une minuscule ou un chiffre.
   * C'est ce dernier point qui écarte les marque-places du genre
   * LIBELLE_APP_STORE ou A_REMPLACER, qui passeraient sinon pour des
   * jetons valides. */
  var FORME_LIBELLE = /^AW-\d{9,12}\/[A-Za-z0-9_-]{8,32}$/;

  /* Certains marque-places ont la forme d'un vrai jeton — à commencer
   * par l'exemple donné plus haut, qui a toutes les apparences requises.
   * Seule une liste explicite les écarte. */
  var JETONS_FACTICES = ['LIBELLE', 'REMPLACER', 'PLACEHOLDER', 'TODO',
                         'XXX', 'EXEMPLE', 'EXAMPLE', 'ABCD'];

  function libelleValide(valeur) {
    if (!valeur || !FORME_LIBELLE.test(valeur)) return false;
    var jeton = valeur.split('/')[1];
    if (!/[a-z0-9]/.test(jeton)) return false;
    var majuscules = jeton.toUpperCase();
    for (var i = 0; i < JETONS_FACTICES.length; i++) {
      if (majuscules.indexOf(JETONS_FACTICES[i]) !== -1) return false;
    }
    return true;
  }

  // ── Stockage ────────────────────────────────────────────────────
  // localStorage lève en navigation privée sur certains navigateurs et
  // quand les données de site sont bloquées. Le bandeau doit rester
  // utilisable dans ce cas : sans mémoire, il se réaffiche, ce qui est
  // le comportement sûr.
  function lire() {
    try { return localStorage.getItem(CLE); } catch (e) { return null; }
  }
  function ecrire(valeur) {
    try { localStorage.setItem(CLE, valeur); } catch (e) { /* sans mémoire */ }
  }

  // ── Google Ads ──────────────────────────────────────────────────
  var gtagCharge = false;

  function chargerGtag() {
    if (gtagCharge) return;
    gtagCharge = true;

    window.dataLayer = window.dataLayer || [];
    // Doit rester une fonction nommée classique : gtag s'appuie sur
    // `arguments`, qu'une fonction fléchée n'a pas.
    window.gtag = function gtag() { window.dataLayer.push(arguments); };

    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + ID_ADS;
    document.head.appendChild(s);

    window.gtag('js', new Date());
    window.gtag('config', ID_ADS);
  }

  /* Déclenche une conversion si, et seulement si, le consentement est
   * accordé, gtag est chargé et le libellé est renseigné. Appelée en
   * parallèle des événements Vercel, qui ne mesurent pas la même chose :
   * Vercel dit quel emplacement a été cliqué, Google Ads rattache le
   * clic à une campagne payante. */
  window.bsConversion = function (nom) {
    if (lire() !== ACCORDE || !gtagCharge) return;
    var envoi = CONVERSIONS[nom];
    if (!envoi) return;
    if (!libelleValide(envoi)) {
      // Visible à la console pendant une recette, plutôt qu'un envoi
      // parti nulle part et des campagnes pilotées sur du vide.
      if (window.console) {
        console.warn('[BailleurSuite] Libellé de conversion invalide pour '
          + nom + ' : « ' + envoi + ' ». Rien n\'a été envoyé.');
      }
      return;
    }
    window.gtag('event', 'conversion', { send_to: envoi });
  };

  // ── Bandeau ─────────────────────────────────────────────────────
  var bandeau = null;

  function fermer() {
    if (!bandeau) return;
    bandeau.remove();
    bandeau = null;
  }

  function choisir(valeur) {
    ecrire(valeur);
    if (valeur === ACCORDE) chargerGtag();
    fermer();
  }

  function afficher() {
    if (bandeau) return;

    bandeau = document.createElement('section');
    bandeau.className = 'bs-consent';
    bandeau.setAttribute('role', 'region');
    bandeau.setAttribute('aria-label', 'Gestion des cookies');

    var texte = document.createElement('p');
    texte.className = 'bs-consent-texte';
    // Court à dessein : le bandeau occupait la moitié d'un écran de
    // téléphone, ce qui en faisait une modale de fait. Le détail est
    // dans la politique de confidentialité, à un lien d'ici.
    texte.innerHTML = 'Cookies de mesure publicitaire : ils nous disent quelles '
      + 'campagnes amènent des bailleurs ici. Rien sans votre accord — et '
      + 'l\'application iPhone n\'est pas concernée. '
      + '<a href="/politique-confidentialite.html">En savoir plus</a>';

    var actions = document.createElement('div');
    actions.className = 'bs-consent-actions';

    // Refuser d'abord dans l'ordre du DOM, et de même poids visuel :
    // refuser doit être aussi simple qu'accepter.
    var non = document.createElement('button');
    non.type = 'button';
    non.className = 'bs-consent-btn bs-consent-refus';
    non.textContent = 'Refuser';
    non.addEventListener('click', function () { choisir(REFUSE); });

    var oui = document.createElement('button');
    oui.type = 'button';
    oui.className = 'bs-consent-btn bs-consent-accord';
    oui.textContent = 'Accepter';
    oui.addEventListener('click', function () { choisir(ACCORDE); });

    actions.appendChild(non);
    actions.appendChild(oui);
    bandeau.appendChild(texte);
    bandeau.appendChild(actions);
    document.body.appendChild(bandeau);
  }

  // ── API publique ────────────────────────────────────────────────
  // Le lien « Gérer les cookies » du pied de page s'en sert pour
  // permettre de revenir sur un choix, accepté comme refusé.
  window.bsConsent = {
    etat: lire,
    ouvrir: afficher,
    accepter: function () { choisir(ACCORDE); },
    refuser: function () { choisir(REFUSE); },
  };

  // ── Démarrage ───────────────────────────────────────────────────
  var etat = lire();
  if (etat === ACCORDE) {
    chargerGtag();
  } else if (etat !== REFUSE) {
    afficher();
  }

  document.addEventListener('click', function (e) {
    var cible = e.target;
    if (!cible || !cible.closest) return;

    if (cible.closest('[data-bs-consent="ouvrir"]')) {
      e.preventDefault();
      afficher();
      return;
    }
    // Conversion principale. Délégué plutôt que posé sur chacun des
    // deux cent trente-deux liens : un seul point à maintenir, et la
    // mécanique suit les liens que le gabarit Jinja ajoutera.
    if (cible.closest('a[href*="apple-store"]')) {
      window.bsConversion('AppStore_Click');
    }
  });
})();
