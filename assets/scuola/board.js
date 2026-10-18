// La versione piccola viene controllata; il catalogo completo si scarica solo se cambia.
(() => {
  const section = document.getElementById('scuola');
  const list = document.getElementById('scuola-circolari');
  const schedules = document.getElementById('scuola-orari');
  const status = document.getElementById('scuola-status');
  const more = document.getElementById('scuola-more');
  const query = document.getElementById('scuola-query');
  const from = document.getElementById('scuola-from');
  const to = document.getElementById('scuola-to');
  const reset = document.getElementById('scuola-reset');
  if (!section || !list || !schedules || !status || !more || !query || !from || !to || !reset) return;

  const localBase = new URL('assets/scuola/', document.baseURI);
  const liveBase = new URL('https://raw.githubusercontent.com/eurekaarchimede/sito-eureka/main/assets/scuola/');
  const published = location.protocol === 'https:' && !['localhost', '127.0.0.1', '::1'].includes(location.hostname);
  const refreshInterval = 30000;
  const idleInterval = 300000;
  const feedCacheKey = 'eureka:circolari:v1';
  let inView = true;
  let failures = 0;
  let refreshTimer;
  let retryAfter = 0;
  let items = [];
  let filtered = [];
  let visibleCount = 4;
  let revision = '';
  let updatedAt = '';
  let loading = false;
  let started = false;
  let retryMessage = '';
  let searchTimer;

  const normalize = value => String(value || '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const isSchoolUrl = value => {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && !url.username && !url.password && !url.port
        && url.hostname === 'www.liceoarchimedeme.edu.it';
    } catch { return false; }
  };
  const dateFormat = new Intl.DateTimeFormat('it-IT', { day: 'numeric', month: 'short', year: 'numeric' });
  const updateFormat = new Intl.DateTimeFormat('it-IT', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Rome'
  });
  const dateLabel = value => {
    const date = new Date(`${String(value || '').slice(0, 10)}T12:00:00`);
    return Number.isNaN(date.getTime()) ? '' : dateFormat.format(date);
  };
  const link = url => {
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener';
    return a;
  };
  const arrow = () => {
    const span = document.createElement('span');
    span.className = 'arrow';
    span.setAttribute('aria-hidden', 'true');
    span.textContent = '↗';
    return span;
  };
  const json = async (url, { cache = 'default', expectedRevision = '' } = {}) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(url, { cache, signal: controller.signal });
      if (!response.ok) {
        const error = new Error(`feed HTTP ${response.status}`);
        const header = response.headers.get('Retry-After');
        const seconds = Number(header);
        error.retryAfter = header ? (Number.isFinite(seconds)
          ? Date.now() + Math.max(0, seconds) * 1000 : Date.parse(header)) : 0;
        throw error;
      }
      const content = await response.text();
      if (expectedRevision) {
        if (!/^[a-f0-9]{64}$/.test(expectedRevision)) throw new Error('versione non valida');
        const bytes = new TextEncoder().encode(content);
        const hash = await crypto.subtle.digest('SHA-256', bytes);
        const actual = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('');
        if (actual !== expectedRevision) throw new Error('catalogo e versione non ancora allineati');
      }
      return JSON.parse(content);
    } finally { clearTimeout(timeout); }
  };
  const versionUrl = base => {
    const url = new URL('version.json', base);
    url.searchParams.set('t', String(Math.floor(Date.now() / refreshInterval)));
    return url;
  };
  const feedUrl = (base, version) => {
    const url = new URL('feed.json', base);
    url.searchParams.set('v', version?.revision || String(Math.floor(Date.now() / refreshInterval)));
    return url;
  };
  const addPage = () => {
    const fragment = document.createDocumentFragment();
    for (const item of filtered.slice(list.children.length, visibleCount)) {
      const li = document.createElement('li');
      const pdfs = Array.isArray(item.pdfs) ? item.pdfs.filter(isSchoolUrl) : [];
      const primary = isSchoolUrl(item.pdf) ? item.pdf : null;
      const a = link(primary || item.url);
      a.className = 'scuola-circolare';
      const details = document.createElement('span');
      details.className = 'details';
      const meta = document.createElement('span');
      meta.className = 'meta';
      const date = document.createElement('time');
      date.dateTime = item.date;
      date.textContent = dateLabel(item.date);
      meta.append(date);
      if (item.number) {
        const number = document.createElement('small');
        number.textContent = item.number;
        meta.append(number);
      }
      const kind = document.createElement('small');
      kind.textContent = primary ? 'PDF diretto' : pdfs.length ? 'PDF nella scheda' : 'scheda ufficiale';
      meta.append(kind);
      const title = document.createElement('strong');
      title.textContent = item.title || 'circolare riservata';
      details.append(meta, title);
      a.append(details, arrow());
      li.append(a);
      if (primary && pdfs.length > 1) {
        const source = link(item.url);
        source.className = 'scuola-source';
        const count = pdfs.length - 1;
        source.textContent = `${count} ${count === 1 ? 'altro PDF' : 'altri PDF'} nella scheda ↗`;
        li.append(source);
      }
      fragment.append(li);
    }
    list.append(fragment);
    more.hidden = list.children.length >= filtered.length;
  };
  const updateStatus = () => {
    const active = normalize(query.value).trim() || from.value || to.value;
    const count = active
      ? `${filtered.length} ${filtered.length === 1 ? 'circolare trovata' : 'circolari trovate'} su ${items.length}`
      : `${items.length} circolari`;
    const date = new Date(updatedAt);
    const time = Number.isNaN(date.getTime()) ? '' : ` · aggiornato ${updateFormat.format(date)}`;
    status.textContent = `${count}${time}${retryMessage}`;
  };
  const update = (resetPage = true) => {
    if (resetPage) visibleCount = 4;
    const invalid = from.value && to.value && from.value > to.value;
    from.setAttribute('aria-invalid', String(!!invalid));
    to.setAttribute('aria-invalid', String(!!invalid));
    if (invalid) {
      list.replaceChildren(); more.hidden = true; reset.hidden = false;
      status.textContent = 'la data iniziale deve precedere la data finale.';
      return;
    }
    const terms = normalize(query.value).trim().split(/\s+/).filter(Boolean);
    filtered = items.filter(item => (!from.value || item.date >= from.value)
      && (!to.value || item.date <= to.value) && terms.every(term => item.searchText.includes(term)));
    list.replaceChildren();
    addPage();
    reset.hidden = !(terms.length || from.value || to.value);
    updateStatus();
  };
  const applyFeed = (data, version) => {
    if (!Array.isArray(data.circolari) || !data.circolari.length) throw new Error('archivio vuoto');
    // Il fallback Pages può essere ancora in pubblicazione: non tornare a una versione precedente.
    if (updatedAt && data.updated_at && data.updated_at < updatedAt) return;
    const nextItems = data.circolari.filter(item => item && isSchoolUrl(item.url)
      && /^\d{4}-\d{2}-\d{2}$/.test(item.date)).map(item => ({
      ...item, searchText: normalize(`${item.title} ${item.number}`)
    })).sort((a, b) => b.date.localeCompare(a.date));
    if (!nextItems.length) throw new Error('nessuna circolare valida');
    const orari = document.createDocumentFragment();
    for (const [kind, label] of [['classi', 'orario classi'], ['docenti', 'orario docenti']]) {
      const item = data.orari?.[kind];
      if (!item || !isSchoolUrl(item.pdf)) continue;
      const a = link(item.pdf);
      a.className = 'scuola-card';
      const info = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = label;
      const date = document.createElement('small');
      date.textContent = `PDF · pubblicato il ${dateLabel(item.date)}`;
      info.append(title, date);
      a.append(info, arrow());
      orari.append(a);
    }
    if (orari.childNodes.length) schedules.replaceChildren(orari);
    items = nextItems;
    updatedAt = data.updated_at || '';
    revision = version?.updated_at === updatedAt ? version.revision : '';
    if (revision) {
      try { localStorage.setItem(feedCacheKey, JSON.stringify({ revision, updatedAt, data })); }
      catch { /* la bacheca funziona anche senza spazio di archiviazione locale */ }
    }
    retryMessage = '';
    update(false);
  };
  const restoreFeed = () => {
    try {
      const cached = JSON.parse(localStorage.getItem(feedCacheKey) || 'null');
      if (!cached || !/^[a-f0-9]{64}$/.test(cached.revision || '')
          || !cached.updatedAt || cached.data?.updated_at !== cached.updatedAt) return false;
      applyFeed(cached.data, { revision: cached.revision, updated_at: cached.updatedAt });
      return !!revision;
    } catch { return false; }
  };
  const scheduleRefresh = () => {
    clearTimeout(refreshTimer);
    if (!started || document.hidden || !navigator.onLine) return;
    const baseDelay = inView ? refreshInterval : idleInterval;
    const delay = Math.min(300000, baseDelay * (2 ** Math.min(failures, 4)));
    // Il jitter distribuisce il picco di letture dopo una notifica collettiva.
    const next = Math.max(delay * (0.9 + Math.random() * 0.2), retryAfter - Date.now());
    refreshTimer = setTimeout(refresh, next);
  };
  const refresh = async () => {
    clearTimeout(refreshTimer);
    if (loading || document.hidden || !navigator.onLine) return;
    if (Date.now() < retryAfter) { scheduleRefresh(); return; }
    loading = true;
    if (!items.length) {
      list.setAttribute('aria-busy', 'true');
      status.textContent = 'caricamento circolari…';
    }
    try {
      let base = published ? liveBase : localBase;
      let version;
      try {
        version = await json(versionUrl(base));
      } catch (error) {
        retryAfter = Math.max(retryAfter, error.retryAfter || 0);
        base = localBase;
        version = await json(versionUrl(base)).catch(() => null);
      }
      if (version?.revision && version.revision === revision) {
        failures = 0;
        retryMessage = '';
        if (!(from.value && to.value && from.value > to.value)) updateStatus();
        return;
      }
      let data;
      try {
        data = await json(feedUrl(base, version), { expectedRevision: version?.revision || '' });
      } catch (error) {
        retryAfter = Math.max(retryAfter, error.retryAfter || 0);
        if (base === localBase) throw error;
        // Pages può servire un commit precedente: usa la sua versione, poi verifica il suo feed.
        version = await json(versionUrl(localBase));
        data = await json(feedUrl(localBase, version), { expectedRevision: version?.revision || '' });
      }
      applyFeed(data, version);
      failures = 0;
    } catch (error) {
      failures++;
      retryAfter = Math.max(retryAfter, error.retryAfter || 0);
      console.warn('Aggiornamento bacheca non riuscito.', error);
      if (items.length) {
        retryMessage = ' · aggiornamento in attesa, riproviamo automaticamente';
        if (!(from.value && to.value && from.value > to.value)) updateStatus();
      } else status.textContent = 'impossibile caricare la bacheca. usa l’archivio ufficiale qui sotto.';
    } finally {
      loading = false;
      list.setAttribute('aria-busy', 'false');
      scheduleRefresh();
    }
  };

  more.addEventListener('click', () => { visibleCount += 12; addPage(); });
  query.addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(update, 150); });
  for (const field of [from, to]) field.addEventListener('input', () => update());
  reset.addEventListener('click', () => {
    clearTimeout(searchTimer);
    query.value = ''; from.value = ''; to.value = '';
    update(); query.focus();
  });
  const start = () => {
    if (started) return;
    started = true;
    restoreFeed();
    refresh();
  };
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearTimeout(refreshTimer);
    else if (started) refresh();
  });
  window.addEventListener('online', () => { if (started) refresh(); });
  window.addEventListener('offline', () => clearTimeout(refreshTimer));
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      inView = entries.some(entry => entry.isIntersecting);
      if (inView) { if (started) refresh(); else start(); }
      else scheduleRefresh();
    }, { rootMargin: '300px' });
    // Carica il catalogo quando si avvicinano le liste, non già nell'hero:
    // il blocco istruzioni/email può precederle di più schermate su mobile.
    observer.observe(list.closest('.scuola-grid') || section);
  } else start();
})();
