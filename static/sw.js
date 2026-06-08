self.addEventListener('install', e => e.waitUntil(caches.open('nongafo-v1').then(c => c.addAll(['/']))));
self.addEventListener('fetch', e => e.respondWith(fetch(e.request).catch(() => caches.match(e.request))));

self.addEventListener('push', e => {
  let data = { titre: 'Nongafo', corps: 'Nouveau message !', url: '/' };
  try { data = Object.assign(data, e.data.json()); } catch(_) {}
  e.waitUntil(
    self.registration.showNotification(data.titre, {
      body: data.corps,
      icon: 'https://img.icons8.com/fluency/192/heart.png',
      badge: 'https://img.icons8.com/fluency/96/heart.png',
      data: { url: data.url }
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data.url || '/'));
});
