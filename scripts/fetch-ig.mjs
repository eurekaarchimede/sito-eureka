// =====================================================================
// fetch-ig.mjs — scarica TUTTI i post di @eureka.archimede via API Meta
// =====================================================================
// Eseguito da GitHub Actions ogni 3 ore (.github/workflows/ig-feed.yml).
// Cosa fa, in ordine:
//   1. legge il token Instagram (da data/token.enc, cifrato; al primo giro
//      dal secret IG_TOKEN)
//   2. lo rinnova (i token Meta scadono dopo 60 giorni: rinnovandolo a ogni
//      run non scade mai)
//   3. scarica profilo + tutti i post (paginati, 50 alla volta)
//   4. scarica le immagini nuove in assets/ig/ (gli URL diretti di Instagram
//      scadono dopo poche settimane: le copie locali no)
//   5. scrive assets/ig/feed.json — il sito legge solo questo file
//
// Env richieste:
//   ENC_KEY  — 64 caratteri hex (chiave AES per cifrare il token nel repo)
//   IG_TOKEN — token Instagram long-lived (serve solo al primo run)
//
// Niente dipendenze: solo Node >= 20.

import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const TOKEN_FILE = join(ROOT, 'data', 'token.enc');
const IMG_DIR = join(ROOT, 'assets', 'ig');
const FEED_FILE = join(ROOT, 'assets', 'ig', 'feed.json');
const GRAPH = 'https://graph.instagram.com';

const ENC_KEY = process.env.ENC_KEY || '';
const BOOTSTRAP_TOKEN = (process.env.IG_TOKEN || '').trim();

if (!/^[0-9a-f]{64}$/i.test(ENC_KEY)) {
  console.error('ENC_KEY mancante o non valida: servono 64 caratteri esadecimali.');
  process.exit(1);
}
const KEY = Buffer.from(ENC_KEY, 'hex');

// ---- cifratura token (AES-256-GCM) ----------------------------------
const encrypt = (text) => {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', KEY, iv);
  const data = Buffer.concat([cipher.update(text, 'utf8'), cipher.final()]);
  return JSON.stringify({
    iv: iv.toString('base64'),
    tag: cipher.getAuthTag().toString('base64'),
    data: data.toString('base64'),
  });
};

const decrypt = (blob) => {
  const { iv, tag, data } = JSON.parse(blob);
  const decipher = createDecipheriv('aes-256-gcm', KEY, Buffer.from(iv, 'base64'));
  decipher.setAuthTag(Buffer.from(tag, 'base64'));
  return Buffer.concat([
    decipher.update(Buffer.from(data, 'base64')),
    decipher.final(),
  ]).toString('utf8');
};

// ---- token: leggi -> rinnova -> persisti -----------------------------
let token = '';
if (existsSync(TOKEN_FILE)) {
  try {
    token = decrypt(readFileSync(TOKEN_FILE, 'utf8'));
    console.log('token letto da data/token.enc');
  } catch {
    console.warn('token.enc illeggibile (ENC_KEY cambiata?), provo col secret IG_TOKEN');
  }
}
if (!token) {
  if (!BOOTSTRAP_TOKEN) {
    console.error('Nessun token: aggiungi il secret IG_TOKEN (vedi SETUP-INSTAGRAM.md).');
    process.exit(1);
  }
  token = BOOTSTRAP_TOKEN;
  console.log('bootstrap: uso il token dal secret IG_TOKEN');
}

const getJSON = async (url) => {
  const res = await fetch(url);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = body && body.error ? body.error.message : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return body;
};

// rinnovo: se fallisce (es. token più giovane di 24h) si continua col token attuale
try {
  const r = await getJSON(`${GRAPH}/refresh_access_token?grant_type=ig_refresh_token&access_token=${token}`);
  if (r.access_token) {
    token = r.access_token;
    console.log(`token rinnovato, valido altri ${Math.round((r.expires_in || 0) / 86400)} giorni`);
  }
} catch (e) {
  console.warn(`rinnovo token non riuscito (${e.message}) — continuo con quello attuale`);
}

// persisti subito il token (anche se il fetch dei media poi fallisse)
mkdirSync(dirname(TOKEN_FILE), { recursive: true });
writeFileSync(TOKEN_FILE, encrypt(token));

// ---- profilo ----------------------------------------------------------
const profile = await getJSON(`${GRAPH}/me?fields=username,followers_count&access_token=${token}`);
console.log(`profilo: @${profile.username}, ${profile.followers_count} follower`);

// ---- tutti i post (paginati) ------------------------------------------
const FIELDS = 'id,caption,permalink,timestamp,like_count,comments_count,media_type,media_url,thumbnail_url';
let url = `${GRAPH}/me/media?fields=${FIELDS}&limit=50&access_token=${token}`;
const raw = [];
for (let page = 0; url && page < 20; page++) {
  const batch = await getJSON(url);
  raw.push(...(batch.data || []));
  url = batch.paging && batch.paging.next;
}
console.log(`post trovati: ${raw.length}`);

// ---- immagini: scarica solo le nuove -----------------------------------
mkdirSync(IMG_DIR, { recursive: true });
let downloaded = 0;
const posts = [];
for (const p of raw) {
  // per i video l'immagine è la copertina
  const src = p.media_type === 'VIDEO' ? (p.thumbnail_url || p.media_url) : p.media_url;
  if (!src) continue;

  const id = String(p.id).replace(/[^0-9a-z_-]/gi, '');
  const file = `${id}.jpg`;
  const path = join(IMG_DIR, file);

  if (!existsSync(path)) {
    try {
      const res = await fetch(src);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      writeFileSync(path, Buffer.from(await res.arrayBuffer()));
      downloaded++;
    } catch (e) {
      console.warn(`immagine ${id} non scaricata (${e.message}), post saltato`);
      continue;
    }
  }

  const caption = (p.caption || '').trim();
  posts.push({
    id,
    permalink: p.permalink,
    timestamp: p.timestamp,
    likeCount: typeof p.like_count === 'number' ? p.like_count : null,
    commentsCount: typeof p.comments_count === 'number' ? p.comments_count : null,
    mediaType: p.media_type,
    caption: caption.length > 360 ? caption.slice(0, 357) + '…' : caption,
    image: `assets/ig/${file}`,
  });
}
console.log(`immagini nuove scaricate: ${downloaded}`);

// ---- feed.json ----------------------------------------------------------
writeFileSync(FEED_FILE, JSON.stringify({
  username: profile.username,
  followersCount: profile.followers_count,
  updatedAt: new Date().toISOString(),
  posts,
}, null, 1));
console.log(`scritto ${FEED_FILE} con ${posts.length} post`);
