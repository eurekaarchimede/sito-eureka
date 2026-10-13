(() => {
  const button = document.getElementById('scuola-notify');
  const status = document.getElementById('scuola-notify-status');
  if (!button || !status) return;

  const say = (message) => {
    status.textContent = message;
    status.hidden = !message;
  };
  const isAppleMobile = /iPhone|iPad|iPod/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isInstalled = window.matchMedia('(display-mode: standalone)').matches
    || navigator.standalone === true;

  async function start() {
    try {
      const configUrl = new URL('assets/notifications/config.json', document.baseURI);
      const response = await fetch(configUrl, { cache: 'no-store' });
      if (!response.ok) return;
      const config = await response.json();
      if (!config.appId || !/^[\da-f-]{36}$/i.test(config.appId)) return;

      const sdk = document.createElement('script');
      sdk.src = 'https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js';
      sdk.defer = true;
      document.head.appendChild(sdk);
      window.OneSignalDeferred = window.OneSignalDeferred || [];
      window.OneSignalDeferred.push(async (OneSignal) => {
        try {
          const scope = new URL('./', document.baseURI).pathname;
          const workerPath = new URL('OneSignalSDKWorker.js', document.baseURI).pathname;
          await OneSignal.init({
            appId: config.appId,
            serviceWorkerPath: workerPath,
            serviceWorkerParam: { scope }
          });
          button.hidden = false;
          if (OneSignal.Notifications.permission) {
            button.textContent = 'notifiche attive';
            button.disabled = true;
          }
          button.addEventListener('click', async () => {
            if (isAppleMobile && !isInstalled) {
              say('Su iPhone o iPad: Condividi → Aggiungi alla schermata Home. Poi apri eureka! dall’icona e attiva le notifiche.');
              return;
            }
            button.disabled = true;
            say('');
            try {
              await OneSignal.Notifications.requestPermission();
              if (OneSignal.Notifications.permission) {
                await OneSignal.User.PushSubscription.optIn();
                button.textContent = 'notifiche attive';
                say('Notifiche attivate. Ti avviseremo quando esce una nuova circolare.');
              } else {
                button.disabled = false;
                say('Permesso non concesso. Puoi abilitarlo dalle impostazioni del browser.');
              }
            } catch (error) {
              button.disabled = false;
              say('Non è stato possibile attivare le notifiche. Riprova tra poco.');
            }
          });
        } catch (error) {
          console.error('Inizializzazione notifiche non riuscita.', error);
        }
      });
    } catch (error) {
      console.error('Configurazione notifiche non disponibile.', error);
    }
  }

  start();
})();
