const CACHE_NAME = 'peintpro-v2';
const ASSETS = [
  '/',
  '/static/style.css',
  '/static/app.js',
  '/static/manifest.json'
];

self.addEventListener('install', (evt) => {
  evt.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (evt) => {
  evt.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (evt) => {
  if (evt.request.url.includes('/api/')) {
    evt.respondWith(fetch(evt.request).catch(() => new Response(JSON.stringify({ error: "Hors-ligne" }), { headers: { "Content-Type": "application/json" } })));
  } else {
    evt.respondWith(
      caches.match(evt.request).then((res) => res || fetch(evt.request))
    );
  }
});
