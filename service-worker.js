const CACHE_NAME="halifax-pwa-v14-2-0";
const CORE=["./","./index.html","./screener.html","./manifest.webmanifest","./offline.html","./icons/icon-192.png","./icons/icon-512.png","./icons/apple-touch-icon.png","./icons/favicon-48.png"];
self.addEventListener("install",event=>{event.waitUntil(caches.open(CACHE_NAME).then(c=>c.addAll(CORE)).catch(()=>{}));self.skipWaiting();});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE_NAME).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener("message",event=>{if(event.data?.type==="SKIP_WAITING")self.skipWaiting();});
async function networkFirst(req,fallback){
  const cache=await caches.open(CACHE_NAME);
  try{const fresh=await fetch(req);if(fresh&&fresh.ok)cache.put(req,fresh.clone());return fresh;}catch(e){return (await cache.match(req))||(fallback?await cache.match(fallback):Response.error());}
}
self.addEventListener("fetch",event=>{
  const req=event.request;if(req.method!=="GET")return;const url=new URL(req.url);if(url.origin!==self.location.origin)return;
  if(url.pathname.endsWith("/screener-data.json")){event.respondWith(networkFirst(req));return;}
  if(req.mode==="navigate"){event.respondWith(networkFirst(req,"./offline.html"));return;}
  event.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(r=>{if(r&&r.ok){const copy=r.clone();caches.open(CACHE_NAME).then(c=>c.put(req,copy));}return r;})));
});
