# coding: utf-8
"""Dedicated drawing collector. Credentials stay server-side; no font masters changed."""
import os,json,re,math,time,uuid,hashlib,sqlite3,threading,urllib.parse,html,subprocess
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('REVIEW_DATA',str(ROOT/'data')))
REPO='pavljenko/nor-nakhijevan-review'
GITDIR=DATA/'git'
KEY=DATA/'deploy_key'
TOKEN=os.environ.get('REVIEW_TOKEN','')
GLYPHS=json.loads((ROOT/'glyphs.json').read_text())
GLYPHS={g['id']:g for p in GLYPHS['pairs'] for g in [p['upper'],p['lower']]}
LOCK=threading.Lock()
def database():
 c=sqlite3.connect(DATA/'archive.sqlite',timeout=30);c.row_factory=sqlite3.Row;return c
def init():
 DATA.mkdir(parents=True,exist_ok=True)
 with database() as c:
  c.execute('CREATE TABLE IF NOT EXISTS drawings (id TEXT PRIMARY KEY, session TEXT, glyph TEXT, body TEXT, status TEXT, svg_url TEXT, json_url TEXT, attempts INTEGER DEFAULT 0, next_try REAL DEFAULT 0, created REAL)')
def validate(d):
 if d.get('glyph') not in GLYPHS:raise ValueError('glyph')
 if not re.fullmatch(r'[a-f0-9-]{36}',d.get('session','')):raise ValueError('session')
 strokes=d.get('strokes');note=d.get('note')
 if not isinstance(strokes,list) or len(strokes)>600 or not isinstance(note,str) or len(note)>4000:raise ValueError('size')
 count=0;out=[]
 for s in strokes:
  pts=s.get('points');width=s.get('width');color=s.get('color')
  if color not in ('#d63842','#08084d') or not isinstance(width,(float,int)) or not 2<=width<=25:raise ValueError('stroke')
  if not isinstance(pts,list) or not 1<=len(pts)<=12000:raise ValueError('points')
  count+=len(pts)
  if count>100000:raise ValueError('points')
  for p in pts:
   if not isinstance(p,list) or len(p)!=2 or any(not isinstance(x,(int,float)) or not math.isfinite(x) or not -100<=x<=5000 for x in p):raise ValueError('coordinate')
  out.append({'points':pts,'width':width,'color':color})
 return {'session':d['session'],'glyph':d['glyph'],'strokes':out,'note':note,'schema':1}
def save_record(d):
 body=json.dumps(validate(d),ensure_ascii=False,separators=(',',':'),sort_keys=True)
 ident=hashlib.sha256(body.encode()).hexdigest()[:32]
 with LOCK,database() as c:
  c.execute('INSERT OR IGNORE INTO drawings(id,session,glyph,body,status,created) VALUES(?,?,?,?,?,?)',(ident,d['session'],d['glyph'],body,'queued',time.time()))
 return ident
def svg(d):
 g=GLYPHS[d['glyph']];w=max(1000,g['advance']+200)
 s=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} 1100"><title>{g["char"]}</title>',f'<desc>{html.escape(d["note"])}</desc><rect width="100%" height="100%" fill="white"/>']
 for y in (850,355,160,1045):s.append(f'<path d="M35 {y}H{w-35}" stroke="#dedde4" fill="none"/>')
 s.append(f'<path d="{g["path"]}" fill="#08084d" opacity=".12" transform="translate({(w-g["advance"])/2} 850) scale(1 -1)"/>')
 for x in d['strokes']:
  path='M'+'L'.join(f'{p[0]},{p[1]}' for p in x['points'])
  if len(x['points'])==1:path+='l.01,.01'
  s.append(f'<path d="{path}" fill="none" stroke="{x["color"]}" stroke-width="{x["width"]}" stroke-linecap="round" stroke-linejoin="round"/>')
 return (''.join(s)+'</svg>').encode()
class GitArchive:
 def run(self,*args):
  env={**os.environ,'GIT_SSH_COMMAND':f'ssh -i {KEY} -o IdentitiesOnly=yes -o UserKnownHostsFile={DATA}/known_hosts -o StrictHostKeyChecking=yes','GIT_TERMINAL_PROMPT':'0'}
  result=subprocess.run(['git',*args],cwd=str(GITDIR) if GITDIR.exists() else str(DATA),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
  if result.returncode:raise RuntimeError('Archive git operation failed')
  return result.stdout.decode()
 def publish(self,d,ident):
  if not (GITDIR/'.git').exists():self.run('clone','--branch','drawings','--single-branch','git@github.com:'+REPO+'.git',str(GITDIR))
  self.run('fetch','origin','drawings');self.run('reset','--hard','origin/drawings')
  rel=f'submissions/{d["session"]}/{d["glyph"]}-{ident}'
  p=GITDIR/rel;p.parent.mkdir(parents=True,exist_ok=True)
  p.with_suffix('.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
  p.with_suffix('.svg').write_bytes(svg(d))
  self.run('add','--',rel+'.json',rel+'.svg')
  if self.run('status','--porcelain'):
   self.run('-c','user.name=Glyph review stand','-c','user.email=review@localhost','commit','-m','Save '+d['glyph']+' construction '+ident[:8])
   self.run('push','origin','HEAD:drawings')
  return 'https://github.com/'+REPO+'/blob/drawings/'+rel+'.svg','https://github.com/'+REPO+'/blob/drawings/'+rel+'.json'
def upload_one(client):
 with LOCK,database() as c:row=c.execute("SELECT * FROM drawings WHERE status!='saved' AND next_try<=? ORDER BY created LIMIT 1",(time.time(),)).fetchone()
 if row is None:return False
 try:
  d=json.loads(row['body'])
  su,ju=client.publish(d,row['id'])
  with LOCK,database() as c:c.execute("UPDATE drawings SET status='saved',svg_url=?,json_url=? WHERE id=?",(su,ju,row['id']))
 except Exception as e:
  print('GitHub upload pending:',type(e).__name__,flush=True)
  with LOCK,database() as c:c.execute("UPDATE drawings SET status='queued',attempts=attempts+1,next_try=? WHERE id=?",(time.time()+30,row['id']))
 return True
def uploader():
 client=GitArchive()
 while True:
  if not upload_one(client):time.sleep(1)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,status,data):
  b=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.cors();self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def cors(self):
  origin=self.headers.get('Origin','')
  if origin in ('https://pavljenko.github.io','http://127.0.0.1:8797'):
   self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
 def do_OPTIONS(self):
  self.send_response(204);self.cors();self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type, X-Review-Key');self.end_headers()
 def allowed(self):
  import hmac
  return bool(TOKEN) and hmac.compare_digest(self.headers.get('X-Review-Key',''),TOKEN)
 def do_GET(self):
  u=urllib.parse.urlsplit(self.path)
  if u.path.endswith('/api/health'):return self.reply(200,{'ready':True})
  if u.path.endswith('/api/review'):
   if not self.allowed():return self.reply(403,{'error':'Нет доступа'})
   session=urllib.parse.parse_qs(u.query).get('session',[''])[0]
   if not re.fullmatch(r'[a-f0-9-]{36}',session):return self.reply(400,{'error':'Неверная сессия'})
   with LOCK,database() as c:rows=c.execute('SELECT id,glyph,status,svg_url,json_url,created FROM drawings WHERE session=? ORDER BY created',(session,)).fetchall()
   return self.reply(200,{'records':[dict(r) for r in rows]})
  if os.environ.get('LOCAL_PREVIEW')=='1':
   name=u.path.split('/')[-1] or 'index.html';p=ROOT/'docs'/name
   if p.is_file() and p.parent==ROOT/'docs':
    self.send_response(200);self.send_header('Content-Type','application/javascript' if p.suffix=='.js' else 'text/html; charset=utf-8');self.end_headers();return self.wfile.write(p.read_bytes())
  self.reply(404,{'error':'Не найдено'})
 def do_POST(self):
  if urllib.parse.urlsplit(self.path).path!='/nor-nakhijevan/api/review':return self.reply(404,{'error':'Не найдено'})
  if not self.allowed():return self.reply(403,{'error':'Нет доступа'})
  origin=self.headers.get('Origin')
  if origin and origin not in ('https://pavljenko.github.io','http://127.0.0.1:8797'):return self.reply(403,{'error':'Неверный источник'})
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=1500000:return self.reply(413,{'error':'Рисунок слишком большой'})
   d=json.loads(self.rfile.read(n));ident=save_record(d)
   self.reply(202,{'id':ident,'accepted':True})
  except (ValueError,TypeError,KeyError,AttributeError):self.reply(400,{'error':'Неверный рисунок'})
  except Exception:self.reply(500,{'error':'Не удалось принять рисунок'})
if __name__=='__main__':
 init()
 if os.environ.get('NO_UPLOAD')!='1':threading.Thread(target=uploader,daemon=True).start()
 ThreadingHTTPServer(('127.0.0.1',8797),Handler).serve_forever()
