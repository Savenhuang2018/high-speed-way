// Service Worker - 高速服务区 PWA
const CACHE_NAME = 'service-area-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/admin',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png',
];

// 安装：预缓存静态资源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {});
    })
  );
  self.skipWaiting();
});

// 激活：清理旧缓存
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) => {
      return Promise.all(
        names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))
      );
    })
  );
  self.clients.claim();
});

// 请求拦截：API 请求走网络，静态资源缓存优先
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API 请求不缓存，直接走网络
  if (url.pathname.startsWith('/health') ||
      url.pathname.startsWith('/service-areas') ||
      url.pathname.startsWith('/merchants') ||
      url.pathname.startsWith('/reviews') ||
      url.pathname.startsWith('/coupons') ||
      url.pathname.startsWith('/users') ||
      url.pathname.startsWith('/favorites') ||
      url.pathname.startsWith('/stats') ||
      url.pathname.startsWith('/route')) {
    return; // 让浏览器正常处理
  }

  // 静态资源：缓存优先，网络回退
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request).then((response) => {
        // 缓存新获取的资源
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => cached);
    })
  );
});
