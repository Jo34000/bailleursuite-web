/* Navigation : menu mobile et menus déroulants.
 *
 * Le balisage vient de tools/nav.py. Sans JavaScript, les menus
 * déroulants s'ouvrent encore au survol et tous les liens restent dans
 * le pied de page ; le script ajoute l'ouverture au clavier
 * (aria-expanded), la fermeture par Échap et par clic à l'extérieur. */
(function () {
  'use strict';

  var burger = document.getElementById('nav-burger');
  var menu = document.getElementById('nav-mobile-menu');
  var racine = document.documentElement;

  function fermerMenu(rendreFocus) {
    if (!menu || !menu.classList.contains('is-open')) return;
    menu.classList.remove('is-open');
    racine.classList.remove('nav-ouvert');
    burger.setAttribute('aria-expanded', 'false');
    burger.setAttribute('aria-label', 'Ouvrir le menu');
    if (rendreFocus) burger.focus();
  }

  if (burger && menu) {
    burger.addEventListener('click', function () {
      var ouvert = menu.classList.toggle('is-open');
      racine.classList.toggle('nav-ouvert', ouvert);
      burger.setAttribute('aria-expanded', String(ouvert));
      burger.setAttribute('aria-label', ouvert ? 'Fermer le menu' : 'Ouvrir le menu');
    });
    window.addEventListener('resize', function () {
      if (window.innerWidth > 900) fermerMenu(false);
    });
  }

  var declencheurs = Array.prototype.slice.call(document.querySelectorAll('.nav-drop-trigger'));

  function fermerDrops(sauf) {
    declencheurs.forEach(function (d) {
      if (d !== sauf) d.setAttribute('aria-expanded', 'false');
    });
  }

  declencheurs.forEach(function (d) {
    d.addEventListener('click', function () {
      var ouvert = d.getAttribute('aria-expanded') === 'true';
      fermerDrops(d);
      d.setAttribute('aria-expanded', String(!ouvert));
    });
    // Le focus quitte le groupe (Tab au-delà du dernier lien) : on referme.
    d.parentNode.addEventListener('focusout', function (e) {
      if (!d.parentNode.contains(e.relatedTarget)) d.setAttribute('aria-expanded', 'false');
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var ouvert = declencheurs.filter(function (d) { return d.getAttribute('aria-expanded') === 'true'; })[0];
    if (ouvert) { ouvert.setAttribute('aria-expanded', 'false'); ouvert.focus(); return; }
    fermerMenu(true);
  });

  document.addEventListener('click', function (e) {
    if (!e.target.closest || !e.target.closest('.nav-drop')) fermerDrops(null);
    if (menu && menu.classList.contains('is-open') && !menu.contains(e.target) && !burger.contains(e.target)) {
      fermerMenu(false);
    }
  });
})();
