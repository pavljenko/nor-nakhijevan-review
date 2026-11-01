const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const context=vm.createContext({setTimeout,clearTimeout,AbortController});
vm.runInContext(fs.readFileSync('src/save-queue.js','utf8')+';globalThis.Outbox=DrawingOutbox',context);
const Outbox=context.Outbox;
class Storage {
 constructor(){this.data=new Map()}
 get length(){return this.data.size} key(i){return [...this.data.keys()][i]}
 getItem(k){return this.data.get(k)??null} setItem(k,v){this.data.set(k,v)} removeItem(k){this.data.delete(k)}
}
const draft=(revision=1,session='old-session')=>({session,glyph:'U0531',revision,strokes:[{points:[[revision,200]],width:7,color:'#d63842'}],note:''});
const receipt={accepted:true,id:'confirmed'};
(async()=>{
 // Lost connection leaves the drawing durable. Reload recovers it for retry,
 // independently of the fresh canvas/session constructed by the page.
 const storage=new Storage(),states=[];
 let calls=0;
 const first=new Outbox({storage,delay:1e6,onState:s=>states.push(s),send:async()=>{calls++;throw Error('offline')}});
 first.put(draft());await first.flush();clearTimeout(first.timer);
 assert.equal(storage.length,1);assert.equal(calls,1);assert.ok(states.at(-1).error);
 const recovered=[];
 const second=new Outbox({storage,delay:1e6,send:async raw=>{recovered.push(JSON.parse(raw));return receipt}});
 second.put(draft(1,'fresh-session'));await second.flush();
 assert.equal(recovered.length,2);assert.equal(recovered[0].session,'old-session');assert.equal(storage.length,0);
 // Editing during a slow request must not be discarded by its older receipt.
 let release;const sent=[];
 const third=new Outbox({storage,delay:1e6,send:raw=>{sent.push(JSON.parse(raw));return sent.length===1?new Promise(r=>release=r):Promise.resolve(receipt)}});
 third.put(draft());const running=third.flush();third.put(draft(2));third.put(draft(3));release(receipt);await running;clearTimeout(third.timer);
 assert.deepEqual(sent.map(d=>d.revision),[1,3]);assert.equal(storage.length,0);assert.equal(third.items.size,0);
 // Double tap sends a single request. A hung request times out and stays queued.
 let resolve;let count=0;
 const fourth=new Outbox({storage,delay:1e6,send:()=>{count++;return new Promise(r=>resolve=r)}});
 fourth.put(draft());const a=fourth.flush(),b=fourth.flush();assert.equal(a,b);resolve(receipt);await a;assert.equal(count,1);
 let signal;
 const hung=new Outbox({storage,delay:1e6,timeout:20,send:(_,s)=>{signal=s;return new Promise(()=>{})}});
 hung.put(draft());await hung.flush();clearTimeout(hung.timer);assert.ok(signal.aborted);assert.equal(storage.length,1);
 // Quota/disabled storage still sends from memory, while reporting no backup.
 const broken={get length(){throw Error('blocked')},setItem(){throw Error('quota')},getItem(){throw Error('blocked')}};
 const fallback=new Outbox({storage:broken,delay:1e6,send:async()=>receipt});fallback.put(draft());assert.ok(fallback.storageFailed);await fallback.flush();assert.equal(fallback.items.size,0);
 // Automatic retry works without another button click.
 let n=0;const retry=new Outbox({storage:new Storage(),delay:1e6,send:async()=>{if(!n++)throw Error('offline');return receipt}});
 retry.put(draft());await retry.flush();await new Promise(r=>setTimeout(r,1100));assert.equal(n,2);assert.equal(retry.items.size,0);
 console.log('Passed: durable reload recovery, offline retry, timeout, quota fallback, newest revision, concurrent edits, double tap');
})().catch(e=>{console.error(e);process.exitCode=1});
