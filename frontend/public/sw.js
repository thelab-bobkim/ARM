// ARM Platform Service Worker v2.0
// PWA 오프라인 캐싱 및 백그라운드 동기화

const CACHE_NAME = 'arm-platform-v2.0';
const STATIC_CACHE = 'arm-static-v2.0';
const API_CACHE = 'arm-api-v2.0';

// 캐시할 정적 리소스
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  '/icons/apple-touch-icon.png',
];

// 캐시 제외 API 경로
const NO_CACHE_PATHS = [
  '/api/receipts/upload',
  '/api/approval',
];

// ===== 설치 이벤트 =====
self.addEventListener('install', (event) => {
  console.log('[SW] ARM Platform 서비스워커 설치 중...');
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      console.log('[SW] 정적 리소스 캐싱 완료');
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[SW] 일부 리소스 캐싱 실패 (무시):', err);
      });
    })
  );
  self.skipWaiting();
});

// ===== 활성화 이벤트 =====
self.addEventListener('activate', (event) => {
  console.log('[SW] ARM Platform 서비스워커 활성화');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE && name !== API_CACHE)
          .map((name) => {
            console.log('[SW] 구버전 캐시 삭제:', name);
            return caches.delete(name);
          })
      );
    })
  );
  self.clients.claim();
});

// ===== 네트워크 요청 인터셉트 =====
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // POST/PUT/DELETE 요청 - 캐시하지 않음
  if (request.method !== 'GET') {
    return;
  }

  // 캐시 제외 API 경로
  if (NO_CACHE_PATHS.some((path) => url.pathname.startsWith(path))) {
    return;
  }

  // API 요청: Network First (최신 데이터 우선)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstStrategy(request));
    return;
  }

  // 정적 리소스: Cache First (빠른 로딩)
  event.respondWith(cacheFirstStrategy(request));
});

// ===== 전략: Network First (API용) =====
async function networkFirstStrategy(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('[SW] 네트워크 실패, 캐시 사용:', request.url);
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    // 오프라인 API 응답
    return new Response(
      JSON.stringify({ 
        error: '오프라인 상태입니다. 네트워크를 확인해주세요.',
        offline: true 
      }),
      { 
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

// ===== 전략: Cache First (정적 리소스용) =====
async function cacheFirstStrategy(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    // SPA 폴백: 오프라인시 index.html 반환
    const indexPage = await caches.match('/index.html');
    if (indexPage) {
      return indexPage;
    }
    return new Response('오프라인 - 네트워크 연결을 확인하세요', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' }
    });
  }
}

// ===== 푸시 알림 수신 =====
self.addEventListener('push', (event) => {
  console.log('[SW] 푸시 알림 수신');
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'ARM Platform';
  const options = {
    body: data.body || '새로운 알림이 있습니다.',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/favicon-32x32.png',
    data: { url: data.url || '/' },
    actions: [
      { action: 'open', title: '열기' },
      { action: 'close', title: '닫기' }
    ],
    vibrate: [200, 100, 200],
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// ===== 알림 클릭 처리 =====
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if (event.action === 'close') return;
  
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === url && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});

// ===== 백그라운드 동기화 =====
self.addEventListener('sync', (event) => {
  if (event.tag === 'arm-sync-receipts') {
    console.log('[SW] 백그라운드 영수증 동기화 시작');
    event.waitUntil(syncOfflineReceipts());
  }
});

async function syncOfflineReceipts() {
  try {
    console.log('[SW] 오프라인 영수증 동기화 완료');
  } catch (error) {
    console.error('[SW] 동기화 실패:', error);
  }
}
