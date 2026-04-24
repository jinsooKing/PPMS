/**
 * PPMS Service Worker
 * 전략: Network-First
 *   - API 호출은 항상 서버 우선 (데이터 정합성)
 *   - 정적 자산(폰트, 아이콘)은 Cache-First (빠른 로딩)
 *   - 오프라인 시 Fallback 페이지 표시
 */

const CACHE_NAME      = 'ppms-v1';
const STATIC_CACHE    = 'ppms-static-v1';

/* 앱 시작 시 미리 캐시할 정적 자산 */
const PRE_CACHE_ASSETS = [
  '/static/pwa/icon-192.png',
  '/static/pwa/icon-512.png',
  '/static/pwa/apple-touch-icon.png',
  '/static/manifest.json',
  '/offline',
];

/* 항상 네트워크로 가야 하는 경로 패턴 */
const NETWORK_ONLY_PATTERNS = [
  /^\/api\//,           // API 호출 전부
  /^\/api\/auth\//,     // 인증
];

/* 캐시해도 되는 외부 정적 자산 패턴 */
const CACHEABLE_ORIGINS = [
  'hangeul.pstatic.net',
  'fonts.googleapis.com',
  'fonts.gstatic.com',
  'unicons.iconscout.com',
  'cdnjs.cloudflare.com',
  's3-us-west-2.amazonaws.com',
];

/* ── Install ── */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(PRE_CACHE_ASSETS).catch(() => {
        /* 일부 자산 캐시 실패해도 설치 중단 안 함 */
      });
    })
  );
  self.skipWaiting();
});

/* ── Activate ── */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME && k !== STATIC_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

/* ── Fetch ── */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  /* 1. GET 이외 요청(POST, PUT, DELETE)은 항상 네트워크 */
  if (request.method !== 'GET') return;

  /* 2. API 경로 — Network Only */
  if (NETWORK_ONLY_PATTERNS.some((p) => p.test(url.pathname))) {
    event.respondWith(
      fetch(request).catch(() => offlineFallback(request))
    );
    return;
  }

  /* 3. 외부 정적 자산 — Cache First */
  if (CACHEABLE_ORIGINS.some((o) => url.hostname.includes(o))) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((res) => {
          if (res && res.status === 200) {
            const resClone = res.clone();
            caches.open(STATIC_CACHE).then((c) => c.put(request, resClone));
          }
          return res;
        });
      })
    );
    return;
  }

  /* 4. 내부 페이지/자산 — Network First, 실패 시 Cache */
  event.respondWith(
    fetch(request)
      .then((res) => {
        /* 성공 시 캐시 업데이트 */
        if (res && res.status === 200 && res.type !== 'opaque') {
          const resClone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(request, resClone));
        }
        return res;
      })
      .catch(() => {
        /* 네트워크 실패 → 캐시 → 오프라인 페이지 */
        return caches.match(request).then((cached) => {
          return cached || offlineFallback(request);
        });
      })
  );
});

/* ── 오프라인 Fallback ── */
function offlineFallback(request) {
  const url = new URL(request.url);
  /* HTML 요청이면 오프라인 페이지, 그 외 빈 응답 */
  if (request.headers.get('accept')?.includes('text/html')) {
    return caches.match('/offline') || new Response(
      `<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>PPMS — 오프라인</title>
  <style>
    body{margin:0;background:#1f2029;color:#c4c3ca;font-family:'Poppins',sans-serif;
         display:flex;flex-direction:column;align-items:center;justify-content:center;
         height:100vh;gap:16px;text-align:center;padding:0 24px;}
    .icon{font-size:3rem;opacity:.4}
    h1{color:#ffeba7;font-size:1.2rem;margin:0}
    p{font-size:.85rem;opacity:.6;max-width:280px;line-height:1.6}
    button{margin-top:8px;padding:12px 28px;background:#ffeba7;color:#102770;
           border:none;border-radius:10px;font-size:.9rem;font-weight:700;cursor:pointer}
  </style>
</head>
<body>
  <div class="icon">📡</div>
  <h1>서버에 연결할 수 없습니다</h1>
  <p>PPMS는 서버 연결이 필요합니다.<br>네트워크 상태를 확인한 뒤 다시 시도해 주세요.</p>
  <button onclick="location.reload()">다시 시도</button>
</body>
</html>`,
      { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
  return new Response('', { status: 503 });
}
