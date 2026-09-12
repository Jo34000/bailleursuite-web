/* Formulaires de rappel fiscal — envoi vers /api/subscribe.
 *
 * Fichier partagé plutôt que recopié : les quatre emplacements (deux
 * guides, la calculatrice et les pages villes du Radar) doivent se
 * comporter à l'identique, et les pages villes sont générées — une
 * copie par page aurait figé quarante variantes divergentes.
 *
 * Chargé en `defer` : le DOM est prêt, pas besoin d'attendre un
 * événement supplémentaire.
 */
(function () {
  'use strict';

  var ENDPOINT = '/api/subscribe';

  function statut(form) {
    var el = form.parentNode.querySelector('.email-status');
    if (!el) {
      el = document.createElement('p');
      el.className = 'email-status';
      el.setAttribute('role', 'status');
      el.setAttribute('aria-live', 'polite');
      form.parentNode.insertBefore(el, form.nextSibling);
    }
    return el;
  }

  function afficher(el, texte, ok) {
    el.textContent = texte;
    el.className = 'email-status ' + (ok ? 'is-ok' : 'is-ko');
    el.hidden = false;
  }

  document.querySelectorAll('form.email-form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();

      var champ = form.querySelector('input[type="email"]');
      var bouton = form.querySelector('button[type="submit"]');
      var source = form.getAttribute('data-source') || 'inconnu';
      var email = (champ.value || '').trim();
      var msg = statut(form);

      if (!email) { champ.focus(); return; }

      var libelle = bouton.textContent;
      bouton.disabled = true;
      bouton.textContent = 'Envoi…';
      msg.hidden = true;

      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, source: source }),
      })
        .then(function (r) {
          return r.json().catch(function () { return {}; }).then(function (data) {
            return { ok: r.ok, data: data };
          });
        })
        .then(function (res) {
          if (!res.ok) {
            // Le message du serveur est affiché tel quel quand il
            // existe : « Email invalide » est plus utile qu'un libellé
            // générique.
            throw new Error(res.data.error || '');
          }
          // Le formulaire disparaît : le laisser en place invite à
          // resoumettre, ce qui déclencherait un second email.
          form.hidden = true;
          var note = form.parentNode.querySelector('.email-note');
          if (note) note.hidden = true;
          afficher(msg, 'C\'est noté. Vous recevrez un email de confirmation '
                        + 'dans quelques instants.', true);
          if (window.va) window.va('event', { name: 'Email_Capture', data: { source: source } });
        })
        .catch(function (err) {
          afficher(msg, err.message
            || 'L\'envoi a échoué. Vérifiez votre connexion et réessayez.', false);
          bouton.disabled = false;
          bouton.textContent = libelle;
        });
    });
  });
})();
