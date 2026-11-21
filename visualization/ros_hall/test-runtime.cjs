const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function createRuntime(){
 const elements=new Map();
 function node(id=''){return {value:id==='mode'?'public':id==='party-size'||id==='arrival-count'?'1':id==='demo-speed'?'full':id==='staff-action'?'review':'individual',checked:false,hidden:false,disabled:false,selectedOptions:[{textContent:'演示'}],classList:{add(){},remove(){},toggle(){}},style:{},children:[],append(){},prepend(){},replaceChildren(){},getContext(){return new Proxy({measureText:t=>({width:t.length*34}),createLinearGradient:()=>({addColorStop(){}})},{get:(o,k)=>o[k]||(()=>{})});}};}
 function el(id){if(!elements.has(id))elements.set(id,node(id));return elements.get(id);}
 const document={getElementById:el,querySelectorAll:()=>[],addEventListener(){},createElement:()=>node(),createTextNode:t=>t,body:node()};
 const ctx=vm.createContext({document,window:{addEventListener(){}},console,setTimeout,clearTimeout,Blob,URL,Date,performance});
 for(const file of ['vendor/three.min.js','config.js','layout.js','motion.js','content.js','people.js','app.js','story-data.js','story-panels.js','scene.js','details.js','performance.js','navigation.js','simulation.js','sensing.js','reception.js','crew.js','traffic.js','cameras.js','workflow.js','metrics.js','upgrade-ui.js','exploration.js']){
  let code=fs.readFileSync(path.join(__dirname,file),'utf8');if(file==='simulation.js')code=code.replace(/boot\(\);\s*$/,'');vm.runInContext(code,ctx,{filename:file});
 }
 vm.runInContext(`
 drawRoute=()=>{};drawObstacles=()=>{};imagePanel=()=>material(0xffffff);
 scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(54,1.4,.1,120);cameraAim=new THREE.Vector3();renderer={capabilities:{getMaxAnisotropy:()=>1}};setupMaterials();zones.forEach(buildZone);buildHall();cacheFixtureBounds();batchStaticScene();robot=buildRobot();
 visitorModels=[visitor(0xbd7352,1.58),visitor(0x839b79,1.52),visitor(0xba9a55,1.02)];sceneReady=true;reset();
 function fresh(){ $('audience').value='individual';$('party-size').value='1';$('mode').value='public';reset(); }
 function begin(type='individual',count=1,automatic=false){fresh();$('audience').value=type;$('party-size').value=String(count);$('arrival-count').value=String(count);start(automatic);if(!automatic){until(()=>s.phase==='greeting',60);acceptTour();until(()=>s.reception.count===count&&s.reception.stableFor>1,60);confirmParty();until(()=>s.accepted,60);}}
 function advance(seconds){for(let t=0;t<seconds;t+=1/60){step(1/60);assertPhysical();}}
 function until(condition,limit=2400){let t=0;while(!condition()&&t<limit){step(1/60);assertPhysical();t+=1/60;}if(!condition())throw Error('Timed out '+s.phase+' zone '+s.index+' pos '+JSON.stringify(s.pos)+' path '+JSON.stringify(s.path.slice(0,2))+' / '+sim.records.slice(-3).map(e=>e.message));return t;}
 let metrics={maxV:0,maxW:0,maxA:0,maxAlpha:0,maxMemberStep:0,minCrowd:100,minMemberCrowd:100};
 let physicalPrevious=null;
 function assertPhysical(){
  if(!walkable(s.pos,s.obstacles))throw Error('robot/static overlap');
  const members=s.party.members;
  for(const m of members){if(!walkable(m,s.obstacles,.29))throw Error('visitor/static overlap '+m.id);if(distance(m,s.pos)<.66)throw Error('robot/visitor overlap');}
  for(let i=0;i<members.length;i++)for(let j=i+1;j<members.length;j++)if(distance(members[i],members[j])<.45)throw Error('visitor pair overlap');
  if(s.crowd){const d=distance(s.pos,s.crowd.pos);metrics.minCrowd=Math.min(metrics.minCrowd,d);if(d<.77)throw Error('robot/pedestrian overlap');for(const m of members){const v=distance(m,s.crowd.pos);metrics.minMemberCrowd=Math.min(metrics.minMemberCrowd,v);if(v<.64)throw Error('visitor/pedestrian overlap');}}
  metrics.maxV=Math.max(metrics.maxV,sim.v);metrics.maxW=Math.max(metrics.maxW,Math.abs(sim.w));
  if(physicalPrevious&&physicalPrevious.task===sim.taskId&&sim.time>physicalPrevious.t){const dt=sim.time-physicalPrevious.t;if(s.phase==='moving'&&physicalPrevious.phase==='moving'){metrics.maxA=Math.max(metrics.maxA,Math.max(0,sim.v-physicalPrevious.v)/dt);metrics.maxAlpha=Math.max(metrics.maxAlpha,Math.abs(sim.w-physicalPrevious.w)/dt);}for(let i=0;i<members.length;i++){const old=physicalPrevious.members[i];if(old)metrics.maxMemberStep=Math.max(metrics.maxMemberStep,distance(members[i],old));}}
  physicalPrevious={task:sim.taskId,t:sim.time,v:sim.v,w:sim.w,phase:s.phase,members:members.map(m=>({...m}))};
 }
 `,ctx);
 return {ctx,evaluate:code=>vm.runInContext(code,ctx)};
}
module.exports={createRuntime};
