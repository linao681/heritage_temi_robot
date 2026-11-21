'use strict';
const $=id=>document.getElementById(id);
const CELL=.2,clearance=.40;
const navPoint=p=>({x:Math.round((p.x+PLAN_W/2)/CELL)*CELL-PLAN_W/2,z:Math.round((p.z+PLAN_D/2)/CELL)*CELL-PLAN_D/2});
let zones,ENTRY,ENTRY_QUEUE,EXIT,ENTRY_YAW,fixtures,approach;
function refreshMapBindings(){
 zones=PLAN_ZONES.map((p,i)=>({name:p.label,short:['概览','工艺','作品','传承','互动'][i],...planPoint(...p.exhibit),goal:navPoint(planPoint(...p.goal)),topic:['先认识非遗，再走近手艺','看见一件作品的制作过程','用细节读懂作品','让技艺被看见，也被学会','把发现变成一次观察回顾'][i]}));
 ENTRY=navPoint(planPoint(...PLAN_WAIT));const portal=PLAN_PORTALS.entry;
 ENTRY_QUEUE={...planPoint(...portal.pixel)};ENTRY_QUEUE.z+=portal.outward*.4;
 EXIT=navPoint(planPoint(...PLAN_PORTALS.exit.pixel));ENTRY_YAW=Math.atan2(ENTRY_QUEUE.x-ENTRY.x,ENTRY_QUEUE.z-ENTRY.z);
 fixtures=MAP_FIXTURES;approach=PLAN_APPROACH.map(list=>list.map(p=>navPoint(planPoint(...p))));
}
refreshMapBindings();
const grid=p=>({i:Math.round((p.x+PLAN_W/2)/CELL),j:Math.round((p.z+PLAN_D/2)/CELL)});
const world=p=>({x:p.i*CELL-PLAN_W/2,z:p.j*CELL-PLAN_D/2});
const key=p=>p.i+','+p.j;
function overlaps(point,box,radius){return fixtureDistance(point,box)<radius;}
function walkable(point,obstacles=[],radius=clearance){
 return Math.abs(point.x)<PLAN_W/2-.2&&point.z>-PLAN_D/2-.05&&point.z<PLAN_D/2+.05
  &&!fixtures.some(box=>overlaps(point,box,radius))&&!obstacles.some(box=>overlaps(point,box,radius));
}
function blocked(p,obstacles=[]){return !walkable(world(p),obstacles);}
function segmentClear(a,b,obstacles){
 const samples=Math.max(1,Math.ceil(Math.hypot(b.x-a.x,b.z-a.z)/.10));
 for(let i=0;i<=samples;i++){
  const t=i/samples;
  if(!walkable({x:a.x+(b.x-a.x)*t,z:a.z+(b.z-a.z)*t},obstacles))return false;
 }
 return true;
}
function findPath(from,to,obstacles=[],occupied=new Set()){
 const start=grid(from),end=grid(to);if(blocked(end,obstacles)||blocked(start,obstacles))return [];
 const heap=[],cost=new Map([[key(start),0]]),prev=new Map();let serial=0;
 const less=(a,b)=>a.f<b.f||(a.f===b.f&&a.serial<b.serial);
 function push(node){node.serial=serial++;heap.push(node);let i=heap.length-1;while(i>0){const parent=(i-1)>>1;if(!less(heap[i],heap[parent]))break;[heap[i],heap[parent]]=[heap[parent],heap[i]];i=parent;}}
 function pop(){const head=heap[0],tail=heap.pop();if(heap.length){heap[0]=tail;let i=0;while(true){let j=i*2+1;if(j>=heap.length)break;if(j+1<heap.length&&less(heap[j+1],heap[j]))j++;if(!less(heap[j],heap[i]))break;[heap[i],heap[j]]=[heap[j],heap[i]];i=j;}}return head;}
 push({...start,g:0,f:Math.abs(start.i-end.i)+Math.abs(start.j-end.j)});
 while(heap.length){
  const c=pop();if(c.g!==cost.get(key(c)))continue;
  if(key(c)===key(end)){const out=[world(c)];let k=key(c);while(prev.has(k)){const p=prev.get(k);out.unshift(world(p));k=key(p);}return out;}
  for(const [di,dj] of [[1,0],[0,-1],[-1,0],[0,1]]){
   const p={i:c.i+di,j:c.j+dj},k=key(p),g=c.g+1;
   if(occupied.has(k)||blocked(p,obstacles)||g>=(cost.get(k)??Infinity))continue;
   cost.set(k,g);prev.set(k,c);push({...p,g,f:g+Math.abs(p.i-end.i)+Math.abs(p.j-end.j)});
  }
 }return [];
}

let scene,camera,planCamera,renderer,robot,routeGroup,obstacleGroup;
let sceneListeners,resizeObserver,clock,contextLost=false;
let viewportWidth=1,viewportHeight=1,needsDraw=true;
let visitorModels=[],zoneLabels=[],wheelModels=[];
let s,sceneReady=false,cameraMode='overview',cameraAim;
const orbit={theta:.61,phi:.64,radius:36},drag={active:false,x:0,y:0};
const mats={};
function material(color,extra={}){return new THREE.MeshStandardMaterial({color,roughness:.75,...extra});}
function mesh(geometry,mat,parent,x=0,y=0,z=0){const m=new THREE.Mesh(geometry,mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;}
function box(w,h,d,mat,parent,x=0,y=0,z=0){return mesh(new THREE.BoxGeometry(w,h,d),mat,parent,x,y,z);}
function cylinder(r1,r2,h,mat,parent,x=0,y=0,z=0){return mesh(new THREE.CylinderGeometry(r1,r2,h,32),mat,parent,x,y,z);}
function sphere(r,mat,parent,x=0,y=0,z=0){return mesh(new THREE.SphereGeometry(r,20,12),mat,parent,x,y,z);}
function label(text, position, className='zone-label') {
 const element=document.createElement('div');
 element.className=className;
 element.textContent=text;
 $('labels').append(element);
 zoneLabels.push({element,position});
}
function visitor(color,height){return createVisitor(color,height);}
function initScene(){
 if(sceneReady)return;
 if(typeof SimulationClock!=='function'||typeof TourTrail!=='function')throw Error('缺少运动模块，请检查 motion.js。');
 if(typeof THREE==='undefined')throw Error('缺少本地三维显示库，请完整解压文件夹后打开。');
 renderer=new THREE.WebGLRenderer({canvas:$('scene'),antialias:true,alpha:false,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.75));renderer.setClearColor(0xccc7bd);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.12;
 scene=new THREE.Scene();scene.background=new THREE.Color(0xccc7bd);scene.fog=new THREE.Fog(0xccc7bd,48,85);camera=new THREE.PerspectiveCamera(54,1,.1,120);camera.position.set(-12.3,2.35,9.3);cameraAim=new THREE.Vector3(-1,1.5,-2);
 planCamera=new THREE.OrthographicCamera(-1,1,1,-1,.1,100);planCamera.position.set(0,50,0);planCamera.up.set(0,0,-1);planCamera.lookAt(0,0,0);
 setupMaterials();
 scene.add(new THREE.HemisphereLight(0xfff4df,0x9ca4b3,1.45));scene.add(new THREE.AmbientLight(0xffffff,.85));
 const sun=new THREE.DirectionalLight(0xfff5e7,1.7);sun.position.set(-8,17,10);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);
 Object.assign(sun.shadow.camera,{left:-24,right:24,top:20,bottom:-20,near:1,far:55});sun.shadow.bias=-.0004;sun.shadow.normalBias=.025;scene.add(sun);
 for(const x of [-8,7]){const lamp=new THREE.PointLight(0xffdca7,1.8,16,2);lamp.position.set(x,3.6,-4);scene.add(lamp);}
 zones.forEach(buildZone);
 buildHall();cacheFixtureBounds();batchStaticScene();

 robot=buildRobot();routeGroup=new THREE.Group();scene.add(routeGroup);obstacleGroup=new THREE.Group();scene.add(obstacleGroup);
 visitorModels=[visitor(0xbd7352,1.58),visitor(0x839b79,1.52),visitor(0xba9a55,1.02)];
 for(const actor of [robot,...visitorModels]) actor.traverse(object=>{object.castShadow=false;});
 renderer.shadowMap.autoUpdate=false;
 renderer.shadowMap.needsUpdate=true;
 sceneReady=true;
 resize();
 resizeObserver=new ResizeObserver(resize);
 resizeObserver.observe($('viewport'));
 sceneListeners=new AbortController();
 const canvas=$('scene');
 const listen=(name,handler,options={})=>canvas.addEventListener(name,handler,{...options,signal:sceneListeners.signal});
 listen('webglcontextlost',event=>{
  event.preventDefault();contextLost=true;clock?.stop();
  if(!s.paused&&!['idle','done','ended'].includes(s.phase))pause();
  runtimeMessage('图形连接中断，等待浏览器恢复。');
 });
 listen('webglcontextrestored',()=>{
  contextLost=false;needsDraw=true;renderer.shadowMap.needsUpdate=true;
  $('webgl-error').hidden=true;clock?.start();
 });
 listen('pointerdown',e=>{drag.active=true;drag.x=e.clientX;drag.y=e.clientY;$('scene').setPointerCapture(e.pointerId);if(cameraMode!=='orbit'){orbit.theta=Math.atan2(camera.position.x-cameraAim.x,camera.position.z-cameraAim.z);const v=camera.position.clone().sub(cameraAim);orbit.radius=v.length();orbit.phi=Math.acos(v.y/orbit.radius);}selectCamera('orbit',true);});
 listen('pointermove',e=>{if(!drag.active)return;orbit.theta-=(e.clientX-drag.x)*.006;orbit.phi=Math.max(.18,Math.min(1.35,orbit.phi+(e.clientY-drag.y)*.005));drag.x=e.clientX;drag.y=e.clientY;});
 listen('pointerup',()=>drag.active=false);listen('pointercancel',()=>drag.active=false);
 listen('lostpointercapture',()=>drag.active=false);
 listen('wheel',e=>{e.preventDefault();if(cameraMode!=='orbit'){const v=camera.position.clone().sub(cameraAim);orbit.radius=v.length();orbit.theta=Math.atan2(v.x,v.z);orbit.phi=Math.acos(v.y/orbit.radius);selectCamera('orbit',true);}orbit.radius=Math.max(6,Math.min(55,orbit.radius+e.deltaY*.025));},{passive:false});
}
function resize(){
 if(!renderer||contextLost)return;
 const rect=$('viewport').getBoundingClientRect();
 if(rect.width<1||rect.height<1)return;
 viewportWidth=rect.width;viewportHeight=rect.height;
 renderer.setSize(viewportWidth,viewportHeight,false);
 camera.aspect=viewportWidth/viewportHeight;camera.updateProjectionMatrix();
 needsDraw=true;
}
function disposeGroup(group){while(group.children.length){const c=group.children[0];group.remove(c);if(c.geometry)c.geometry.dispose();if(c.userData.disposeMaterial)c.material.dispose();}}
function drawRoute(){if(!sceneReady)return;disposeGroup(routeGroup);if(s.phase==='feedback')return;const points=[{...s.pos},...s.path];if(points.length<2)return;const geometry=new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(p.x,.065,p.z)));const line=new THREE.Line(geometry,new THREE.LineDashedMaterial({color:0xd3a657,dashSize:.19,gapSize:.12}));line.computeLineDistances();line.userData.disposeMaterial=true;routeGroup.add(line);for(let i=2;i<points.length;i+=4){const p=points[i];const disc=mesh(new THREE.CircleGeometry(.065,10),new THREE.MeshBasicMaterial({color:0xe7c88b,side:THREE.DoubleSide}),routeGroup,p.x,.068,p.z);disc.rotation.x=-Math.PI/2;disc.userData.disposeMaterial=true;}}
function drawObstacles(){if(!sceneReady)return;disposeGroup(obstacleGroup);for(const b of s.obstacles){box(b.w, .09,b.d,mats.red,obstacleGroup,b.x,.07,b.z);for(const x of [-b.w/2+.14,b.w/2-.14]){cylinder(.07,.11,.65,mats.gold,obstacleGroup,b.x+x,.38,b.z);cylinder(.12,.12,.08,mats.tire,obstacleGroup,b.x+x,.1,b.z);}box(b.w,.17,.09,mats.red,obstacleGroup,b.x,.68,b.z);}}
function selectCamera(mode,manual=false){cameraMode=mode;needsDraw=true;if(manual)$('auto-camera').checked=false;document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===mode));}


function turnActor(model,yaw,dt){
 const difference=Math.atan2(Math.sin(yaw-model.rotation.y),Math.cos(yaw-model.rotation.y));
 model.rotation.y+=difference*Math.min(1,dt*10);
}
function updateScene(dt){
 if(!sceneReady||contextLost||!s)return;
 const target=new THREE.Vector3(),position=new THREE.Vector3();
 if(ceilingGroup)ceilingGroup.visible=cameraMode!=='overview'&&camera.position.y<4.05;
 if(zoneFloorGroup){zoneFloorGroup.visible=true;for(const o of zoneFloorGroup.children)if(o.isMesh)o.material.opacity=cameraMode==='overview'?.70:.42;}
 if(floorReflection)floorReflection.plane.visible=cameraMode!=='overview';
 if(recommendedRouteGroup)recommendedRouteGroup.visible=cameraMode==='overview';
 camera.up.set(0,1,0);
 if(cameraMode==='hall'){
  target.fromArray(activeMap.hall.target);position.fromArray(activeMap.hall.position);
 }else if(cameraMode==='overview'){
  target.set(0,.45,0);const fit=Math.max(PLAN_D,PLAN_W/camera.aspect)*1.12;position.set(0,fit/(2*Math.tan(THREE.MathUtils.degToRad(camera.fov/2))),.03);camera.up.set(0,0,-1);
 }else if(['exhibit','follow','robot'].includes(cameraMode)){
  const fit=fitServiceCamera(cameraMode);target.copy(fit.target);position.copy(fit.position);
 }
 else{target.copy(cameraAim);position.set(target.x+Math.sin(orbit.theta)*Math.sin(orbit.phi)*orbit.radius,target.y+Math.cos(orbit.phi)*orbit.radius,target.z+Math.cos(orbit.theta)*Math.sin(orbit.phi)*orbit.radius);}
 const movingCamera=camera.position.distanceToSquared(position)>.0001||cameraAim.distanceToSquared(target)>.0001;
 if(!movingCamera&&!needsDraw)return;
 const speed=movingCamera?1-Math.exp(-dt*2.1):1;
 if(['exhibit','follow','robot'].includes(cameraMode)){camera.position.copy(position);cameraAim.copy(target);}else{camera.position.lerp(position,speed);cameraAim.lerp(target,speed);}camera.lookAt(cameraAim);
 const view=cameraMode==='overview'?planCamera:camera;
 if(cameraMode==='overview'){
  const height=Math.max(PLAN_D,PLAN_W/camera.aspect)*1.07;
  Object.assign(planCamera,{left:-height*camera.aspect/2,right:height*camera.aspect/2,top:height/2,bottom:-height/2});planCamera.updateProjectionMatrix();planCamera.updateMatrixWorld();
 }
 renderer.render(scene,view);
 needsDraw=false;
 for(const [i,label] of zoneLabels.entries()){const v=label.position.clone().project(view);label.element.style.left=(v.x*.5+.5)*viewportWidth+'px';label.element.style.top=(-v.y*.5+.5)*viewportHeight+'px';label.element.style.display=(v.z>1||v.z< -1||Math.abs(v.x)>1.1||Math.abs(v.y)>1.1)?'none':'';label.element.classList.toggle('active',i<5&&s.index===i&&!['idle','done','ended'].includes(s.phase));}
}
const states={confirming:'等待人数确认',docking:'到点停稳',crowd_wait:'等待行人通过',perception:'感知受限 · 已停车',ended:'服务已结束',idle:'入口待命',greeting:'接待与确认',moving:'导览中',speaking:'停靠讲解',question:'问答中',manual:'等待人工协助',lost:'定位丢失 · 已停车',blocked:'路线受阻 · 已停车',estop:'急停已触发',feedback:'结束与反馈',done:'已到达出口'};
function log(text){if(typeof sim!=='undefined'){sim.records.push({t:Number(sim.time.toFixed(3)),phase:s?.phase||'idle',zone:s?.index<5?s.index+1:null,message:text});if(sim.records.length>MODEL.performance.maxEvents){sim.records.shift();sim.droppedEvents++;}}const p=document.createElement('p'),t=document.createElement('time');t.textContent=new Date().toLocaleTimeString('zh-CN',{hour12:false});p.append(t,document.createTextNode(text));$('log').prepend(p);while($('log').children.length>60)$('log').lastChild.remove();}
let toastTimer;
function toast(text){$('toast').textContent=text;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3000);}
function silence(){if('speechSynthesis'in window)speechSynthesis.cancel();}
function speak(text){silence();if($('voice').checked&&'speechSynthesis'in window){const u=new SpeechSynthesisUtterance(text);u.lang='zh-CN';u.rate=1;speechSynthesis.speak(u);}}
function show(chapter,title,text,source='流程依据：方案流程 · 本地交互演示'){ $('chapter').textContent=chapter;$('title').textContent=title;$('speech').textContent=text;$('source').textContent=source;speak(text);}
function renderUI(){
 needsDraw=true;
 const active=!['idle','done','ended'].includes(s.phase),halted=['manual','lost','blocked','estop','perception','crowd_wait'].includes(s.phase);
 const explaining=['speaking','question'].includes(s.phase)&&s.questionReturn!=='moving';
 $('interact').disabled=!sceneReady||s.paused||s.index>=5||!explaining;
 $('status').textContent=s.paused?'导览已暂停':states[s.phase];$('status-dot').style.background=halted?'#b1573e':'#b58d50';$('count').textContent=String(s.visited.size).padStart(2,'0');
 $('start').disabled=active||!sceneReady||s.phase==='ended';$('auto').disabled=$('start').disabled;
 $('pause').disabled=!active||!!s.endRequest;$('pause').textContent=s.paused?'继续':'暂停';$('end-tour').disabled=!active;
 $('next').disabled=s.paused||!['speaking','question','feedback'].includes(s.phase);
 $('next').textContent=s.questionReturn==='moving'?'回答完毕，继续行进 →':s.phase==='feedback'?'结束讲解，前往服务终点 →':'继续下一展区 →';
 $('repeat').disabled=s.paused||!explaining;$('skip').disabled=s.paused||s.index>=5||!['moving','speaking','question','blocked'].includes(s.phase);
 $('block').disabled=s.paused||s.phase!=='moving';$('crowd').disabled=$('block').disabled||!!s.crowd;$('clear').disabled=!s.obstacles.length&&!s.crowd&&!trafficPeople().length;$('traffic-inject').disabled=s.paused||!(s.phase==='moving'||$('traffic-type').value==='occlusion'&&['speaking','question'].includes(s.phase))||!!s.crowd||!!trafficPeople().length;
 for(const id of ['lost','human','glass'])$(id).disabled=s.paused||!active||halted;
 $('estop').disabled=!active||s.phase==='estop';$('resume').disabled=s.paused||!['manual','lost','blocked','estop','perception'].includes(s.phase);
 $('audience').disabled=s.accepted;$('party-size').disabled=s.accepted||$('audience').value==='individual';$('mode-badge').textContent=$('mode').selectedOptions[0].textContent;
 $('reception').hidden=s.phase!=='greeting';$('group-confirm').hidden=s.phase!=='confirming';
 $('accept-tour').disabled=s.paused;$('decline-tour').disabled=s.paused;$('confirm-party').disabled=s.paused;
 const canAsk=!s.paused&&['moving','speaking','question'].includes(s.phase);
 $('question').disabled=!canAsk;$('send-question').disabled=!canAsk;document.querySelectorAll('[data-q]').forEach(b=>b.disabled=!canAsk);
 $('task').textContent=s.phase==='idle'?'入口待命':s.phase==='ended'?'任务已终止':s.phase==='done'?'任务完成':s.index<5?zones[s.index].name:'前往出口';
 $('ticket').textContent=s.handoff?.status==='pending'?'人工协助待确认':halted?'等待安全恢复':'无待办';
 document.querySelectorAll('.stop').forEach((e,i)=>{e.classList.toggle('active',active&&s.index===i);e.classList.toggle('visited',s.visited.has(i));});
 renderHandoff();renderEngineeringUI();renderUpgradeUI();
}

function acceptTour(){
 if(s.phase!=='greeting'||s.paused||s.faults.length||s.stopRequest)return;
 s.phase='confirming';s.elapsed=0;
 show('02 / 人数确认','请确认游客类型与人数','选择散客、小团体或亲子游客，再确认本次人数。人数确认前不会开始移动。');
 log('游客接受导览 → 等待人数确认');renderUI();
}



function reset(){resetTelemetry();silence();s={phase:'idle',paused:false,accepted:false,partyCount:0,party:{type:'unconfirmed',members:[]},entrants:[],reception:null,questionReturn:null,handoff:null,crowd:null,confidence:1,speed:.8,index:0,pos:{...ENTRY},yaw:ENTRY_YAW,path:[],obstacles:[],visited:new Set(),trail:typeof TourTrail==='function'?new TourTrail(ENTRY):null,followers:[],distanceMoved:false,autoAssist:false,auto:false,waypoint:0,elapsed:0,obstacleDone:false,questionDone:false,humanDone:false,resumePhase:null,faults:[],endRequest:null,regroup:null,lowBatteryHandled:false,serviceOutcome:null,serviceEndedAt:null};resetUpgrade();setVisitorVisibility();$('log').replaceChildren();show('01 / 接待与确认','您好，我是非遗智导','点击“游客到来”模拟入口到访，再决定是否需要导览并确认人数。确认后按五区固定路线参观；可途中提问、暂停或结束。' ,'依据赛题图 2 拓扑搭建 · 几何尺寸与展项为示意');if(sceneReady){drawRoute();drawObstacles();robot.position.set(ENTRY.x,0,ENTRY.z);robot.rotation.y=ENTRY_YAW;}if(sceneReady){
  updateFollowers(0);
  visitorModels.forEach((model,i)=>{const p=s.party.members[i];if(p){model.position.set(p.x,0,p.z);model.rotation.y=p.yaw;}});
  updateActors(0);
 }
 clock?.rebase();
 selectCamera('overview');log('系统待命 · 固定主线与五个停靠点已加载');renderUI();}

function goal(){return s.parking?.target||zones[s.index]?.goal||EXIT;}


function travel(){
 if(s.faults.length||s.stopRequest){toast('请先完成安全处置，再恢复导览');return;}
 if(!s.accepted&&s.index<5){toast('请先接受导览并确认人数');return;}
 silence();s.questionReturn=null;s.phase='moving';s.elapsed=0;
 if(plan()){
  show('03 / 导览引导',s.index<5?'前往'+zones[s.index].name:'前往出口',s.index<5?'请保持队形，跟随我前往下一展区。窄通道和展柜旁会减速；到点后先停稳再讲解。途中提问时我会先停车。':'感谢参观。我将前往出口，完成送别与本次任务。','固定五区主线 / 栅格路径 / 本地碰撞约束');
  log('开始移动 → '+(zones[s.index]?.name||'出口'));
 }cameraForPhase();renderUI();
}
function renderSources(ids){
 $('source').replaceChildren();
 for(const id of new Set(ids)){
  const source=GUIDE_SOURCES[id],node=document.createElement(source.url?'a':'span');node.textContent=source.label+' ';
  if(source.url){node.href=source.url;node.target='_blank';node.rel='noopener noreferrer';}
  $('source').append(node);
 }
}
function explanation(){
 if(s.index>=5)return;
 const z=zones[s.index];s.questionReturn=null;
 show('04 / 展区 '+String(s.index+1).padStart(2,'0')+' · '+z.name,z.topic,guideText(s.index,$('mode').value),'通用科普与观察任务，具体馆藏信息需场馆核实');
 renderSources(GUIDE_CARDS[s.index].map(p=>p.source));
}

function next(){if(s.paused)return;if(s.phase==='question'&&s.questionReturn==='moving'){travel();return;}if(s.phase==='feedback'){s.index=5;travel();return;}if(!['speaking','question'].includes(s.phase))return;s.questionReturn=null;s.approachOverride=null;s.index++;s.waypoint=0;if(s.index===5){s.phase='feedback';s.elapsed=0;show('07 / 结束与反馈','今天，您发现了什么？','五个展区的参观已结束。您可以回顾最喜欢的工艺或纹样；真实场馆可在游客自愿的前提下收集意见。接下来前往出口服务区结束机器人导览；到达后您可选择自由参观或自行离馆。','方案流程 · 结束反馈 → 出口');log('五区讲解结束 → 反馈与服务终点；游客去向待本人选择');renderUI();cameraForPhase();}else travel();}
function skip(){
 if($('skip').disabled)return;hardStop();
 const safeTransit=(s.phase==='moving'||s.questionReturn==='moving')?[...approach[s.index].slice(s.waypoint),zones[s.index].goal]:null;
 log('游客请求跳过 → '+zones[s.index].name);
 s.index++;
 s.approachOverride=safeTransit;
 s.waypoint=0;
 if(s.index<5){travel();return;}
 s.phase='feedback';s.elapsed=0;s.path=s.path.slice(0,1);
 drawRoute();cameraForPhase();
 show('07 / 结束与反馈','本次导览即将结束','您已跳过最后一个展区。可以选择结束并前往出口。');
 renderUI();
}

function addObstacle(){
 if(s.phase!=='moving'||s.paused||s.obstacles.length)return;
 let before=s.pos,p=null,total=0;
 for(const end of s.path){const d=distance(before,end);if(total+d>=2.2){const t=(2.2-total)/d;p={x:before.x+(end.x-before.x)*t,z:before.z+(end.z-before.z)*t};break;}total+=d;before=end;}
 if(!p||distance(p,goal())<1.6){toast('当前路段太短，请在下一段注入障碍');return;}
 const obstacle={...p,w:.8,d:.65};
 if(s.party.members.some(m=>overlaps(m,obstacle,clearance))||overlaps(s.pos,obstacle,clearance)){toast('该位置仍有队伍，不能放置障碍');return;}
 hardStop();s.obstacles.push(obstacle);log('静态障碍注入 → 保留原展区，重新检查机器人和实际队列路线');
 if(plan()){log('静态局部绕行路线已找到 → 继续导览');toast('已重新规划安全路线');}
 drawObstacles();renderUI();
}





$('auto').onclick=()=>start(true);$('start').onclick=()=>start(false);$('pause').onclick=()=>pause();$('end-tour').onclick=()=>endTour();$('accept-tour').onclick=()=>acceptTour();$('decline-tour').onclick=()=>declineTour();$('confirm-party').onclick=()=>confirmParty();$('reset').onclick=()=>{if(sceneReady&&!contextLost){reset();clock.start();}else if(!contextLost)boot();};$('next').onclick=next;$('skip').onclick=skip;$('repeat').onclick=()=>{if(!$('repeat').disabled){s.phase='speaking';s.elapsed=0;explanation();renderUI();}};
$('block').onclick=addObstacle;$('lost').onclick=()=>injectLocalizationLoss();$('human').onclick=()=>interrupt('manual');$('estop').onclick=()=>interrupt('estop');
$('mode').onchange=()=>{if(s.phase==='speaking'||(s.phase==='question'&&s.questionReturn!=='moving')){s.phase='speaking';s.elapsed=0;explanation();}log('讲解切换 → '+$('mode').selectedOptions[0].textContent);renderUI();};
$('audience').onchange=()=>{if($('audience').value==='family')$('mode').value='child';if($('audience').value==='individual')$('party-size').value='1';setVisitorVisibility();renderUI();};
$('party-size').onchange=()=>{setVisitorVisibility();renderUI();};
$('voice').onchange=()=>{$('voice').checked?speak($('speech').textContent):silence();};$('question-form').onsubmit=e=>{e.preventDefault();ask($('question').value);};document.querySelectorAll('[data-q]').forEach(b=>b.onclick=()=>ask(b.dataset.q));document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>selectCamera(b.dataset.view,true));$('auto-camera').onchange=()=>cameraForPhase();
$('record-mode').onclick=()=>{document.body.classList.add('recording');resize();toast('录屏视图已开启，按 Esc 退出');};document.addEventListener('keydown',e=>{if(e.key==='Escape'){document.body.classList.remove('recording');resize();}});function suspendTour(){
 drag.active=false;
 clock?.rebase();
 if(s&&!s.paused&&!['idle','done','ended'].includes(s.phase))pause();
}
window.addEventListener('blur',suspendTour);
document.addEventListener('visibilitychange',()=>{
 if(document.hidden){suspendTour();clock?.stop();}
 else if(sceneReady&&!contextLost)clock?.start();
});
window.addEventListener('pagehide',event=>{
 if(event.persisted){suspendTour();clock?.stop();}
 else disposeScene();
});
window.addEventListener('pageshow',()=>{if(sceneReady&&!contextLost)clock?.start();});
zones.forEach((z,i)=>{const div=document.createElement('div');div.className='stop';const n=document.createElement('i');n.textContent=i+1;div.append(n,document.createTextNode(z.short));$('tour-stops').append(div);});
function runtimeMessage(message,error){
 $('webgl-error').hidden=false;
 $('error-detail').textContent=error?message+' '+error.message:message;
}
function disposeScene(){
 clock?.stop();silence();clearTimeout(toastTimer);
 sceneListeners?.abort();resizeObserver?.disconnect();
 drag.active=false;
 const geometries=new Set(),materials=new Set(),textures=new Set();
 scene?.traverse(object=>{
  if(object.geometry)geometries.add(object.geometry);
  for(const item of [].concat(object.material||[]))materials.add(item);
  if(object.isLight&&object.shadow)object.shadow.dispose();
 });
 for(const material of materials){
  for(const value of Object.values(material))if(value?.isTexture)textures.add(value);
  material.dispose();
 }
 for(const geometry of geometries)geometry.dispose();
 for(const texture of textures)texture.dispose();
 renderer?.dispose();visitorResources=null;
 renderer=null;scene=null;sceneReady=false;
 visitorModels=[];wheelModels=[];zoneLabels=[];
 $('labels').replaceChildren();
}
function boot(){
 if(sceneReady)return;
 try{
  initScene();
  clock=new SimulationClock(dt=>{
   const previousPhase=s.phase;
   step(dt);
   if(freeVisitors.length||!['idle','done','ended'].includes(s.phase)||s.phase!==previousPhase)updateActors(dt);
  },updateScene,error=>{
   disposeScene();
   runtimeMessage('画面运行中断，可点“重置”重新初始化。',error);
   renderUI();
  });
  reset();
  $('webgl-error').hidden=true;
  if(!document.hidden)clock.start();
 }catch(error){
  disposeScene();
  reset();
  runtimeMessage('三维场景初始化失败。',error);
 }
}
// Booted after the simulation instrumentation is installed.
