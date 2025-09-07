// static/script.js

// Check for Service Worker support and register it
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(reg => {
                console.log('Service Worker registered with scope:', reg.scope);
            })
            .catch(err => {
                console.error('Service Worker registration failed:', err);
            });
    });
}

// Find the button and add a click listener
const notificationBtn = document.getElementById('notification-btn');

if (notificationBtn) {
    notificationBtn.addEventListener('click', () => {
        if ('Notification' in window && 'PushManager' in window) {
            // Check if permission is already granted
            if (Notification.permission === 'granted') {
                console.log('Notification permission already granted.');
                subscribeUserToPush();
            } else if (Notification.permission !== 'denied') {
                // Request permission from the user
                Notification.requestPermission().then(permission => {
                    if (permission === 'granted') {
                        console.log('Notification permission granted.');
                        subscribeUserToPush();
                    } else {
                        console.log('Notification permission denied.');
                    }
                });
            } else {
                console.log('Notification permission denied by the user. Please change settings.');
            }
        }
    });
}

function subscribeUserToPush() {
    // We moved this function outside the event listener
    if ('PushManager' in window) {
        navigator.serviceWorker.ready.then(registration => {
            registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
            }).then(subscription => {
                console.log('User is subscribed:', subscription);
                sendSubscriptionToBackend(subscription);
            }).catch(err => {
                console.error('Failed to subscribe the user:', err);
            });
        });
    }
}

function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, "+")
        .replace(/_/g, "/");
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

function sendSubscriptionToBackend(subscription) {
    fetch("/push_subscribe", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(subscription),
    })
    .then(response => response.json())
    .then(data => {
        console.log("Subscription sent to backend:", data);
    })
    .catch(error => {
        console.error("Error sending subscription to backend:", error);
    });
}
