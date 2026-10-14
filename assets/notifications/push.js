(() => {
  const button = document.getElementById('scuola-notify');
  const status = document.getElementById('scuola-notify-status');
  const install = document.getElementById('scuola-install');
  if (!button || !status) return;

  let oneSignal = null;
  let starting = false;
  let activating = false;
  const isAppleMobile = /iPhone|iPad|iPod/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isInstalled = window.matchMedia('(display-mode: standalone)').matches
    || navigator.standalone === true;
  const needsInstall = isAppleMobile && !isInstalled;
  const say = message => { status.textContent = message; status.hidden = !message; };
  const subscribed = () => !!(oneSignal?.User.PushSubscription.optedIn && oneSignal.User.PushSubscription.id);
  const syncButton = () => {
    if (needsInstall) { button.textContent = 'attiva su iOS / Android'; return; }
    button.textContent = subscribed() ? 'notifiche attive' : 'attiva su iOS / Android';
  };
  const withTimeout = (promise, milliseconds, message) => {
    let timer;
    return Promise.race([
      promise,
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(message)), milliseconds); })
    ]).finally(() => clearTimeout(timer));
  };
  const waitForSubscription = () => {
    if (subscribed()) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const deadline = Date.now() + 15000;
      const check = () => {
        if (subscribed()) return resolve();
        if (Date.now() >= deadline) return reject(new Error('Iscrizione OneSignal non confermata'));
        setTimeout(check, 200);
      };
      check();
    });
  };

  button.addEventListener('click', async () => {
    if (needsInstall) {
      say('Aggiungi eureka! alla schermata Home, aprila dalla sua icona e attiva le notifiche.');
      return;
    }
    if (!oneSignal) { start(); return; }
    if (subscribed()) { say('Sei già iscritto: riceverai un avviso per le nuove circolari.'); return; }
    if (!oneSignal.Notifications.isPushSupported()) {
      say('Questo browser non supporta le notifiche. Usa un browser aggiornato; su iPhone apri eureka! dalla Home.');
      return;
    }
    if (window.Notification?.permission === 'denied') {
      say('Le notifiche sono bloccate. Abilitale nelle impostazioni del browser per questo sito, poi riprova.');
      return;
    }

    activating = true;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    try {
      // La richiesta del permesso parte direttamente dal tap, come richiesto da iOS.
      await oneSignal.Notifications.requestPermission();
      if (!oneSignal.Notifications.permission) {
        say('Permesso non concesso. Puoi abilitarlo dalle impostazioni del browser.');
        return;
      }
      say('Registrazione delle notifiche in corso…');
      await oneSignal.User.PushSubscription.optIn();
      await waitForSubscription();
      say('Notifiche attivate. Ti avviseremo quando esce una nuova circolare.');
    } catch (error) {
      console.error('Attivazione notifiche non riuscita.', error);
      say('Iscrizione non completata. Controlla la connessione e riprova.');
    } finally {
      activating = false;
      button.disabled = false;
      button.setAttribute('aria-busy', 'false');
      syncButton();
    }
  });

  async function start() {
    if (starting || needsInstall) return;
    starting = true;
    button.disabled = true;
    button.textContent = 'caricamento notifiche…';
    button.setAttribute('aria-busy', 'true');
    say('');
    try {
      const response = await withTimeout(fetch(new URL('assets/notifications/config.json', document.baseURI),
        { cache: 'no-store' }), 8000, 'Configurazione non raggiungibile');
      if (!response.ok) throw new Error(`config HTTP ${response.status}`);
      const config = await response.json();
      if (!config.appId || !/^[\da-f-]{36}$/i.test(config.appId)) throw new Error('App ID non configurato');

      window.OneSignalDeferred = window.OneSignalDeferred || [];
      if (!document.getElementById('eureka-onesignal-sdk')) {
        const sdk = document.createElement('script');
        sdk.id = 'eureka-onesignal-sdk';
        sdk.src = 'https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js';
        sdk.defer = true;
        sdk.onerror = () => { sdk.remove(); };
        document.head.appendChild(sdk);
      }
      await withTimeout(new Promise((resolve, reject) => {
        window.OneSignalDeferred.push(async OneSignal => {
          try {
            if (!oneSignal) {
              await OneSignal.init({
                appId: config.appId,
                serviceWorkerPath: new URL('OneSignalSDKWorker.js', document.baseURI).pathname,
                serviceWorkerParam: { scope: new URL('./', document.baseURI).pathname },
                notifyButton: { enable: false }
              });
              oneSignal = OneSignal;
              OneSignal.User.PushSubscription.addEventListener('change', () => {
                if (!activating) syncButton();
              });
              OneSignal.Notifications.addEventListener('permissionChange', () => {
                if (!activating) syncButton();
              });
              syncButton();
            }
            resolve();
          } catch (error) { reject(error); }
        });
      }), 15000, 'OneSignal non pronto');
      if (!oneSignal.Notifications.isPushSupported()) {
        say('Questo browser non supporta le notifiche. Usa un browser aggiornato.');
      }
    } catch (error) {
      console.error('Inizializzazione notifiche non riuscita.', error);
      say('Servizio notifiche non raggiungibile. Premi il pulsante per riprovare.');
    } finally {
      starting = false;
      button.disabled = false;
      button.setAttribute('aria-busy', 'false');
      syncButton();
    }
  }

  syncButton();
  if (!needsInstall) start();
})();
