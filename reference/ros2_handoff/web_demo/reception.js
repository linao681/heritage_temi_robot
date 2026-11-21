'use strict';
// Buttons create actors only. Range/bearing observations, tracking and stability drive reception.
let freeVisitors=[];
function clearFreeVisitors(){
 const geometries=new Set(),materials=new Set(),textures=new Set(),removed=freeVisitors.map(a=>a.model);
 for(const model of removed)model.removeFromParent();
 const keepMaterial=m=>{if(!m)return;materials.add(m);for(const value of Object.values(m))if(value?.isTexture)textures.add(value);};
 // Avatars share primitive geometry and clothing materials, but own their hair,
 // curves, shadow planes and queue rings. Removing a root alone leaks GPU buffers.
 if(visitorResources){
  for(const name of ['sphere','capsule','torso'])geometries.add(visitorResources[name]);
  keepMaterial(visitorResources.shadowMaterial);for(const style of visitorResources.styles.values())for(const m of Object.values(style))keepMaterial(m);
 }
 scene?.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of [].concat(o.material||[]))keepMaterial(m);});
 const deadGeometry=new Set(),deadMaterials=new Set(),deadTextures=new Set();
 for(const model of removed)model.traverse(o=>{
  if(o.geometry&&!geometries.has(o.geometry))deadGeometry.add(o.geometry);
  for(const m of [].concat(o.material||[]))if(!materials.has(m)){deadMaterials.add(m);for(const value of Object.values(m))if(value?.isTexture&&!textures.has(value))deadTextures.add(value);}
 });
 for(const g of deadGeometry)g.dispose();for(const m of deadMaterials)m.dispose();for(const t of deadTextures)t.dispose();
 freeVisitors=[];
}
function resetReception(){s.entrants=[];s.reception={tracks:[],nextTrack:1,stableFor:0,lastCount:0,count:0,greeted:false,greetings:0,departing:false};}
function setVisitorVisibility(){
 const actors=s.accepted?s.party.members:s.entrants;
 visitorModels.forEach((model,i)=>{const a=actors.find(a=>a.index===i);model.visible=!!a&&a.active!==false;if(!a)return;model.scale.setScalar((a.role==='child'?1.02:i===0?1.58:1.52)/1.4);setVisitorRole(model,a.role||'adult');model.position.set(a.x,0,a.z);model.userData.queueMarker.visible=!!a.straggler;});
}
function spawnVisitors(count=1,options={}){
 if(!sceneReady||!['idle','arriving','greeting','confirming'].includes(s.phase)||s.reception.departing)return false;
 s.entrants=s.entrants.filter(a=>a.active!==false);
 const slots=[0,1,2].filter(i=>!s.entrants.some(a=>a.index===i));
 const available=slots.length;count=Math.max(1,count);if(!available)return false;
 if(count>available){toast('本次接待最多3人，当前还可追加 '+available+' 人；请减少入场人数');return false;}
 const portal=PLAN_PORTALS.entry,p=planPoint(...portal.pixel),out=portal.outward;
 const waiting=[...s.entrants,...freeVisitors,...trafficPeople()];
 for(let j=0;j<count;j++){
  const lane=[-.68,0,.68][slots[j]]*out,pos={x:p.x+lane*.65,z:p.z+out*(1.8+j*.8)};
  if(waiting.some(a=>a.active!==false&&distance(pos,a)<.60)){toast('入口仍有游客通行，请稍后追加');return false;}
 }
 for(let j=0;j<count;j++){
  const index=slots[j],lane=[-.68,0,.68][index]*out,stage={x:ENTRY.x+lane,z:ENTRY.z+out*1.85};
  const outside={x:p.x+lane*.65,z:p.z+out*(1.8+j*.8)};
  const target=options.outsideFov?{x:ENTRY.x,z:ENTRY.z-out*2}:stage;
  const actor={index,actorId:'actor-'+index,x:outside.x,z:outside.z,yaw:out>0?Math.PI:0,active:true,role:'adult',speed:.65,walked:0,delay:options.delay||j*1.1,transient:!!options.transient,stage,target,path:[{x:p.x+lane*.65,z:p.z-out*.3},target]};
  if(options.outsideFov){actor.x=target.x;actor.z=target.z;actor.path=[];}
  s.entrants.push(actor);
 }
 s.phase=s.reception.greeted?s.phase:'arriving';s.elapsed=0;setVisitorVisibility();cameraForPhase();renderUI();
 log('模拟游客实体入场 → '+count+' 人；等待视场、遮挡与稳定检测');return true;
}
function start(automatic=false){
 if(!sceneReady)return;
 if(s.phase==='done'){toast('本轮已完成；留馆游客继续参观。开始新一轮请显式点击“重新开始”。');return;}
 if(s.phase!=='idle'||s.faults.length||s.stopRequest)return;
 if(sim.battery<=MODEL.battery.low){toast('电量不足，请重置模拟充电后开始');return;}
 if(!spawnVisitors(Number($('arrival-count').value)||1))return;
 s.auto=automatic;sim.testMode=automatic?($('demo-speed').value==='fast'?'fast-demo':'full-demo'):'interactive';
 if(clock)clock.simRate=sim.testMode==='fast-demo'?3:1;sim.startedWall=performance.now();renderUI();
}
function receptionWalkable(p){
 const exit=PLAN_PORTALS.exit,e=planPoint(...exit.pixel);
 if((p.z-e.z)*exit.outward>-.25&&Math.abs(p.x-e.x)<1.08&&Math.abs(p.z-e.z)<4)return ![...fixtures,...s.obstacles].some(b=>overlaps(p,b,.27));
 const portal=PLAN_PORTALS.entry,q=planPoint(...portal.pixel),outside=(p.z-q.z)*portal.outward>-.25;
 if(outside&&Math.abs(p.x-q.x)<1.08&&Math.abs(p.z-q.z)<4)return true;
 return walkable(p,s.obstacles,.27);
}
function moveEntrant(a,dt){
 a.moving=false;if(a.active===false)return;if(a.delay>0){a.delay-=dt;return;}
 if(!a.path.length){
  if(a.transient&&!a.leaving){a.leaving=true;const p=planPoint(...PLAN_PORTALS.entry.pixel);a.path=[{x:p.x,z:p.z+PLAN_PORTALS.entry.outward*2}];}
  else if(a.leaving){a.active=false;setVisitorVisibility();}return;
 }
 const target=a.path[0],d=distance(a,target);if(d<.0001){a.path.shift();return;}
 const step=Math.min(d,a.speed*dt),p={x:a.x+(target.x-a.x)*step/d,z:a.z+(target.z-a.z)*step/d};
 const other=[...s.entrants,...freeVisitors,...trafficPeople()].filter(b=>b!==a&&b.active!==false);
 if(!receptionWalkable(p)||distance(p,s.pos)<.90||other.some(b=>distance(p,b)<(s.phase==='forming'&&freeVisitors.includes(b)?.67:.55))){
  for(const b of freeVisitors)if(distance(p,b)<.85)b.entryYieldUntil=sim.time+3;
  return;
 }
 a.yaw=Math.atan2(p.x-a.x,p.z-a.z);a.walked+=step;Object.assign(a,p);a.moving=true;
}
function receptionObservations(){
 const observations=[];
 for(const a of s.entrants){
  if(a.active===false||a.leaving)continue;
  const d=distance(s.pos,a),bearing=Math.atan2(a.x-s.pos.x,a.z-s.pos.z),angle=angleDiff(bearing,s.yaw);
  const portal=planPoint(...PLAN_PORTALS.entry.pixel);
  if((a.z-portal.z)*PLAN_PORTALS.entry.outward>-.12||d>MODEL.sensors.reception.maxRange||Math.abs(angle)>THREE.MathUtils.degToRad(MODEL.sensors.reception.fovDegrees/2))continue;
  if(rayDistance(s.pos,bearing,d+.01,s.obstacles)<d-.16)continue;
  const occluded=[...s.entrants,...freeVisitors].some(b=>b!==a&&b.active!==false&&distance(s.pos,b)<d-.3&&Math.abs(angleDiff(Math.atan2(b.x-s.pos.x,b.z-s.pos.z),bearing))<.07);
  if(occluded)continue;
  const measured=d+(sensorRandom()-.5)*.018,measuredAngle=bearing+(sensorRandom()-.5)*.004;
  observations.push({x:s.pos.x+Math.sin(measuredAngle)*measured,z:s.pos.z+Math.cos(measuredAngle)*measured});
 }
 return observations;
}
function updateReception(dt){
 if(s.phase==='forming'){updateFormation(dt);return;}
 for(const a of s.entrants)moveEntrant(a,dt);
 const r=s.reception;if(!r||s.accepted)return;
 const obs=receptionObservations(),used=new Set();
 for(const o of obs){
  let t=r.tracks.filter(t=>!used.has(t.id)&&sim.time-t.lastSeen<1.2&&distance(t,o)<.7).sort((a,b)=>distance(a,o)-distance(b,o))[0];
  if(!t){t={id:'track-'+r.nextTrack++,firstSeen:sim.time,anchor:{...o},anchorAt:sim.time,...o};r.tracks.push(t);}
  if(distance(t.anchor,o)>.10){t.anchor={...o};t.anchorAt=sim.time;}
  Object.assign(t,o,{lastSeen:sim.time});used.add(t.id);
 }
 r.tracks=r.tracks.filter(t=>sim.time-t.lastSeen<2);const live=r.tracks.filter(t=>sim.time-t.lastSeen<.22);
 r.count=live.length;r.stableFor=r.count>0&&r.count===r.lastCount&&live.every(t=>sim.time-t.anchorAt>.25)?r.stableFor+dt:0;r.lastCount=r.count;
 if(s.paused||s.faults.length||s.stopRequest||!['idle','arriving','greeting','confirming'].includes(s.phase))return;
 if(s.phase!=='idle'&&s.entrants.every(a=>a.active===false)){resetReception();s.phase='idle';s.auto=false;hardStop();setVisitorVisibility();show('01 / 入口待命','继续等待到访游客','路过游客已离开，未启动导览。');renderUI();return;}
 if(live.length&&['arriving','greeting','confirming'].includes(s.phase)){
  const center={x:live.reduce((v,t)=>v+t.x,0)/live.length,z:live.reduce((v,t)=>v+t.z,0)/live.length};
  const e=angleDiff(Math.atan2(center.x-s.pos.x,center.z-s.pos.z),s.yaw);sim.w=ramp(sim.w,Math.max(-.65,Math.min(.65,e*2)),MODEL.motion.alphaMax,dt);s.yaw=angleDiff(s.yaw+sim.w*dt,0);
 }
 if(r.stableFor>=1&&!r.greeted&&s.phase==='arriving'){
  r.greeted=true;r.greetings++;s.phase='greeting';s.elapsed=0;sim.w=0;
  $('party-size').value=String(r.count);show('01 / 自主迎宾','您好，需要导览服务吗？','检测到 '+r.count+' 位游客稳定进入接待视场。是否需要参观五个展区？','浏览器模拟：几何视场、遮挡、目标跟踪与稳定人数；未接入摄像头');
  sim.countObservations.push({t:sim.time,estimated:r.count,truth:s.entrants.filter(a=>a.active!==false&&!a.leaving).length,trackIds:live.map(t=>t.id)});log('稳定检测满 1 秒 → 主动迎宾 / '+r.count+' 人');renderUI();cameraForPhase();
 }
 if(r.stableFor>=1&&s.phase==='confirming'&&!s.manualCount)$('party-size').value=String(r.count);
 if(r.greeted&&r.count===0&&!r.departing){r.absent=(r.absent||0)+dt;if(r.absent>3){releaseReception('游客离开接待范围，取消未确认导览',false);}}else r.absent=0;
 if(!r.greeted&&r.count===0&&s.elapsed>10&&s.entrants.length&&s.entrants.every(a=>!a.path.length))releaseReception('未形成稳定接待，转为普通看展游客',false);
}
function releaseReception(reason,declined){
 const greeted=s.reception.greeted,leaving=s.entrants.filter(a=>a.active!==false&&a.leaving);
 for(const a of s.entrants.filter(a=>a.active!==false&&!a.leaving)){
  const id=freeVisitors.length,model=visitorModels[a.index];
  freeVisitors.push({...a,id:'free-'+id,model,declinedGuide:declined,leaving:false,freeIndex:id,roamIndex:0,roamTime:0,roamTarget:null,targetZone:0,visitedZones:[],visitLog:[],roamState:'entering',history:[{x:a.x,z:a.z}],speed:[.64,.70,.60][id%3],dwell:0,blockedFor:0,approaching:true});
  visitorModels[a.index]=visitor([0xbd7352,0x839b79,0xba9a55][a.index],[1.58,1.52,1.02][a.index]);visitorModels[a.index].traverse(o=>o.castShadow=false);
 }
 resetReception();s.entrants=leaving;s.reception.departing=leaving.length>0;s.auto=false;s.phase=leaving.length?'arriving':'idle';s.elapsed=0;hardStop();setVisitorVisibility();
 if(declined||greeted)show('01 / 自由参观',declined?'好的，请自由参观':'您可以先自行参观','需要导览时欢迎再来找我。我会继续在入口接待其他游客。','未确认导览不等于离馆；不会替游客指定离馆路线');
 log(reason+' → 入口待命；在馆游客继续自由参观');renderUI();cameraForPhase();
}
function declineTour(){if(s.phase==='greeting'&&!s.paused&&!s.faults.length&&!s.stopRequest)releaseReception('游客拒绝机器人导览',true);}
function releaseGuidedVisitors(mode){
 const guests=s.party.members.map(({path,...a})=>({...a}));
 for(const a of s.party.members){
  const id=freeVisitors.length,model=visitorModels[a.index];model.userData.queueMarker.visible=false;
  freeVisitors.push({...a,id:'free-'+id,model,freeIndex:id,active:true,leaving:mode==='leave',assistance:mode==='staff'?'staff':null,path:[],delay:a.index*.35,speed:a.role==='child'?.48:.64,walked:0,roamIndex:s.visited.size,roamTime:0,roamTarget:null,targetZone:Math.min(s.index,4),visitedZones:[...s.visited].map(i=>i+1),visitLog:[],roamState:mode==='leave'?'departing':'waiting',history:[{x:a.x,z:a.z}],dwell:0,blockedFor:0,approaching:false,yielding:false,straggler:false});
  visitorModels[a.index]=visitor([0xbd7352,0x839b79,0xba9a55][a.index],[1.58,1.52,1.02][a.index]);visitorModels[a.index].traverse(o=>o.castShadow=false);
 }
 s.party.members=[];s.entrants=[];s.regroup=null;setVisitorVisibility();return guests;
}
function updateIndependentDeparture(a,dt){
 a.moving=false;a.roamTime+=dt;if(a.delay>0){a.delay-=dt;return;}
 if(s.parking)return;
 const portal=PLAN_PORTALS.exit,q=planPoint(...portal.pixel),out=portal.outward;
 if(!a.path.length){
  if(a.exitSegment){a.active=false;a.model.visible=false;a.departedAt=sim.time;log('游客自主离馆 → '+a.id);return;}
  let route;
  for(const offset of [.90,-.90,.88,-.88,0]){
   const inside={x:q.x+offset,z:q.z-out*1.25},outside={x:q.x+offset,z:q.z+out*1.8};
   let safe=true;for(let t=0;t<=1;t+=.01){const p={x:inside.x,z:inside.z+(outside.z-inside.z)*t};if(!receptionWalkable(p)||distance(p,s.pos)<.90){safe=false;break;}}
   if(!safe)continue;const path=freePath(a,inside);if(!path.length)continue;route=[...path,inside,outside];break;
  }
  if(!route){a.roamState='waiting-exit';return;}a.path=route;a.exitSegment=true;
 }
 const target=a.path[0],d=distance(a,target);if(d<.012){a.path.shift();return;}
 const length=Math.min(d,a.speed*dt),p={x:a.x+(target.x-a.x)*length/d,z:a.z+(target.z-a.z)*length/d};
 if(!receptionWalkable(p)||distance(p,s.pos)<.90||freeAgents(a).some(b=>distance(p,b)<.55)){a.blockedFor+=dt;return;}
 a.blockedFor=0;a.yaw=Math.atan2(p.x-a.x,p.z-a.z);Object.assign(a,p);a.walked+=length;a.moving=true;
}
// Each visitor chooses a personal order and viewpoint; no robot trail or queue attachment.
const FREE_VISIT_ORDERS=[[0,1,2,3,4],[0,2,3,1,4],[0,4,3,2,1]];
function freeAgents(a){return [...freeVisitors,...trafficPeople(),...(s.accepted?s.party.members:s.entrants)].filter(b=>b!==a&&b.active!==false);}
function guideRouteDistance(p){
 let best=distance(p,s.pos),from=s.pos,remaining=3;
 for(const target of s.path){const d=distance(from,target);if(d<1e-8)continue;const ratio=Math.min(1,remaining/d),q={x:from.x+(target.x-from.x)*ratio,z:from.z+(target.z-from.z)*ratio},dx=q.x-from.x,dz=q.z-from.z;
  const t=Math.max(0,Math.min(1,((p.x-from.x)*dx+(p.z-from.z)*dz)/(dx*dx+dz*dz)));
  best=Math.min(best,distance(p,{x:from.x+t*dx,z:from.z+t*dz}));remaining-=d;if(remaining<=0)break;from=target;
 }return best;
}
function freePath(a,target){
 const circle=(p,r)=>({x:p.x,z:p.z,radius:Math.max(0,Math.min(r,distance(navPoint(a),p)-clearance-.025))});
 const dynamic=[circle(s.pos,.60),...freeAgents(a).map(p=>circle(p,(s.accepted?s.party.members:s.phase==='forming'?s.entrants:[]).includes(p)?.30:.24)),...(s.crowd?[circle(s.crowd.pos,.30)]:[])];
 const obstacles=[...s.obstacles,...dynamic];
 const direct=findPath(a,target,obstacles);if(direct.length)return direct.slice(1);
 // Anchor recovery is only for an invalid rounded start, not a blocked goal
 // or a disconnected route. Avoid hundreds of redundant searches per retry.
 if(walkable(navPoint(a),obstacles)||!walkable(navPoint(target),obstacles))return [];
 // Reception poses may be outside the navigation grid or round into a wall cell.
 // Walk to a reachable grid anchor rather than leaving that visitor stranded.
 const anchors=[];
 for(let i=-12;i<=12;i++)for(let j=-12;j<=12;j++){
  const q=world({i:grid(a).i+i,j:grid(a).j+j});
  if(!walkable(q,obstacles))continue;
  const n=Math.max(1,Math.ceil(distance(a,q)/.05));let clear=true;
  for(let k=1;k<=n;k++){
   const p={x:a.x+(q.x-a.x)*k/n,z:a.z+(q.z-a.z)*k/n};
   if(!receptionWalkable(p)||distance(p,s.pos)<.90||freeAgents(a).some(b=>distance(p,b)<.55)){clear=false;break;}
  }if(clear)anchors.push(q);
 }
 anchors.sort((p,q)=>distance(a,p)-distance(a,q));
 for(const q of anchors.slice(0,12)){const path=findPath(q,target,obstacles);if(path.length)return [q,...path.slice(1)];}
 return [];
}
function planFreeVisit(a){
 a.approaching=false;
 const order=FREE_VISIT_ORDERS[a.freeIndex%FREE_VISIT_ORDERS.length];a.targetZone=order[(a.roamIndex+Math.floor(a.freeIndex/3))%order.length];
 const points=activeMap.freeRoamStops[a.targetZone];
 for(let n=0;n<points.length;n++){
  const target=navPoint(planPoint(...points[(a.freeIndex+n)%points.length]));
  if(distance(target,s.pos)<1.05||freeAgents(a).some(b=>distance(target,b)<.8))continue;
  if(distance(a,target)<.10){a.roamTarget=target;return true;}
  const path=freePath(a,target);if(!path.length)continue;
  a.roamTarget=target;a.path=path;a.roamState='walking';return true;
 }a.roamState='waiting';a.dwell=.6;return false;
}
function yieldFreeVisitor(a){
 const candidates=a.history.slice().reverse().filter(p=>distance(p,a)>1.2&&distance(p,a)<3.6);
 for(const radius of [1.3,2.0])for(let i=0;i<12;i++)candidates.push({x:a.x+Math.sin(i*Math.PI/6)*radius,z:a.z+Math.cos(i*Math.PI/6)*radius});
 const safe=candidates.filter(p=>walkable(p,s.obstacles,.42)&&distance(p,s.pos)>1.7&&freeAgents(a).every(b=>distance(p,b)>.85)&&(!s.accepted||guideRouteDistance(p)>1.05&&s.party.members.every(m=>distance(p,m)>.98)));
 safe.sort((p,q)=>distance(p,a)-distance(q,a));
 for(const target of safe.slice(0,6)){const path=freePath(a,target);if(!path.length)continue;a.path=path;a.yielding=true;a.roamState='yielding';a.blockedFor=0;return true;}
 return false;
}
function finishFreeVisit(a){
 if(a.yielding){a.yielding=false;a.dwell=2;a.roamState='waiting';return;}
 if(a.approaching){a.approaching=false;return;}
 if(!a.roamTarget||distance(a,a.roamTarget)>.16)return;
 const zone=a.targetZone+1;if(!a.visitedZones.includes(zone))a.visitedZones.push(zone);
 a.dwell=7+(a.freeIndex*3+a.roamIndex*2)%6;a.roamState='viewing';
 a.visitLog.push({zone,at:a.roamTime,dwell:a.dwell,x:a.x,z:a.z});if(a.visitLog.length>50)a.visitLog.shift();
 const exhibit=zones[a.targetZone];a.yaw=Math.atan2(exhibit.x-a.x,exhibit.z-a.z);
 a.roamIndex++;a.roamTarget=null;
 log('自由参观 '+(a.freeIndex+1)+'号 → '+zone+'区驻足看展');
}
function updateFreeVisitors(dt){
 for(const a of freeVisitors){
  if(a.active===false)continue;
  if(a.leaving){updateIndependentDeparture(a,dt);continue;}
  a.moving=false;a.roamTime+=dt;if(a.delay>0){a.delay-=dt;continue;}
  const entryClose=(a.entryYieldUntil||0)>sim.time;
  const activeGuide=s.accepted&&!['done','ended'].includes(s.phase);
  const guideClose=entryClose||activeGuide&&(distance(a,s.pos)<1.65||guideRouteDistance(a)<1.05||s.party.members.some(m=>distance(a,m)<.95));
  if(entryClose&&!a.yielding)yieldFreeVisitor(a);
  if(guideClose&&!a.yielding&&sim.time>=(a.guideYieldRetry||0)){a.guideYieldRetry=sim.time+1;yieldFreeVisitor(a);}
  if(!a.path.length){
   if(a.dwell>0){a.dwell-=dt;if(guideClose&&!a.yielding)yieldFreeVisitor(a);if(!a.path.length)continue;}
   else if(!planFreeVisit(a))continue;
   if(!a.path.length){finishFreeVisit(a);continue;}
  }
  const target=a.path[0],d=distance(a,target);
  if(d<.012){a.path.shift();if(!a.path.length)finishFreeVisit(a);continue;}
  const length=Math.min(d,a.speed*(a.yielding?.8:1)*dt),p={x:a.x+(target.x-a.x)*length/d,z:a.z+(target.z-a.z)*length/d};
  const enteringGuideLane=activeGuide&&guideRouteDistance(a)>=1.0&&guideRouteDistance(p)<1.0;
  const agents=freeAgents(a),queueActors=s.accepted?s.party.members:s.phase==='forming'?s.entrants:[],blocked=enteringGuideLane||!receptionWalkable(p)||distance(p,s.pos)<.90||agents.some(b=>distance(p,b)<(queueActors.includes(b)?.67:.55))||s.crowd&&distance(p,s.crowd.pos)<.74;
  if(blocked){
   a.blockedFor+=dt;
   if(a.blockedFor>1.0){
    const lowerPriority=guideClose||freeVisitors.some(b=>b!==a&&b.freeIndex<a.freeIndex&&distance(a,b)<1.1);
    if(!(lowerPriority&&yieldFreeVisitor(a))){a.path=[];a.yielding=false;a.dwell=.35;a.roamState='waiting';}a.blockedFor=0;
   }continue;
  }
  a.blockedFor=0;a.yaw=Math.atan2(p.x-a.x,p.z-a.z);a.walked+=length;Object.assign(a,p);a.moving=true;
  if(distance(a,a.history.at(-1))>.3){a.history.push({x:a.x,z:a.z});if(a.history.length>36)a.history.shift();}
 }
}
function freeVisitorsNearRoute(){
 const segments=[];let from=s.pos,remaining=1.4;
 for(const target of s.path){const d=distance(from,target);if(d<1e-8)continue;const ratio=Math.min(1,remaining/d),end={x:from.x+(target.x-from.x)*ratio,z:from.z+(target.z-from.z)*ratio};segments.push([from,end]);remaining-=d;if(remaining<=0)break;from=target;}
 return freeVisitors.some(a=>s.party.members.some(m=>distance(m,a)<.65)||segments.some(([p,q])=>{
  const dx=q.x-p.x,dz=q.z-p.z,t=((a.x-p.x)*dx+(a.z-p.z)*dz)/(dx*dx+dz*dz);
  if(t<=0)return false;
  return distance(a,{x:p.x+dx*Math.min(1,t),z:p.z+dz*Math.min(1,t)})<.86;
 }));
}
function confirmParty(){
 if(s.phase!=='confirming'||s.paused||s.faults.length||s.stopRequest)return;const n=Number($('party-size').value),type=$('audience').value;
 if(sim.battery<=MODEL.battery.low){s.auto=false;toast('电量不足，不能开始新导览；您可自由参观或联系工作人员');renderUI();return;}
 if(s.entrants.some(a=>a.active!==false&&!a.leaving&&a.path.length)){toast('仍有游客正在入场，请等站定后核实人数');return;}
 if(!Number.isInteger(n)||n<1||n>3||(type==='individual'&&n!==1)||(type!=='individual'&&n<2)){toast('散客 1 人；小团体或亲子 2–3 人，请确认类型和人数');return;}
 if(s.reception.stableFor<1||(n!==s.reception.count&&!$('count-correction').checked)){toast('人数尚未稳定或与检测不一致，请等待游客进入视场；可在人数栏纠正后再次核实');return;}
 if(n!==s.entrants.filter(a=>a.active!==false&&!a.leaving).length){toast('确认人数与实际到场不一致，请核实后再开始');return;}
 if(n!==s.reception.count){sim.countObservations.push({t:sim.time,estimated:s.reception.count,confirmed:n,manualCorrection:true});log('游客明确核实并纠正人数 → 检测 '+s.reception.count+' / 人工确认 '+n);}
 const live=s.reception.tracks.filter(t=>sim.time-t.lastSeen<.22),actors=s.entrants.filter(a=>a.active!==false&&!a.leaving);
 s.partyCount=n;s.party={type,members:[]};s.formationActors=actors.slice(0,n);s.formationIndex=n-1;s.phase='forming';s.elapsed=0;
 s.formationActors.forEach((a,i)=>{a.trackId=live[i]?.id;a.role=type==='family'&&i===n-1?'child':'adult';a.path=[];});
 show('02 / 队列形成','人数已确认，请依次进入队列','从队尾开始形成队列，所有游客到位后才出发。');log('人工确认游客类型 '+type+' / 检测人数 '+n+' → 形成实际队列');renderUI();setVisitorVisibility();
}
function updateFormation(dt){
 const i=s.formationIndex;if(i<0){
  s.accepted=true;s.party.members=s.formationActors.map((a,i)=>({...a,id:a.trackId||'manual-confirmed-'+i,gap:MODEL.queue.gaps[i],progress:-MODEL.queue.gaps[i],lag:0,velocity:0,speedFactor:1,straggler:false,...s.trail.sample(MODEL.queue.gaps[i])}));
  sim.acceptedAt=sim.time;sim.countObservations.push({t:sim.time,estimated:s.reception.count,confirmed:s.partyCount,truth:s.formationActors.length});setVisitorVisibility();travel();return;
 }
 const a=s.formationActors[i],target=s.trail.sample(MODEL.queue.gaps[i]);
 if(distance(a,target)<.0001){s.formationIndex--;return;}
 if(!a.path.length)a.path=[target];moveEntrant(a,dt);
}
