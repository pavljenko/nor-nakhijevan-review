const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context=vm.createContext({});
vm.runInContext(fs.readFileSync('src/canvas-guards.js','utf8')+';this.install=installCanvasGuards',context);
class Surface {
 constructor(){this.events=new Map()}
 addEventListener(name,fn,options){this.events.set(name,{fn,options})}
 fire(name,{cancelable=true,inDialog=false}={}) {
  const event={cancelable,prevented:false,target:{closest:()=>inDialog?{}:null},preventDefault(){this.prevented=true}};
  this.events.get(name).fn(event);return event.prevented;
 }
}
const app=new Surface(),stage=new Surface(),document=new Surface();let open=false;
context.install({app,stage,document,isPickerOpen:()=>open});
for(const event of ['touchstart','touchmove','gesturestart','gesturechange']) {
 assert.equal(stage.events.get(event).options.passive,false);
 assert.equal(stage.fire(event),true);assert.equal(stage.fire(event,{cancelable:false}),false);
}
for(const event of ['dragstart','contextmenu'])assert.equal(stage.fire(event),true);
for(const event of ['gesturestart','gesturechange','wheel'])assert.equal(app.fire(event),true);
assert.equal(document.fire('touchmove'),true);
open=true;assert.equal(document.fire('touchmove',{inDialog:true}),false);
assert.equal(document.fire('touchmove',{inDialog:false}),true);
// Buttons keep their normal taps; scrolling is intercepted only on movement.
assert.equal(app.events.has('touchstart'),false);
const legacyWindow=new Surface();legacyWindow.innerWidth=320;legacyWindow.innerHeight=568;
document.defaultView=legacyWindow;app.style={};
context.install({app,stage,document,isPickerOpen:()=>false});
assert.equal(app.style.height,'568px');
legacyWindow.innerHeight=640;legacyWindow.fire('resize');assert.equal(app.style.height,'568px');
legacyWindow.innerWidth=640;legacyWindow.innerHeight=320;legacyWindow.fire('resize');assert.equal(app.style.height,'320px');
console.log('Passed: native pan/zoom/drag cancelled, non-passive touch handlers, picker scroll and button taps preserved');
