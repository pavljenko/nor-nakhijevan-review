// A timed polyline, not video: preserve the author's pauses and drawing speed.
class MotionCapture {
  constructor(glyph,viewBox,source=null) {
    this.glyph=glyph;this.viewBox=viewBox;this.strokes=source?.strokes.map(s=>({points:s.points.map(p=>[...p])}))||[];
    this.origin=null;this.active=null;this.resumeAt=source?.duration||0;
  }
  begin(x,y,now) {
    if(this.active)return false;
    if(this.origin===null)this.origin=now-this.resumeAt;
    this.active={points:[]};this.strokes.push(this.active);this.add(x,y,now,true);return true;
  }
  add(x,y,now,force=false) {
    if(!this.active)return;
    const last=this.active.points.at(-1),t=Math.max(last?.[2]||0,Math.round(now-this.origin));
    const p=[Math.round(x*10)/10,Math.round(y*10)/10,t];
    if(!last||force||t-last[2]>=8||Math.hypot(x-last[0],y-last[1])>=2)this.active.points.push(p);
  }
  end(x,y,now){if(!this.active)return;this.add(x,y,now,true);this.active=null;}
  undo(){if(this.active)return;this.strokes.pop();this.resumeAt=this.strokes.at(-1)?.points.at(-1)?.[2]||0;this.origin=null;}
  pause(){this.resumeAt=this.strokes.at(-1)?.points.at(-1)?.[2]||0;this.origin=null;}
  snapshot(){
    const strokes=this.strokes.map(s=>({points:simplifyTimed(s.points,1.2)}));
    return {schema:1,glyph:this.glyph,viewBox:this.viewBox,duration:strokes.at(-1)?.points.at(-1)?.[2]||0,strokes};
  }
}
function simplifyTimed(points,tolerance) {
  if(points.length<3)return points.map(p=>[...p]);
  const keep=new Set([0,points.length-1]),stack=[[0,points.length-1]];
  while(stack.length){
    const [a,b]=stack.pop(),start=points[a],end=points[b],dt=end[2]-start[2];let best=tolerance,index=-1;
    for(let i=a+1;i<b;i++){
      const k=dt?(points[i][2]-start[2])/dt:0;
      const error=Math.hypot(points[i][0]-start[0]-(end[0]-start[0])*k,points[i][1]-start[1]-(end[1]-start[1])*k);
      if(error>best){best=error;index=i;}
    }
    if(index!==-1){keep.add(index);stack.push([a,index],[index,b]);}
  }
  return [...keep].sort((a,b)=>a-b).map(i=>[...points[i]]);
}
function motionPath(points){return 'M'+points.map(p=>p.slice(0,2).join(',')).join('L')+(points.length===1?'l.01,.01':'');}
function prepareMotion(motion){
  return motion.strokes.map(s=>{
    const lengths=[0];for(let i=1;i<s.points.length;i++)lengths.push(lengths.at(-1)+Math.hypot(s.points[i][0]-s.points[i-1][0],s.points[i][1]-s.points[i-1][1]));
    return {points:s.points,lengths,total:lengths.at(-1),path:motionPath(s.points)};
  });
}
function motionFrame(strokes,time){
  let tip=null;const states=strokes.map(s=>{
    const ps=s.points,first=ps[0],last=ps.at(-1);
    if(time<first[2])return {visible:false,progress:0};
    if(time>last[2])return {visible:true,progress:1};
    let lo=0,hi=ps.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(ps[mid][2]<=time)lo=mid;else hi=mid-1;}
    const a=ps[lo],b=ps[Math.min(lo+1,ps.length-1)],u=b[2]>a[2]?(time-a[2])/(b[2]-a[2]):0;
    tip=[a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u];
    return {visible:true,progress:s.total?(s.lengths[lo]+Math.hypot(b[0]-a[0],b[1]-a[1])*u)/s.total:1};
  });
  return {states,tip};
}
class MotionPlayer {
  constructor({motion,paths,hand,request=fn=>requestAnimationFrame(fn),cancel=id=>cancelAnimationFrame(id),onEnd=()=>{}}){
    Object.assign(this,{motion,paths,hand,request,cancel,onEnd});this.strokes=prepareMotion(motion);this.frame=null;
  }
  seek(time){
    const f=motionFrame(this.strokes,time);
    f.states.forEach((s,i)=>{this.paths[i].setAttribute('visibility',s.visible?'visible':'hidden');this.paths[i].setAttribute('stroke-dashoffset',String(1-s.progress));});
    this.hand.setAttribute('visibility',f.tip?'visible':'hidden');
    if(f.tip)this.hand.setAttribute('transform',`translate(${f.tip[0]} ${f.tip[1]}) rotate(-14) scale(.30) translate(-234.667 0)`);
  }
  play(){
    this.stop();let start;
    const tick=now=>{
      if(start===undefined)start=now;
      const time=now-start-350;this.seek(time);
      if(time<this.motion.duration+450)this.frame=this.request(tick);
      else{this.frame=null;this.hand.setAttribute('visibility','hidden');this.onEnd();}
    };
    this.frame=this.request(tick);
  }
  stop(){if(this.frame!==null)this.cancel(this.frame);this.frame=null;this.hand.setAttribute('visibility','hidden');}
}
