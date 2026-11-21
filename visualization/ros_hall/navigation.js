'use strict';
// A* plans a corridor; this controller integrates a differential-drive pose.
const angleDiff=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
const ramp=(value,target,rate,dt)=>value+Math.max(-rate*dt,Math.min(rate*dt,target-value));
function queueClear(route,obstacles=s.obstacles,people=[]){
 const preview=new TourTrail(ENTRY);preview.points=s.trail.points.slice();preview.distance=s.trail.distance;
 let start=s.pos;
 for(const end of route){
  if(!segmentClear(start,end,obstacles))return false;
  const n=Math.max(1,Math.ceil(distance(start,end)/.05));
  for(let i=1;i<=n;i++){
   const p={x:start.x+(end.x-start.x)*i/n,z:start.z+(end.z-start.z)*i/n};preview.append(p.x,p.z);
   if(!queuePoseClear(p,preview,obstacles,false))return false;
   // A blocked follower holds position in updateFollowers; it does not jump to
   // the ideal future trail sample. Dynamic follower safety is checked per step.
   if(people.some(a=>distance(p,a)<.78))return false;
  }start=end;
 }return true;
}
function queuePoseClear(p,trail,obstacles=s.obstacles,dynamic=true){
 const members=dynamic?s.party.members:s.party.members.map(m=>trail.sample(m.gap+m.lag));
 if(!walkable(p,obstacles)||members.some(m=>!walkable(m,obstacles,MODEL.queue.bodyRadius+.06)||distance(m,p)<MODEL.queue.robotSeparation))return false;
 for(let i=0;i<members.length;i++)for(let j=i+1;j<members.length;j++)if(distance(members[i],members[j])<MODEL.queue.memberSeparation)return false;
 if(dynamic&&s.crowd&&(distance(p,s.crowd.pos)<.78||members.some(m=>distance(m,s.crowd.pos)<.65)))return false;
 if(dynamic&&trafficPeople().some(a=>distance(a,p)<.86||members.some(m=>distance(m,a)<.70)))return false;
 if(dynamic&&freeVisitors.some(a=>distance(a,p)<.78||members.some(m=>distance(m,a)<.65)))return false;
 return true;
}
function simplifyPath(route){
 const out=[];
 for(const p of route){
  while(out.length>1){const a=out[out.length-2],b=out[out.length-1],u={x:b.x-a.x,z:b.z-a.z},v={x:p.x-b.x,z:p.z-b.z};if(Math.abs(u.x*v.z-u.z*v.x)>1e-7||u.x*v.x+u.z*v.z<0)break;out.pop();}
  out.push(p);
 }return out;
}
function shortenGridSteps(route,obstacles){
 const out=[];let i=0;
 while(i<route.length){
  out.push(route[i]);let next=i+1;
  for(let j=i+2;j<route.length;j++){
   // Only remove local grid stair steps; preserve broad detours and approach points.
   if(distance(route[i],route[j])>1.4)break;
   const a=route[i],b=route[j],n=Math.max(1,Math.ceil(distance(a,b)/.05));let clear=true;
   for(let k=0;k<=n;k++)if(!walkable({x:a.x+(b.x-a.x)*k/n,z:a.z+(b.z-a.z)*k/n},obstacles,clearance+.18)){clear=false;break;}
   if(clear)next=j;
  }i=next;
 }return out;
}
function plan(extra=[],quiet=false){
 const people=freeVisitors.filter(a=>distance(a,s.pos)<5||s.party.members.some(m=>distance(a,m)<2));
 extra=[...extra.filter(b=>!b.freePerson),...people.map(a=>({x:a.x,z:a.z,radius:.46,freePerson:true}))];
 if(s.crowd?.mode==='viewing'&&!extra.some(b=>distance(b,s.crowd.pos)<.01))extra=[...extra,{...s.crowd.pos,radius:MODEL.crowd.radius+.15}];
 // Reserve space for bounded corner tracking error; runtime checks retain the actual obstacle size.
 const reserve=MODEL.motion.trackingReserve;
 const obstacles=[...s.obstacles,...extra].map(b=>b.radius!==undefined?{...b,radius:b.radius+(b.freePerson?0:reserve)}:{...b,w:b.w+2*reserve,d:b.d+2*reserve}),occupied=new Set();
 obstacles.push(...fixtures.map(b=>b.radius!==undefined?{...b,radius:b.radius+.01,trackingFixture:true}:{...b,w:b.w+.02,d:b.d+.02,trackingFixture:true}));
 const queueObstacles=obstacles.filter(b=>!b.freePerson&&!b.trackingFixture);
 for(const m of s.party.members)for(let d=Math.max(.7,m.gap-.2);d<=m.gap+.2;d+=.1)occupied.add(key(grid(s.trail.sample(d))));
 occupied.delete(key(grid(s.pos)));
 for(const m of s.party.members){const g=grid(m);for(let i=-4;i<=4;i++)for(let j=-4;j<=4;j++){const q={i:g.i+i,j:g.j+j};if(distance(world(q),m)<.72)occupied.add(key(q));}}
 occupied.delete(key(grid(s.pos)));
 const occupiedByViewer=p=>s.crowd?.mode==='viewing'&&distance(p,s.crowd.pos)<clearance+MODEL.crowd.radius+.15+reserve||people.some(a=>distance(p,a)<.86);
 const stops=(s.approachOverride||approach[s.index]).slice(s.waypoint).filter(p=>!occupiedByViewer(p));
 const candidates=[[...stops,goal()],[goal()]];
 // A shortest first turn can fold back into the trailing queue. Try a bounded
 // side departure before declaring failure; every candidate keeps full checks.
 for(const radius of [1.2,2])for(let i=0;i<8;i++){
  const p=navPoint({x:s.pos.x+Math.sin(i*Math.PI/4)*radius,z:s.pos.z+Math.cos(i*Math.PI/4)*radius});
  if(segmentClear(s.pos,p,obstacles))candidates.push([p,goal()]);
 }
 for(const checkpoints of candidates){
  let route=[];const original=[];let from=s.pos;
  for(const checkpoint of checkpoints){
   let direct=segmentClear(from,checkpoint,obstacles);
   if(direct&&!route.length){const n=Math.max(1,Math.ceil(distance(from,checkpoint)/.05));for(let k=1;k<=n;k++)if(occupied.has(key(grid({x:from.x+(checkpoint.x-from.x)*k/n,z:from.z+(checkpoint.z-from.z)*k/n})))){direct=false;break;}}
   let leg=direct?[{...from},{...checkpoint}]:findPath(from,checkpoint,obstacles,route.length?new Set():occupied);
   if(!leg.length&&distance(from,s.pos)<.01){
    // The true start can be safe while its rounded grid cell lies in an inflated person circle.
    const start=grid(from),anchors=[];
    for(let i=-3;i<=3;i++)for(let j=-3;j<=3;j++){
     const q=world({i:start.i+i,j:start.j+j});if(!walkable(q,obstacles))continue;
     const n=Math.max(1,Math.ceil(distance(from,q)/.04));let clear=true;
     for(let k=0;k<=n;k++){const p={x:from.x+(q.x-from.x)*k/n,z:from.z+(q.z-from.z)*k/n};if(!walkable(p,queueObstacles)||people.some(a=>distance(p,a)<.78)){clear=false;break;}}
     if(clear)anchors.push(q);
    }
    anchors.sort((a,b)=>distance(a,from)+distance(a,checkpoint)-distance(b,from)-distance(b,checkpoint));
    for(const q of anchors.slice(0,12)){const tail=findPath(q,checkpoint,obstacles,route.length?new Set():occupied);if(tail.length){leg=[{...from},...tail];break;}}
   }
   if(!leg.length){route.length=0;break;}
   original.push(...leg.slice(original.length?1:0));
   const short=shortenGridSteps(leg,obstacles);route.push(...short.slice(route.length?1:0));from=checkpoint;
  }
  if(!route.length)continue;
  if(!queueClear(route,queueObstacles,people)){if(!queueClear(original,queueObstacles,people))continue;route=original;}
  s.path=simplifyPath(route);while(s.path.length&&distance(s.path[0],s.pos)<MODEL.motion.waypointTolerance)s.path.shift();
  s.aligning=true;drawRoute();return true;
 }
 if(quiet)return false;
 hardStop();s.path=[];interrupt('blocked','通道不可达，需要工作人员清障或协助到出口');
 show('06 / 安全处置','无安全通路，已停车','已保存原任务和队列。请工作人员处理障碍，再确认恢复。');
 log('路径不可达 → 安全停车并生成人工工单');drawRoute();renderUI();return false;
}
function allowedSpeed(){
 if(s.confidence<.6||!sim.localization.ready)return 0;
 const wall=Math.min(...fixtures.map(b=>fixtureDistance(s.pos,b)));
 let limit=wall<1.05?.35:MODEL.motion.vMax;
 if(trafficNear(s.pos,2.2)||freeVisitors.some(a=>distance(a,s.pos)<2.2))limit=Math.min(limit,.25);
 if(s.crowd){const d=distance(s.pos,s.crowd.pos);if(d<MODEL.crowd.slowDistance)limit=Math.min(limit,.25);}
 const lag=Math.max(0,...s.party.members.map(m=>m.lag));return Math.min(limit,lag>.5?.32:MODEL.motion.vMax);
}
function hardStop(){sim.v=0;sim.w=0;s.distanceMoved=false;}
function drive(dt){
 const cfg=MODEL.motion;
 if(!sim.localization.ready||s.confidence<.6){hardStop();interrupt(!sim.localization.ready?'lost':'perception','定位或观测不可信，运动锁定');return;}
 while(s.path.length&&distance(s.pos,s.path[0])<(s.path.length>1&&fixtures.some(b=>fixtureDistance(s.path[0],b)<.5)?.005:cfg.waypointTolerance)&&sim.v<.08){
  const p=s.path.shift(),checkpoints=s.approachOverride||approach[s.index];
  while(checkpoints[s.waypoint]&&(s.crowd?.mode==='viewing'&&distance(checkpoints[s.waypoint],s.crowd.pos)<clearance+MODEL.crowd.radius+.15+cfg.trackingReserve||freeVisitors.some(a=>distance(checkpoints[s.waypoint],a)<.86)))s.waypoint++;
  const checkpoint=checkpoints[s.waypoint];
  if(checkpoint&&distance(checkpoint,p)<.08)s.waypoint++;
  s.aligning=true;
 }
 if(!s.path.length){
  hardStop();
  if(s.parking){s.parking=null;s.approachOverride=null;s.phase='done';show('08 / 自主离馆','出口通道已让出','游客按自己的选择自行离馆；机器人在旁待机。');log('机器人靠边完成 → 游客自行离馆');renderUI();return;}
  arrive();return;
 }
 const target=s.path[0],d=distance(s.pos,target),heading=Math.atan2(target.x-s.pos.x,target.z-s.pos.z),error=angleDiff(heading,s.yaw);
 if(Math.abs(error)>.10)s.aligning=true;
 if(s.aligning&&Math.abs(error)<.008&&Math.abs(sim.w)<.03&&sim.v<.01)s.aligning=false;
 const vTarget=s.aligning?0:Math.min(allowedSpeed(),d*.95,Math.sqrt(2*cfg.aMax*d))*Math.max(0,Math.cos(error));
 const wTarget=s.aligning&&sim.v>.01?0:Math.sign(error)*Math.min(cfg.wMax,Math.abs(error)*cfg.headingGain,Math.sqrt(2*cfg.alphaMax*Math.abs(error)));
 const v=ramp(sim.v,vTarget,cfg.aMax,dt),w=ramp(sim.w,wTarget,cfg.alphaMax,dt);
 const yaw=s.yaw+w*dt,p={x:s.pos.x+v*Math.sin(s.yaw+w*dt/2)*dt,z:s.pos.z+v*Math.cos(s.yaw+w*dt/2)*dt};
 const trail=new TourTrail(ENTRY);trail.points=s.trail.points.slice();trail.distance=s.trail.distance;trail.append(p.x,p.z);
 if(!queuePoseClear(p,trail)){
  hardStop();if(s.crowd||trafficPeople().length||freeVisitorsNearRoute()||freeVisitors.some(a=>distance(a,p)<.82||s.party.members.some(m=>distance(m,a)<.70))){beginCrowdWait();return;}
  interrupt('blocked','机器人或队列下一步安全距离不足');return;
 }
 sim.v=v;sim.w=w;s.pos=p;s.yaw=angleDiff(yaw,0);s.trail.append(p.x,p.z);s.distanceMoved=v>.001;
}

