import json,tempfile,threading,http.client,copy
from pathlib import Path
import server as s
s.DATA=Path(tempfile.mkdtemp());s.TOKEN='motion-shared-test';s.OWNER_TOKEN='motion-owner-test';s.init()
data={'schema':1,'glyph':'U0531','viewBox':[0,0,max(1000,s.GLYPHS['U0531']['advance']+200),1100],'duration':1200,'strokes':[{'points':[[100,200,0],[200,200,400]]},{'points':[[200,300,700],[400,400,1200]]}]}
ident=s.save_motion(data);assert s.save_motion(data)==ident
assert json.loads((s.DATA/'motions'/(ident+'.json')).read_text())==data
s.init()
with s.database() as c:assert c.execute('SELECT count(*) FROM motions').fetchone()[0]==1
for bad in [dict(data,duration=-1),dict(data,viewBox=[0,0,1,1]),dict(data,glyph='bad'),dict(data,duration=1201),dict(data,strokes=[{'points':[[1,2,0],[1,2,-1]]}]),dict(data,strokes=[{'points':[[1,2,1],[1,2,1200]]}]),dict(data,strokes=[{'points':[[float('nan'),2,0],[1,2,1200]]}])]:
 try:s.validate_motion(bad)
 except ValueError:pass
 else:raise AssertionError('Invalid motion accepted')
http=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
def request(method,url,headers={},body=None):
 c=__import__('http.client',fromlist=['HTTPConnection']).HTTPConnection('127.0.0.1',http.server_port,timeout=3)
 c.request(method,'/nor-nakhijevan/api/'+url,body=json.dumps(body) if body else None,headers=headers);r=c.getresponse();raw=r.read();status=r.status;c.close();return status,json.loads(raw)
for headers in ({},{'X-Review-Key':s.TOKEN},{'X-Owner-Key':'wrong'}):
 for url in ('motions','motions/'+ident):assert request('GET',url,headers)[0]==403
 assert request('POST','motions',headers,data)[0]==403
owner={'X-Owner-Key':s.OWNER_TOKEN}
assert request('GET','motions',owner)[1]['records'][0]['id']==ident
assert request('GET','motions/'+ident,owner)[1]==data
assert request('POST','motions',owner,data)[1]['durable']
assert request('POST','motions',{**owner,'Origin':'https://example.org'},data)[0]==403
assert request('GET','gallery')[1]['records']==[]
http.shutdown();print('Passed: private motion storage, durable JSON, timing validation and gallery isolation')
