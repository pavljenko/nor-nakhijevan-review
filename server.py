# coding: utf-8
"""Dedicated drawing collector. Credentials stay server-side; no font masters changed."""
import os,json,re,math,time,uuid,hashlib,sqlite3,threading,urllib.parse,html,subprocess
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('REVIEW_DATA',str(ROOT/'data')))
REPO='pavljenko/nor-nakhijevan-review'
GITDIR=DATA/'git'
KEY=DATA/'deploy_key'
TOKEN=os.environ.get('REVIEW_TOKEN','')
OWNER_TOKEN=os.environ.get('OWNER_TOKEN','')
GLYPHS=json.loads((ROOT/'glyphs.json').read_text())
GLYPHS={g['id']:g for p in GLYPHS['pairs'] for g in [p['upper'],p['lower']]}
LOCK=threading.Lock()
WAKE=threading.Event()
@contextmanager
def database():
 c=sqlite3.connect(DATA/'archive.sqlite',timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA synchronous=FULL')
 try:
  with c:yield c
 finally:c.close()
def init():
 DATA.mkdir(parents=True,exist_ok=True)
 with database() as c:
  c.execute('PRAGMA journal_mode=WAL')
  c.execute('CREATE TABLE IF NOT EXISTS drawings (id TEXT PRIMARY KEY, session TEXT, glyph TEXT, body TEXT, status TEXT, svg_url TEXT, json_url TEXT, attempts INTEGER DEFAULT 0, next_try REAL DEFAULT 0, created REAL)')
  c.execute('CREATE TABLE IF NOT EXISTS deleted_groups (session TEXT, glyph TEXT, status TEXT, next_try REAL DEFAULT 0, PRIMARY KEY(session,glyph))')
  if 'revision' not in [r[1] for r in c.execute('PRAGMA table_info(drawings)')]:c.execute('ALTER TABLE drawings ADD COLUMN revision INTEGER DEFAULT 0')
  c.execute('CREATE INDEX IF NOT EXISTS drawings_group_revision ON drawings(session,glyph,revision)')
  c.execute('CREATE TABLE IF NOT EXISTS motions (id TEXT PRIMARY KEY, glyph TEXT, body TEXT, created REAL)')
def validate_motion(d):
 if d.get('schema')!=1 or d.get('glyph') not in GLYPHS:raise ValueError('glyph')
 w=max(1000,GLYPHS[d['glyph']]['advance']+200)
 if d.get('viewBox')!=[0,0,w,1100]:raise ValueError('viewBox')
 duration=d.get('duration');strokes=d.get('strokes')
 if type(duration) is not int or not 0<=duration<=180000:raise ValueError('duration')
 if not isinstance(strokes,list) or not 1<=len(strokes)<=100:raise ValueError('strokes')
 count=0;previous=-1;out=[]
 for stroke in strokes:
  points=stroke.get('points')
  if not isinstance(points,list) or not 1<=len(points)<=20000:raise ValueError('points')
  count+=len(points)
  if count>60000:raise ValueError('points')
  clean=[]
  for p in points:
   if not isinstance(p,list) or len(p)!=3:raise ValueError('point')
   x,y,t=p
   if any(type(v) not in (int,float) or not math.isfinite(v) or not -5000<=v<=5000 for v in (x,y)):raise ValueError('coordinate')
   if type(t) is not int or not 0<=t<=duration or t<previous:raise ValueError('time')
   clean.append([x,y,t]);previous=t
  out.append({'points':clean})
 if out[0]['points'][0][2]!=0 or previous!=duration:raise ValueError('time bounds')
 return {'schema':1,'glyph':d['glyph'],'viewBox':[0,0,w,1100],'duration':duration,'strokes':out}
def save_motion(d):
 d=validate_motion(d);body=json.dumps(d,ensure_ascii=False,separators=(',',':'),sort_keys=True)
 ident=hashlib.sha256(body.encode()).hexdigest()[:32]
 with LOCK,database() as c:
  folder=DATA/'motions';folder.mkdir(exist_ok=True)
  temp=folder/(ident+'.pending')
  with temp.open('wb') as f:f.write(body.encode());f.flush();os.fsync(f.fileno())
  os.replace(temp,folder/(ident+'.json'))
  c.execute('INSERT OR IGNORE INTO motions(id,glyph,body,created) VALUES(?,?,?,?)',(ident,d['glyph'],body,time.time()))
 return ident
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
 result={'session':d['session'],'glyph':d['glyph'],'strokes':out,'note':note,'schema':1}
 if 'revision' in d:
  if type(d['revision']) is not int or not 1<=d['revision']<=1000000000:raise ValueError('revision')
  result['revision']=d['revision']
 return result
def save_record(d):
 body=json.dumps(validate(d),ensure_ascii=False,separators=(',',':'),sort_keys=True)
 ident=hashlib.sha256(body.encode()).hexdigest()[:32]
 with LOCK,database() as c:
  if c.execute('SELECT 1 FROM deleted_groups WHERE session=? AND glyph=?',(d['session'],d['glyph'])).fetchone():raise ValueError('deleted group')
  revision=d.get('revision',0)
  if revision:
   latest=c.execute('SELECT id,revision FROM drawings WHERE session=? AND glyph=? ORDER BY revision DESC LIMIT 1',(d['session'],d['glyph'])).fetchone()
   if latest and latest['revision']>=revision:return latest['id']
  c.execute('INSERT OR IGNORE INTO drawings(id,session,glyph,body,status,created,revision) VALUES(?,?,?,?,?,?,?)',(ident,d['session'],d['glyph'],body,'queued',time.time(),revision))
 WAKE.set()
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
def public_gallery():
 with LOCK,database() as c:
  rows=c.execute("SELECT d.* FROM drawings d WHERE d.status IN ('saved','queued') AND NOT EXISTS(SELECT 1 FROM deleted_groups g WHERE g.session=d.session AND g.glyph=d.glyph) ORDER BY d.created DESC").fetchall()
 records=[]
 for row in rows:
  d=json.loads(row['body'])
  if not d.get('strokes'):continue
  rel=f'submissions/{d["session"]}/{d["glyph"]}-{row["id"]}'
  preview='https://tools.pavljenko.ru/nor-nakhijevan/api/sketch/'+row['id']
  records.append({'id':row['id'],'session':d['session'],'glyph':d['glyph'],'char':GLYPHS[d['glyph']]['char'],'created':row['created'],'note':d.get('note',''),'svg':rel+'.svg','json':rel+'.json','preview_svg':preview+'.svg','preview_json':preview+'.json'})
 return {'records':records}
def gallery_index():
 with database() as c:dates={r['id']:r['created'] for r in c.execute('SELECT id,created FROM drawings')}
 with database() as c:deleted={(r['session'],r['glyph']) for r in c.execute('SELECT session,glyph FROM deleted_groups')}
 records=[]
 for p in (GITDIR/'submissions').glob('*/*.json'):
  d=json.loads(p.read_text())
  if not d.get('strokes') or (d['session'],d['glyph']) in deleted:continue
  ident=p.stem.split('-')[-1];rel=p.relative_to(GITDIR).with_suffix('').as_posix()
  records.append({'id':ident,'session':d['session'],'glyph':d['glyph'],'char':GLYPHS[d['glyph']]['char'],'created':dates.get(ident,p.stat().st_mtime),'note':d.get('note',''),'svg':rel+'.svg','json':rel+'.json'})
 records.sort(key=lambda r:r['created'],reverse=True)
 (GITDIR/'gallery.json').write_text(json.dumps({'records':records},ensure_ascii=False,indent=2)+'\n')
 latest={}
 for r in records:latest.setdefault((r['session'],r['glyph']),r)
 gallery=GITDIR/'gallery';gallery.mkdir(exist_ok=True)
 cards=list(latest.values())
 for old in gallery.glob('latest-*.svg'):old.unlink()
 for i,r in enumerate(cards[:6],1):(gallery/f'latest-{i}.svg').write_bytes((GITDIR/r['svg']).read_bytes())
 lines=['# Зарисовки','', '[Открыть галерею](https://tools.pavljenko.ru/nor-gallery)','', 'Новые варианты сверху. Все предыдущие версии сохранены в папке submissions.','']
 from datetime import datetime,timezone
 for r in cards[:100]:
  date=datetime.fromtimestamp(r['created'],timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
  lines.extend([f'### {r["char"]} · {date}', '', f'[![{r["char"]}]({r["svg"]})]({r["svg"]})','',html.escape(r['note']), '', f'[SVG]({r["svg"]}) · [Данные]({r["json"]})',''])
 (GITDIR/'README.md').write_text('\n'.join(lines))
 return records
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
  gallery_index()
  self.run('add','--',rel+'.json',rel+'.svg','README.md','gallery.json','gallery')
  if self.run('status','--porcelain'):
   self.run('-c','user.name=Glyph review stand','-c','user.email=review@localhost','commit','-m','Save '+d['glyph']+' construction '+ident[:8])
   self.run('push','origin','HEAD:drawings')
  return 'https://github.com/'+REPO+'/blob/drawings/'+rel+'.svg','https://github.com/'+REPO+'/blob/drawings/'+rel+'.json'
 def remove_group(self,session,glyph):
  self.run('fetch','origin','drawings');self.run('reset','--hard','origin/drawings')
  for suffix in ('json','svg'):
   for p in (GITDIR/'submissions'/session).glob(glyph+'-*.'+suffix):p.unlink()
  gallery_index();self.run('add','-A','--','submissions','gallery','gallery.json','README.md')
  if self.run('status','--porcelain'):
   self.run('-c','user.name=Glyph review stand','-c','user.email=review@localhost','commit','-m','Remove construction '+glyph+' from session '+session)
   self.run('push','origin','HEAD:drawings')
def request_delete(session,glyph):
 if not isinstance(session,str) or not re.fullmatch(r'[a-f0-9-]{36}',session) or glyph not in GLYPHS:raise ValueError('invalid group')
 with LOCK,database() as c:
  if not c.execute('SELECT 1 FROM drawings WHERE session=? AND glyph=?',(session,glyph)).fetchone():raise ValueError('unknown group')
  c.execute("INSERT OR IGNORE INTO deleted_groups(session,glyph,status) VALUES(?,?,'queued')",(session,glyph))
  c.execute("UPDATE drawings SET status='deleted' WHERE session=? AND glyph=?",(session,glyph))
 WAKE.set()
def delete_one(client):
 with LOCK,database() as c:r=c.execute("SELECT * FROM deleted_groups WHERE status='queued' AND next_try<=? LIMIT 1",(time.time(),)).fetchone()
 if r is None:return False
 try:
  client.remove_group(r['session'],r['glyph'])
  with LOCK,database() as c:c.execute("UPDATE deleted_groups SET status='done' WHERE session=? AND glyph=?",(r['session'],r['glyph']))
 except Exception:
  with LOCK,database() as c:c.execute('UPDATE deleted_groups SET next_try=? WHERE session=? AND glyph=?',(time.time()+30,r['session'],r['glyph']))
 return True
def upload_one(client):
 with LOCK,database() as c:row=c.execute("SELECT * FROM drawings WHERE status='queued' AND next_try<=? ORDER BY created LIMIT 1",(time.time(),)).fetchone()
 if row is None:return False
 try:
  d=json.loads(row['body'])
  su,ju=client.publish(d,row['id'])
  with LOCK,database() as c:c.execute("UPDATE drawings SET status='saved',svg_url=?,json_url=? WHERE id=? AND status!='deleted'",(su,ju,row['id']))
 except Exception as e:
  print('GitHub upload pending:',type(e).__name__,flush=True)
  with LOCK,database() as c:c.execute("UPDATE drawings SET status='queued',attempts=attempts+1,next_try=? WHERE id=? AND status!='deleted'",(time.time()+30,row['id']))
 return True
def uploader():
 client=GitArchive()
 while True:
  WAKE.clear()
  if not delete_one(client) and not upload_one(client):WAKE.wait(1)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,status,data):
  b=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.cors();self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def cors(self):
  origin=self.headers.get('Origin','')
  if origin in ('https://pavljenko.github.io','https://tools.pavljenko.ru','http://127.0.0.1:8797'):
   self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
 def do_OPTIONS(self):
  self.send_response(204);self.cors();self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type, X-Review-Key, X-Owner-Key');self.send_header('Access-Control-Max-Age','3600');self.end_headers()
 def allowed(self):
  import hmac
  return bool(TOKEN) and hmac.compare_digest(self.headers.get('X-Review-Key',''),TOKEN)
 def owner_allowed(self):
  import hmac
  return bool(OWNER_TOKEN) and hmac.compare_digest(self.headers.get('X-Owner-Key',''),OWNER_TOKEN)
 def do_GET(self):
  u=urllib.parse.urlsplit(self.path)
  if u.path.endswith('/api/recorder-ui'):
   b=(ROOT/'recorder.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.end_headers();return self.wfile.write(b)
  if u.path.endswith('/api/motions') or re.fullmatch(r'/nor-nakhijevan/api/motions/[a-f0-9]{32}',u.path):
   if not self.owner_allowed():return self.reply(403,{'error':'Только автор может открывать записи показа'})
   with LOCK,database() as c:
    if u.path.endswith('/api/motions'):
     rows=c.execute('SELECT id,glyph,created,length(body) AS bytes FROM motions ORDER BY created DESC').fetchall()
     return self.reply(200,{'records':[dict(r) for r in rows]})
    row=c.execute('SELECT body FROM motions WHERE id=?',(u.path.rsplit('/',1)[-1],)).fetchone()
   return self.reply(200,json.loads(row['body'])) if row else self.reply(404,{'error':'Запись не найдена'})
  if u.path.endswith('/api/stand-ui'):
   b=(ROOT/'stand.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.end_headers();return self.wfile.write(b)
  match=re.fullmatch(r'/nor-nakhijevan/api/sketch/([a-f0-9]{32})\.(svg|json)',u.path)
  if match:
   with LOCK,database() as c:row=c.execute("SELECT d.body FROM drawings d WHERE d.id=? AND d.status IN ('saved','queued') AND NOT EXISTS(SELECT 1 FROM deleted_groups g WHERE g.session=d.session AND g.glyph=d.glyph)",(match[1],)).fetchone()
   if not row:return self.reply(404,{'error':'Не найдено'})
   d=json.loads(row['body']);b=svg(d) if match[2]=='svg' else row['body'].encode()
   self.send_response(200);self.cors();self.send_header('Content-Type','image/svg+xml' if match[2]=='svg' else 'application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();return self.wfile.write(b)
  if u.path.endswith('/api/gallery-ui'):
   b=(ROOT/'gallery.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.end_headers();return self.wfile.write(b)
  if u.path.endswith('/api/gallery'):return self.reply(200,public_gallery())
  if u.path.endswith('/api/owner'):
   if not self.owner_allowed():return self.reply(403,{'error':'Нет доступа'})
   with LOCK,database() as c:deleted=[dict(r) for r in c.execute('SELECT session,glyph,status FROM deleted_groups')]
   return self.reply(200,{'owner':True,'deleted':deleted})
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
  if urllib.parse.urlsplit(self.path).path=='/nor-nakhijevan/api/motions':
   if not self.owner_allowed():return self.reply(403,{'error':'Только автор может сохранять показ'})
   if self.headers.get('Origin') not in ('https://pavljenko.github.io','https://tools.pavljenko.ru','http://127.0.0.1:8797',None):return self.reply(403,{'error':'Неверный источник'})
   try:
    n=int(self.headers.get('Content-Length','0'))
    if not 0<n<=1500000:return self.reply(413,{'error':'Запись слишком большая'})
    ident=save_motion(json.loads(self.rfile.read(n)))
    return self.reply(202,{'id':ident,'accepted':True,'durable':True})
   except (ValueError,TypeError,KeyError,AttributeError):return self.reply(400,{'error':'Неверная запись движения'})
   except Exception:return self.reply(500,{'error':'Не удалось сохранить показ'})
  if urllib.parse.urlsplit(self.path).path=='/nor-nakhijevan/api/delete':
   if not self.owner_allowed():return self.reply(403,{'error':'Только владелец может удалять зарисовки'})
   if self.headers.get('Origin') not in ('https://pavljenko.github.io','https://tools.pavljenko.ru','http://127.0.0.1:8797',None):return self.reply(403,{'error':'Неверный источник'})
   try:
    n=int(self.headers.get('Content-Length','0'))
    if not 0<n<=2000:return self.reply(413,{'error':'Неверный запрос'})
    d=json.loads(self.rfile.read(n));request_delete(d.get('session'),d.get('glyph'))
    return self.reply(202,{'accepted':True})
   except (ValueError,TypeError):return self.reply(400,{'error':'Неверная зарисовка'})
  if urllib.parse.urlsplit(self.path).path!='/nor-nakhijevan/api/review':return self.reply(404,{'error':'Не найдено'})
  if not self.allowed():return self.reply(403,{'error':'Нет доступа'})
  origin=self.headers.get('Origin')
  if origin and origin not in ('https://pavljenko.github.io','https://tools.pavljenko.ru','http://127.0.0.1:8797'):return self.reply(403,{'error':'Неверный источник'})
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=1500000:return self.reply(413,{'error':'Рисунок слишком большой'})
   d=json.loads(self.rfile.read(n));ident=save_record(d)
   self.reply(202,{'id':ident,'accepted':True,'durable':True})
  except (ValueError,TypeError,KeyError,AttributeError):self.reply(400,{'error':'Неверный рисунок'})
  except Exception:self.reply(500,{'error':'Не удалось принять рисунок'})
if __name__=='__main__':
 init()
 if os.environ.get('NO_UPLOAD')!='1':threading.Thread(target=uploader,daemon=True).start()
 ThreadingHTTPServer(('127.0.0.1',8797),Handler).serve_forever()
