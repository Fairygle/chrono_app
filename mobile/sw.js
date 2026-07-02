// ChronoApp — hors-ligne. Stratégie "réseau d'abord" pour la page,
// pour que les mises à jour soient prises immédiatement.
// Les données restent dans localStorage (jamais touché ici).
const CACHE = "chronoapp-v3";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-maskable.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const isPage = e.request.mode === "navigate" ||
                 e.request.destination === "document" ||
                 e.request.url.endsWith("index.html");
  if (isPage) {
    // Réseau d'abord ; cache seulement si hors-ligne
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return res;
        })
        .catch(() => caches.match(e.request).then((h) => h || caches.match("./index.html")))
    );
  } else {
    // Icônes/manifest : cache d'abord (change rarement)
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request))
    );
  }
});
