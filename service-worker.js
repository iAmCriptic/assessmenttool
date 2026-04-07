const CACHE_NAME = 'bewertung-app-cache-v1';
const urlsToCache = [
    './',
    './login',
    './static_files/manifest.json',
    './static_files/img/logo.svg',
    './service-worker.js',
    // Weitere statische Assets, die Sie cachen möchten, z.B.
    // './static_files/images/background.jpg',
    // './static_files/js/main.js',
    // Fügen Sie hier alle wichtigen HTML-Dateien hinzu, wenn Sie sie offline verfügbar machen möchten,
    // aber seien Sie vorsichtig mit dynamischen Inhalten.
    // Für die PWA-Installierbarkeit ist es wichtiger, dass die Start-URL und Icons gecached werden können.
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('Opened cache');
                return cache.addAll(urlsToCache);
            })
            .catch(error => {
                console.error('Failed to cache during install:', error);
            })
    );
});

self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                // Cache Hit - return response
                if (response) {
                    return response;
                }
                return fetch(event.request);
            })
    );
});

self.addEventListener('activate', (event) => {
    const cacheAllowlist = [CACHE_NAME];
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheAllowlist.indexOf(cacheName) === -1) {
                        // Delete old caches
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});