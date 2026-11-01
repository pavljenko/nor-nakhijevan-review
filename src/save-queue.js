// Durable browser outbox. A fresh canvas never discards undelivered sessions.
class DrawingOutbox {
  constructor({storage,send,onState=()=>{},delay=300,timeout=8000}) {
    Object.assign(this,{storage,send,onState,delay,timeout});
    this.prefix='nor-review-outbox-v1:';this.items=new Map();this.timer=null;
    this.running=null;this.failures=0;this.error='';this.storageFailed=false;
    this.readStorage();
  }
  readStorage() {
    try {
      for(let i=0;i<this.storage.length;i++) {
        const k=this.storage.key(i);if(!k?.startsWith(this.prefix))continue;
        try {
          const raw=this.storage.getItem(k),d=JSON.parse(raw);
          if(d.session&&d.glyph&&Array.isArray(d.strokes)&&Number.isInteger(d.revision)) {
            const old=this.items.get(k);
            if(!old||JSON.parse(old).revision<d.revision)this.items.set(k,raw);
          }
        } catch {}
      }
    } catch {this.storageFailed=true;}
  }
  put(d,delay=this.delay) {
    const k=this.prefix+d.session+'/'+d.glyph,raw=JSON.stringify(d);
    this.items.set(k,raw);
    try {this.storage.setItem(k,raw);this.storageFailed=false;}catch{this.storageFailed=true;}
    this.error='';this.emit();this.schedule(delay);
  }
  emit(){this.onState({pending:this.items.size,saving:!!this.running,error:this.error,storageFailed:this.storageFailed});}
  schedule(ms){clearTimeout(this.timer);this.timer=setTimeout(()=>this.flush(),ms);}
  flush() {
    clearTimeout(this.timer);
    if(this.running)return this.running;
    this.readStorage();
    this.running=this.drain().finally(()=>{this.running=null;this.emit();});
    this.emit();return this.running;
  }
  async drain() {
    for(const [k] of this.items) {
      while(this.items.has(k)) {
        // Snapshot at send time, not at enqueue time: don't send stale strokes.
        const raw=this.items.get(k),controller=new AbortController();
        let deadline;
        try {
          const response=await Promise.race([
            this.send(raw,controller.signal),
            new Promise((_,reject)=>{deadline=setTimeout(()=>{controller.abort();reject(Error('timeout'));},this.timeout);})
          ]);
          if(!response?.accepted||!response.id)throw Error('receipt');
          if(this.items.get(k)===raw)this.items.delete(k);
          try {if(this.storage.getItem(k)===raw)this.storage.removeItem(k);}catch{this.storageFailed=true;}
          this.failures=0;this.error='';this.emit();
        } catch(e) {
          this.error=e.permanent?'Не удалось принять рисунок. Повторите сохранение или скачайте копию.':'Нет подтверждения сервера. Повторим автоматически.';
          this.failures++;this.schedule(e.permanent?30000:Math.min(30000,1000*2**Math.min(this.failures-1,5)));
          return;
        } finally {clearTimeout(deadline);}
      }
    }
  }
}
