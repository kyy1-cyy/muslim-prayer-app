// static/sw.js
self.addEventListener("push", (event) => {
  const payload = event.data ? event.data.json() : {};
  const title = payload.notification.title || "Prayer App";
  const options = {
    body: payload.notification.body || "A new notification.",
    icon: "/static/path-to-your-icon.png", // Make sure to add a small icon file
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(self.location.origin));
});
