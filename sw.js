self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
    const client = list.find((item) => /localhost|127\.0\.0\.1/.test(item.url)) || list[0];
    if (client) {
      client.postMessage({ type: "open-note", data });
      return client.focus();
    }
    const tag = encodeURIComponent(data.tag || "");
    return self.clients.openWindow("/?note=" + tag);
  }));
});
