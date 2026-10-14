(() => {
  const button = document.getElementById('scuola-notify');
  const status = document.getElementById('scuola-notify-status');
  if (!button || !status) return;

  let oneSignal = null;
  const say = (message) => {
    status.textContent = message;
    status.hidden = !message;
  };
  const isAppleMobile = /iPhone|iPad|iPod/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isInstalled = window.matchMedia('(display-mode: standalone)').matches
    || navigator.standalone === true;

  button.addEventListener('click', async () => {
    if (isAppleMobile && !isInstalled) {
      say('Su iPhone o iPad: Condividi → Aggiungi alla schermata Home. Poi apri eureka! dall’icona e attiva le notifiche.');
      return;
    }
    if (!oneSignal) {
      say('Il servizio notifiche non è ancora pronto. Ricarica la pagina e riprova tra qualche secondo.');
      return;
    }

    button.disabled = true;
    say('');
    try {
      await oneSignal.Notifications.requestPermission();
      if (oneSignal.Notifications.permission) {
        await oneSignal.User.PushSubscription.optIn();
        button.textContent = 'notifiche attive';
        say('Notifiche attivate. Ti avviseremo quando esce una nuova circolare.');
      } else {
        say('Permesso non concesso. Puoi abilitarlo dalle impostazioni del browser.');
      }
    } catch (error) {
      console.error('Attivazione notifiche non riuscita.', error);
      say('Non è stato possibile attivare le notifiche. Controlla i permessi del browser e riprova.');
    } finally {
      button.disabled = false;
    }
  });

  async function start() {
    try {
      const configUrl = new URL('assets/notifications/config.json', document.baseURI);
      const response = await fetch(configUrl, { cache: 'no-store' });
      if (!response.ok) throw new Error(`config HTTP ${response.status}`);
      const config = await response.json();
      if (!config.appId || !/^[\da-f-]{36}$/i.test(config.appId)) {
        throw new Error('App ID non configurato');
      }

      window.OneSignalDeferred = window.OneSignalDeferred || [];
      const sdkReady = new Promise((resolve, reject) => {
        const sdk = document.createElement('script');
        sdk.src = 'https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js';
        sdk.defer = true;
        sdk.onload = resolve;
        sdk.onerror = () => reject(new Error('SDK OneSignal non raggiungibile'));
        document.head.appendChild(sdk);
      });
      await sdkReady;

      oneSignal = await new Promise((resolve, reject) => {
        window.OneSignalDeferred.push(async (OneSignal) => {
          try {
            const scope = new URL('./', document.baseURI).pathname;
            const workerPath = new URL('OneSignalSDKWorker.js', document.baseURI).pathname;
            await OneSignal.init({
              appId: config.appId,
              serviceWorkerPath: workerPath,
              serviceWorkerParam: { scope }
            });
            resolve(OneSignal);
          } catch (error) {
            reject(error);
          }
        });
      });

      if (oneSignal.Notifications.permission && oneSignal.User.PushSubscription.optedIn) {
        button.textContent = 'notifiche attive';
      }
    } catch (error) {
      console.error('Inizializzazione notifiche non riuscita.', error);
      say('Non riusciamo a caricare il servizio notifiche. Riprova più tardi.');
    }
  }

  start();
})();
