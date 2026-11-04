import json,re,hashlib
from pathlib import Path
root=Path(__file__).parent
s=(root/'src/review.html').read_text().replace('__GLYPHS__',(root/'glyphs.json').read_text())
s=s.replace('__SAVE_QUEUE__',(root/'src/save-queue.js').read_text())
s=s.replace('__CANVAS_GUARDS__',(root/'src/canvas-guards.js').read_text())
s=s.replace('__MOTION__',(root/'src/motion.js').read_text())
s=s.replace('__TUTORIAL_UI__',(root/'src/tutorial.js').read_text())
s=s.replace('__TUTORIAL__',(root/'src/tutorial-motion.json').read_text())
finger=re.search(r' d="([^"]+)"',(root/'src/assets/finger.svg').read_text()).group(1)
s=s.replace('__FINGER_PATH__',json.dumps(finger))
(root/'docs/stand.html').write_text(s)
style=re.search(r'<style>(.*?)</style>',s,re.S).group(1);body=re.search(r'<body>(.*?)<script>',s,re.S).group(1);js=re.search(r'<script>(.*?)</script>',s,re.S).group(1)
bundle="'use strict';\nconst style=document.createElement('style');style.textContent="+json.dumps(style)+";document.head.append(style);document.body.innerHTML="+json.dumps(body)+";\n"+js
name='nor-nakhijevan-'+hashlib.sha256(bundle.encode()).hexdigest()[:12]+'.js'
(root/'docs'/name).write_text(bundle)
head=s.split('<style>')[0]
(root/'docs/index.html').write_text(head+'</head><body><script src="'+name+'"></script></body></html>')
print(name)
recorder=(root/'src/recorder.html').read_text().replace('__GLYPHS__',(root/'glyphs.json').read_text())
recorder=recorder.replace('__CANVAS_GUARDS__',(root/'src/canvas-guards.js').read_text())
recorder=recorder.replace('__MOTION__',(root/'src/motion.js').read_text())
recorder=recorder.replace('__FINGER_PATH__',json.dumps(finger))
(root/'docs/recorder.html').write_text(recorder)
print('recorder.html')
