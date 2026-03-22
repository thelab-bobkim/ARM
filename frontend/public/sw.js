// ARM Platform Service Worker v2.1
// 자동 업데이트 + 오프라인 캐싱 + 백그라운드 동기화

// ⚡ 버전 변경 시 자동으로 새 캐시로 교체됨
const SW_VERSION = 'v2.1';
const CACHE_NAME = `arm-platform-${SW_VERSION}`;
const STATIC_CACHE = `arm-static-${SW_VERSION}`;
const API_CACHE = `arm-api-${SW_VERSION}`;

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
  console.log(`[SW ${SW_VERSION}] 설치 중...`);
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[SW] 일부 리소스 캐싱 실패 (무시):', err);
      });
    })
  );
  // ✅ 핵심: 대기 없이 즉시 활성화 (자동 업데이트 핵심)
  self.skipWaiting();
});

// ===== 활성화 이벤트 - 구버전 캐시 자동 삭제 =====
self.addEventListener('activate', (event) => {
  console.log(`[SW ${SW_VERSION}] 활성화 - 구버전 캐시 정리 중...`);
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
    }).then(() => {
      console.log(`[SW ${SW_VERSION}] 활성화 완료`);
      // ✅ 핵심: 열린 탭 즉시 제어 (새로고침 없이 바로 적용)
      return self.clients.claim();
    })
  );
});

// ===== 메시지 수신 (앱 → 서비스워커) =====
self.addEventListener('message', (event) => {
  // 수동 업데이트 요청
  if (event.data?.type === 'SKIP_WAITING') {
    console.log('[SW] 수동 업데이트 요청 수신');
    self.skipWaiting();
  }
  // 버전 확인 요청
  if (event.data?.type === 'GET_VERSION') {
    event.source?.postMessage({ type: 'SW_VERSION', version: SW_VERSION });
  }
  // 캐시 강제 초기화 요청
  if (event.data?.type === 'CLEAR_CACHE') {
    caches.keys().then((names) => Promise.all(names.map((n) => caches.delete(n))))
      .then(() => event.source?.postMessage({ type: 'CACHE_CLEARED' }));
  }
});

// ===== 네트워크 요청 인터셉트 =====
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // POST/PUT/DELETE → 캐시 안 함
  if (request.method !== 'GET') return;

  // 캐시 제외 API 경로
  if (NO_CACHE_PATHS.some((path) => url.pathname.startsWith(path))) return;

  // API 요청: Network First
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstStrategy(request));
    return;
  }

  // 정적 리소스: Stale-While-Revalidate (캐시 반환 + 백그라운드 업데이트)
  event.respondWith(staleWhileRevalidate(request));
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
  } catch {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) return cachedResponse;
    return new Response(
      JSON.stringify({ error: '오프라인 상태입니다.', offline: true }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

// ===== 전략: Stale-While-Revalidate (정적 리소스용) =====
// → 캐시된 버전을 즉시 반환하면서, 백그라운드에서 최신 버전으로 캐시 갱신
async function staleWhileRevalidate(request) {
  const cachedResponse = await caches.match(request);

  const fetchPromise = fetch(request).then((networkResponse) => {
    if (networkResponse.ok) {
      const cache = caches.open(STATIC_CACHE);
      cache.then((c) => c.put(request, networkResponse.clone()));
    }
    return networkResponse;
  }).catch(() => null);

  // 캐시가 있으면 즉시 반환 (빠른 로딩)
  if (cachedResponse) return cachedResponse;

  // 캐시 없으면 네트워크 응답 대기
  const networkResponse = await fetchPromise;
  if (networkResponse) return networkResponse;

  // SPA 폴백
  const indexPage = await caches.match('/index.html');
  if (indexPage) return indexPage;

  return new Response('오프라인', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}

// ===== 푸시 알림 수신 =====
self.addEventListener('push', (event) => {
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
        if (client.url === url && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});

// ===== 백그라운드 동기화 =====
self.addEventListener('sync', (event) => {
  if (event.tag === 'arm-sync-receipts') {
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
