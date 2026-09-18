// Read-only relay: official LABORA sources only; never an arbitrary URL proxy.
export function allowed(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && u.hostname === 'labora.gva.es' &&
      !u.username && !u.password && (!u.port || u.port === '443') &&
      (u.pathname.startsWith('/documents/') ||
       u.pathname.startsWith('/es/programes-mixtos-d-ocupacio/') ||
       u.pathname === '/es/tallers-d-ocupacio-per-a-dones');
  } catch { return false; }
}

export async function handle(request, env, fetcher) {
  if (!env.RELAY_TOKEN) return new Response('Relay not configured', {status:503});
  if (request.headers.get('Authorization') !== `Bearer ${env.RELAY_TOKEN}`)
    return new Response('Unauthorized', {status:401});
  if (request.method !== 'GET') return new Response('GET only', {status:405});
  let target = new URL(request.url).searchParams.get('url');
  if (!allowed(target)) return new Response('Official LABORA source required', {status:400});
  const headers = new Headers({'User-Agent':'Mozilla/5.0 (compatible; VigilanteProgramasEmpleo/1.0)'});
  for (const name of ['Accept','If-None-Match','If-Modified-Since']) {
    if (request.headers.has(name)) headers.set(name,request.headers.get(name));
  }
  try {
    for (let redirects=0;redirects<4;redirects++) {
      const upstream=await fetcher(target,{headers,redirect:'manual',signal:AbortSignal.timeout(20000),cf:{cacheTtl:0}});
      if ([301,302,303,307,308].includes(upstream.status)) {
        const location=upstream.headers.get('Location');
        if (!location) return new Response('Invalid upstream redirect',{status:502});
        target=new URL(location,target).href;
        if (!allowed(target)) return new Response('Unexpected upstream destination',{status:502});
        continue;
      }
      const resultHeaders=new Headers({'Cache-Control':'no-store','X-Source-URL':target});
      for (const name of ['Content-Type','ETag','Last-Modified']) {
        if (upstream.headers.has(name)) resultHeaders.set(name,upstream.headers.get(name));
      }
      return new Response(upstream.body,{status:upstream.status,headers:resultHeaders});
    }
    return new Response('Too many upstream redirects',{status:502});
  } catch { return new Response('LABORA fetch failed',{status:502}); }
}
export default {fetch(request,env) {return handle(request,env,fetch);}};
