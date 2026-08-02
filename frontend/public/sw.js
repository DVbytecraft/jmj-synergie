self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((key) => key.startsWith("jmj-synergie"))
          .map((key) => caches.delete(key))
      );

      const registrations = await self.registration.unregister();
      await self.clients.claim();

      const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      clients.forEach((client) => {
        client.navigate(client.url);
      });

      return registrations;
    })()
  );
});
