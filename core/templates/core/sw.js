const CACHE_NAME = 'softcom-energy-v7';
const urlsToCache = [
    '/',
    '/static/core/img/icon-512.png'
];

self.addEventListener('install', event => {
    self.skipWaiting(); // Forzar actualización inmediata
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[Service Worker] Borrando caché vieja:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('[Service Worker] Activado y listo.');
            return clients.claim();
        })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    return response;
                }
                return fetch(event.request);
            })
    );
});

// Soporte para Web Push Notifications
self.addEventListener('push', function(event) {
    console.log('[Service Worker] Push recibido', event);
    
    let data = {
        title: 'Notificación de Energía',
        body: 'Nueva actualización en el sistema',
        icon: '/static/core/img/icon-512.png',
        url: '/'
    };

    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            console.warn('[Service Worker] Datos de Push no son JSON:', event.data.text());
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: data.icon || '/static/core/img/icon-512.png',
        badge: '/static/core/img/icon-512.png',
        vibrate: [300, 100, 400],
        tag: 'energy-notification-tag', // Evita duplicados pero asegura que suene
        renotify: true, // Obliga a notificar aunque el tag sea el mismo
        requireInteraction: true, // La notificación no desaparece hasta que se interactúa (útil en móviles)
        data: {
            url: data.url
        }
    };

    event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            const url = event.notification.data.url || '/';
            // Si ya hay una ventana abierta con la app, enfocarla
            for (let i = 0; i < clientList.length; i++) {
                let client = clientList[i];
                if (client.url.includes(url) && 'focus' in client) {
                    return client.focus();
                }
            }
            // Si no, abrir una nueva
            if (clients.openWindow) {
                return clients.openWindow(url);
            }
        })
    );
});
