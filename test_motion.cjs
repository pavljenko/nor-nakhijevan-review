const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context=vm.createContext({});vm.runInContext(fs.readFileSync('src/motion.js','utf8')+';this.api={MotionCapture,MotionPlayer,simplifyTimed,prepareMotion,motionFrame}',context);
const {MotionCapture,MotionPlayer,simplifyTimed,prepareMotion,motionFrame}=context.api;
const capture=new MotionCapture('U0531',[0,0,1103,1100]);
capture.begin(100,200,1000);capture.add(150,200,1100);capture.add(200,200,1200);capture.end(200,200,1400);
capture.begin(300,400,1900);capture.end(300,500,2100);
const record=capture.snapshot();assert.equal(record.duration,1100);
assert.equal(record.strokes[0].points[0][2],0);assert.equal(record.strokes[1].points[0][2],900);
const prepared=prepareMotion(record);
const f=motionFrame(prepared,150);assert.ok(Math.abs(f.tip[0]-175)<.001);assert.ok(Math.abs(f.tip[1]-200)<.001);
assert.equal(motionFrame(prepared,-1).tip,null);assert.equal(motionFrame(prepared,650).tip,null);
assert.equal(motionFrame(prepared,1000).tip[1],450);assert.equal(motionFrame(prepared,1200).tip,null);
// A hold and a velocity change must survive simplification, even on a straight line.
const held=[[0,0,0],[100,0,100],[100,0,600],[200,0,700]];
assert.equal(simplifyTimed(held,1).length,4);
const linear=Array.from({length:501},(_,i)=>[i,0,i*10]);assert.equal(simplifyTimed(linear,1).length,2);
const rounded=Array.from({length:1001},(_,i)=>[Math.cos(i/1000*Math.PI)*100,Math.sin(i/1000*Math.PI)*100,i]);
const small=simplifyTimed(rounded,1.2);assert.ok(small.length<100);
const src=prepareMotion({strokes:[{points:small}]});
for(let i=0;i<1000;i++)assert.ok(Math.hypot(...motionFrame(src,i).tip.map((v,j)=>v-rounded[i][j]))<=1.21);
// Restoring a draft continues after its previous end. Preview time is excluded.
const restore=new MotionCapture('U0531',record.viewBox,record);restore.begin(20,30,9000);restore.end(30,40,9100);assert.equal(restore.snapshot().duration,1200);
restore.undo();assert.equal(restore.snapshot().duration,1100);
restore.pause();restore.begin(50,60,25000);restore.end(60,70,25100);assert.equal(restore.snapshot().duration,1200);
// Cursor hotspot is exactly the sampled point, and repeated playback cancels RAF.
class Element {constructor(){this.attrs={}}setAttribute(k,v){this.attrs[k]=v}}
let scheduled=new Map(),serial=0,finished=0;
const paths=record.strokes.map(()=>new Element()),hand=new Element();
const player=new MotionPlayer({motion:record,paths,hand,request:fn=>{scheduled.set(++serial,fn);return serial},cancel:id=>scheduled.delete(id),onEnd:()=>finished++});
player.seek(150);assert.ok(hand.attrs.transform.startsWith('translate(175 200)'));assert.equal(hand.attrs.visibility,'visible');
player.seek(650);assert.equal(hand.attrs.visibility,'hidden');
player.play();player.play();assert.equal(scheduled.size,1);player.stop();assert.equal(scheduled.size,0);
// Browser RAF functions must be called as globals, never as player methods.
context.requestAnimationFrame=function(fn){assert.ok(!this?.motion,'illegal RAF receiver');return 1;};
context.cancelAnimationFrame=function(id){assert.ok(!this?.motion,'illegal RAF receiver');};
const defaults=new MotionPlayer({motion:record,paths,hand});defaults.play();defaults.stop();
console.log('Passed: real timing, lifted-finger gaps, holds, bounded simplification error, restore, cursor alignment, RAF cancellation');
