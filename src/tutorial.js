const TUTORIAL_MOTION=__TUTORIAL__,TUTORIAL_FINGER=__FINGER_PATH__;
function showDrawingTutorial(){
 const style=document.createElement('style');style.textContent=`
 #drawing-tutorial{width:min(96vw,640px);height:min(92vh,780px);height:min(92svh,780px);max-height:92svh;padding:0;overflow:hidden;border-radius:20px;background:var(--paper);touch-action:none}
 #drawing-tutorial[open]{display:flex;flex-direction:column}
 .tutorial-head{padding:18px 18px 12px;flex:none}.tutorial-head h2{margin:0;font-size:19px;line-height:1.3;font-weight:550}
 .tutorial-demo{position:relative;flex:1;min-height:0;min-width:0;background:#fff;border-block:1px solid var(--line);overflow:hidden;touch-action:none;user-select:none;-webkit-user-select:none;-webkit-touch-callout:none}
 .tutorial-actions{display:flex;gap:8px;padding:12px;flex:none}.tutorial-start{flex:1;min-width:0;background:var(--ink);color:#fff;border-color:var(--ink);font-weight:550}.tutorial-repeat{width:48px;min-width:44px;font-size:23px;padding:0}
 @media(max-height:450px){.tutorial-head{padding:10px 14px 8px}.tutorial-head h2{font-size:16px}.tutorial-actions{padding:8px}}
 `;document.head.append(style);
 const dialog=document.createElement('dialog');dialog.id='drawing-tutorial';dialog.setAttribute('aria-labelledby','tutorial-title');
 dialog.innerHTML='<header class="tutorial-head"><h2 id="tutorial-title">Нарисуйте свой вариант буквы целиком</h2></header><div class="tutorial-demo"></div><footer class="tutorial-actions"><button class="tutorial-repeat" aria-label="Повторить показ" title="Повторить показ">↻</button><button class="tutorial-start" autofocus>Начать рисовать</button></footer>';
 const g=glyphs[TUTORIAL_MOTION.glyph],svg=makeSvg(g,false);svg.setAttribute('class','editor-canvas');svg.setAttribute('aria-label','Показ рисования нового контура '+g.char);svg.querySelector('.original').setAttribute('opacity','.12');
 const paths=[];
 for(const s of TUTORIAL_MOTION.strokes){const p=node('path',{d:motionPath(s.points),fill:'none',stroke:'#d63842','stroke-width':7,'stroke-linecap':'round','stroke-linejoin':'round',pathLength:1,'stroke-dasharray':1,'stroke-dashoffset':1,visibility:'hidden'});paths.push(p);svg.append(p);}
 const hand=node('g',{visibility:'hidden','aria-hidden':'true'});hand.append(node('path',{d:TUTORIAL_FINGER,fill:'#11134b',stroke:'#fff','stroke-width':16,'stroke-linejoin':'round','paint-order':'stroke fill'}));svg.append(hand);
 dialog.querySelector('.tutorial-demo').append(svg);document.body.append(dialog);
 const player=new MotionPlayer({motion:TUTORIAL_MOTION,paths,hand});
 dialog.querySelector('.tutorial-repeat').onclick=()=>player.play();dialog.querySelector('.tutorial-start').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{player.stop();dialog.remove();});
 dialog.showModal();
 if(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){player.seek(TUTORIAL_MOTION.duration+1);}
 else player.play();
}
