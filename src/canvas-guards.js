// Native touch cancellation complements touch-action in older mobile WebKit.
// Scope it to the editor; the separate alphabet dialog must still scroll.
function installCanvasGuards({app,stage,document,isPickerOpen}) {
  const view=document.defaultView;
  if(view&&!view.CSS?.supports('height','100svh')) {
    let width=view.innerWidth;
    const fit=()=>{app.style.height=view.innerHeight+'px';};
    fit();
    // Older browsers: toolbar show/hide must not resize the drawing surface.
    // A width change still refits the editor after rotating the device.
    view.addEventListener('resize',()=>{if(view.innerWidth!==width){width=view.innerWidth;fit();}});
  }
  const cancel=e=>{if(e.cancelable)e.preventDefault();};
  for(const name of ['touchstart','touchmove','gesturestart','gesturechange']) {
    stage.addEventListener(name,cancel,{passive:false});
  }
  for(const name of ['dragstart','contextmenu'])stage.addEventListener(name,cancel);
  for(const name of ['gesturestart','gesturechange','wheel']) {
    app.addEventListener(name,cancel,{passive:false});
  }
  document.addEventListener('touchmove',e=>{
    if(!isPickerOpen()||!e.target?.closest?.('dialog'))cancel(e);
  },{passive:false});
}
