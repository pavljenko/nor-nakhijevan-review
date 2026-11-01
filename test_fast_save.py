import json,tempfile,uuid,threading,http.client,time
from pathlib import Path
import server as s
s.DATA=Path(tempfile.mkdtemp());s.TOKEN='test-save-key';s.init()
http=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler)
threading.Thread(target=http.serve_forever,daemon=True).start()
def req(method,path,body=None):
 c=__import__('http.client',fromlist=['HTTPConnection']).HTTPConnection('127.0.0.1',http.server_port,timeout=2)
 c.request(method,'/nor-nakhijevan/api/'+path,body=json.dumps(body) if body else None,headers={'X-Review-Key':s.TOKEN,'Content-Type':'application/json'})
 r=c.getresponse();data=r.read();code=r.status;c.close();return code,data
d={'session':str(uuid.uuid4()),'glyph':'U0531','revision':1,'strokes':[{'color':'#d63842','width':7,'points':[[100,200],[120,230]]}],'note':'test-fast-save'}
start=time.monotonic();code,body=req('POST','review',d);elapsed=time.monotonic()-start
receipt=json.loads(body);assert code==202 and receipt['durable'] and elapsed<1
ident=receipt['id']
assert json.loads(req('POST','review',d)[1])['id']==ident
# No GitHub uploader is running: gallery and exact SVG/JSON work immediately.
assert ident in [r['id'] for r in json.loads(req('GET','gallery')[1])['records']]
assert req('GET','sketch/'+ident+'.svg')[0]==200
assert json.loads(req('GET','sketch/'+ident+'.json')[1])['revision']==1
s.init() # Restart/migration preserves queued drawings and idempotency.
assert json.loads(req('POST','review',d)[1])['id']==ident
new={**d,'revision':3,'strokes':[{'color':'#d63842','width':7,'points':[[300,400]]}]}
latest=json.loads(req('POST','review',new)[1])['id'];assert latest!=ident
assert json.loads(req('POST','review',{**d,'revision':2})[1])['id']==latest
with s.database() as db:
 assert db.execute('SELECT count(*) FROM drawings').fetchone()[0]==2
 assert db.execute('PRAGMA journal_mode').fetchone()[0]=='wal'
 assert db.execute('PRAGMA synchronous').fetchone()[0]==2
s.request_delete(d['session'],d['glyph'])
assert req('GET','sketch/'+latest+'.svg')[0]==404
assert not json.loads(req('GET','gallery')[1])['records']
assert req('POST','review',new)[0]==400
http.shutdown();print(f'Passed: durable ack {elapsed:.3f}s without GitHub, immediate gallery/files, restart, duplicate/stale revision, deletion')
