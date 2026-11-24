// Offline support: keeps the game, icons and voice files on the device after the first visit.
// build_site.mjs fills in the version and file list on every build, so updates download automatically.
const CACHE = "little-taps-6805cf73bf";
const FILES = ["./","manifest.webmanifest","icons/icon-180.png","icons/icon-192.png","icons/icon-512.png","icons/icon-maskable-512.png","voice/index.json","voice/v1.mp3","voice/v2.mp3","voice/v3.mp3","voice/v4.mp3","voice/v5.mp3","voice/v6.mp3","voice/v7.mp3"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k.startsWith("little-taps-") && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  // The page itself: try the network first so updates show up, fall back to the saved copy offline.
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(CACHE).then(c => c.put("./", copy)); return r; })
      .catch(() => caches.match("./")));
    return;
  }
  // Everything else (voice, icons, fonts): saved copy first.
  e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request).then(r => {
    if (r.ok || r.type === "opaque") { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); }
    return r;
  })));
  void url;
});
