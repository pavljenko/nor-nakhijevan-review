import json,tempfile,uuid,threading,http.client
from pathlib import Path
import server as s
s.DATA=Path(tempfile.mkdtemp());s.GITDIR=s.DATA/'git';s.TOKEN='shared-test-key';s.OWNER_TOKEN='private-test-owner';s.init()
d={'session':str(uuid.uuid4()),'glyph':'U0531','strokes':[{'color':'#d63842','width':7,'points':[[100,200]]}],'note':'test'}
ident=s.save_record(d)
class Git(s.GitArchive):
 def run(self,*a):
  if a[0]=='clone':(s.GITDIR/'.git').mkdir(parents=True)
  return 'changed' if a[:2]==('status','--porcelain') else ''
g=Git();g.publish(s.validate(d),ident)
http=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
def req(method,path,headers,body=None):
 c=__import__('http.client',fromlist=['HTTPConnection']).HTTPConnection('127.0.0.1',http.server_port)
 c.request(method,'/nor-nakhijevan/api/'+path,body=json.dumps(body) if body else None,headers=headers);r=c.getresponse();data=json.loads(r.read());c.close();return r.status,data
assert req('GET','owner',{})[0]==403
assert req('GET','owner',{'X-Review-Key':s.TOKEN})[0]==403
assert req('GET','owner',{'X-Owner-Key':'wrong'})[0]==403
assert req('GET','owner',{'X-Owner-Key':s.OWNER_TOKEN})[1]['owner']
for h in ({},{'X-Review-Key':s.TOKEN},{'X-Owner-Key':'wrong'}):assert req('POST','delete',h,d)[0]==403
assert req('POST','delete',{'X-Owner-Key':s.OWNER_TOKEN},d)[0]==202
assert s.gallery_index()==[]
assert s.delete_one(g)
assert not list((s.GITDIR/'submissions'/d['session']).glob('*'))
with s.database() as db:
 assert db.execute('select status from deleted_groups').fetchone()[0]=='done'
 assert db.execute('select status from drawings').fetchone()[0]=='deleted'
assert not s.upload_one(g)
try:s.save_record(d)
except ValueError:pass
else:raise AssertionError('deleted revision resurrected')
http.shutdown();print('Passed: owner-only HTTP auth, shared-key denial, complete group deletion, no resurrection')
