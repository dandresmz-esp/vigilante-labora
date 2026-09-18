import test from 'node:test';
import assert from 'node:assert/strict';
import {allowed,handle} from './worker.mjs';
const target='https://labora.gva.es/documents/d/labora/calendario';
const req=(url=target,token='test-secret') => new Request('https://example.workers.dev/?url='+encodeURIComponent(url),{headers:{Authorization:'Bearer '+token}});
test('only official public paths',()=>{
  assert.equal(allowed(target),true);
  for(const u of ['https://example.com/documents/test','http://labora.gva.es/documents/test','https://labora.gva.es/admin','https://user:password@labora.gva.es/documents/test'])assert.equal(allowed(u),false);
});
test('authentication before any fetch',async()=>{
  const r=await handle(req(target,'wrong'),{RELAY_TOKEN:'test-secret'},()=>assert.fail('unexpected fetch'));
  assert.equal(r.status,401);
});
test('preserves PDF bytes and validator',async()=>{
  const r=await handle(req(),{RELAY_TOKEN:'test-secret'},async(u,options)=>{
    assert.equal(options.headers.has('Authorization'),false);
    return new Response('%PDF-original',{headers:{'Content-Type':'application/pdf',ETag:'original'}});
  });
  assert.equal(await r.text(),'%PDF-original');assert.equal(r.headers.get('ETag'),'original');
});
test('does not follow off-site redirects',async()=>{
  const r=await handle(req(),{RELAY_TOKEN:'test-secret'},async()=>new Response(null,{status:302,headers:{Location:'https://example.com/private'}}));
  assert.equal(r.status,502);
});
test('upstream outage remains an error',async()=>{
  const r=await handle(req(),{RELAY_TOKEN:'test-secret'},async()=>{throw Error('timeout')});
  assert.equal(r.status,502);
});
