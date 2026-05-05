const CACHE_NAME = 'softcom-energy-v6';
const urlsToCache = [
    '/',
    '/static/core/img/icon-512.png'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
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
        title: 'Notificación del Sistema',
        body: 'Nueva actualización disponible',
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
        badge: data.badge || '/static/core/img/icon-512.png',
        vibrate: [100, 50, 100],
        data: {
            url: data.url
        }
    };

    event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    if (event.notification.data && event.notification.data.url) {
        event.waitUntil(clients.openWindow(event.notification.data.url));
    }
});
