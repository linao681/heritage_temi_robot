'use strict';
// Scenario actors are independent synthetic people with perfect simulated tracks.
// They do not imply a deployed detector or measured real-world crowd capacity.
let trafficModels=[];
const TRAFFIC_TYPES={crossing:'单人横穿',meeting:'双人交汇',same:'多人同向',opposite:'多人反向',gathering:'临时聚集',narrow:'窄通道会车',occlusion:'遮挡后重现'};
function resetTraffic(){sim.traffic={type:null,people:[],elapsed:0,waited:0,clearFor:0,detourTried:false,detoured:false,samples:[],droppedSamples:0};for(const m of trafficModels)m.visible=false;}
function trafficPeople(){return sim.traffic?.people||[];}
function trafficNear(p,r){return trafficPeople().some(a=>distance(a,p)<r);}
function trafficBlocked(){const t=sim.traffic;return trafficNear(s.pos,.94)||!t.detoured&&trafficNear(s.pos,1.4)||s.party.members.some(m=>trafficNear(m,.85));}
function trafficSnapshot(){return sim.traffic?{...sim.traffic,people:trafficPeople().map(a=>({...a,path:a.path.map(p=>({...p}))}))}:null;}
function trafficSite(type){
 const route=[s.pos,...s.path];let travelled=0;
 for(let i=1;i<route.length;i++){
  const a=route[i-1],b=route[i],len=distance(a,b);if(len<.1)continue;
  const t={x:(b.x-a.x)/len,z:(b.z-a.z)/len},n={x:-t.z,z:t.x};
  for(let d=.4;d<len-.3;d+=.3){
   const ahead=travelled+d;if(ahead<2.2||ahead>6)continue;
   const p={x:a.x+t.x*d,z:a.z+t.z*d};let corridorWidth=null;
   if(type==='narrow'){
    const angle=Math.atan2(n.x,n.z),right=rayDistance(p,angle,5,s.obstacles),left=rayDistance(p,angle+Math.PI,5,s.obstacles);corridorWidth=right+left;
    if(corridorWidth>3.2||corridorWidth<1.25)continue;
    p.x+=n.x*(right-left)/2;p.z+=n.z*(right-left)/2;
   }
   const point=(along,across)=>navPoint({x:p.x+t.x*along+n.x*across,z:p.z+t.z*along+n.z*across});
   let pairs;
   if(type==='crossing')pairs=[[point(0,-1.5),point(0,1.5)]];
   else if(type==='meeting')pairs=[[point(-.4,-1.5),point(-.4,1.5)],[point(.4,1.5),point(.4,-1.5)]];
   else if(type==='same')pairs=[-.8,0,.8].map(o=>[point(-.6,o),point(2,o)]);
   else if(type==='opposite')pairs=[-.8,.8].map(o=>[point(1,o),point(-1,o)]);
   else if(type==='gathering')pairs=[-.8,0,.8].map(o=>[point(.7,o),point(0,o)]);
   else if(type==='narrow')pairs=[[point(1,.3),point(-1,.3)],[point(-.3,-.3),point(1.7,-.3)]];
   else continue;
   const paths=pairs.map(([from,to])=>findPath(from,to,s.obstacles));
   if(paths.some(path=>path.length<2)||pairs.some(([from,to])=>distance(from,s.pos)<1.1||s.party.members.some(m=>distance(from,m)<.75)||freeVisitors.some(m=>distance(from,m)<.75)||distance(to,goal())<.85))continue;
   if(pairs.some(([a],j)=>pairs.some(([b],k)=>k!==j&&distance(a,b)<.58)))continue;
   return {pairs,paths,corridorWidth};
  }travelled+=len;
 }return null;
}
function occludedTrafficSite(){
 const hidden=[],visible=[];
 for(const r of [1.8,2.6,3.4,4.2])for(let i=0;i<24;i++){
  const p=navPoint({x:s.pos.x+Math.sin(i*Math.PI/12)*r,z:s.pos.z+Math.cos(i*Math.PI/12)*r});
  if(!walkable(p,s.obstacles,.46)||[...s.party.members,...freeVisitors].some(a=>distance(a,p)<.8))continue;
  const d=distance(s.pos,p),bearing=Math.atan2(p.x-s.pos.x,p.z-s.pos.z),blocked=rayDistance(s.pos,bearing,d+.05,s.obstacles)<d-.18;
  (blocked?hidden:visible).push(p);
 }
 for(const from of hidden.slice(0,16)){
  const candidates=visible.filter(to=>distance(from,to)<3.5).sort((a,b)=>distance(from,a)-distance(from,b));
  for(const to of candidates.slice(0,6)){const path=findPath(from,to,s.obstacles);if(path.length>1)return {pairs:[[from,to]],paths:[path]};}
 }return null;
}
function injectTraffic(type=$('traffic-type').value){
 const atObservationStop=type==='occlusion'&&['speaking','question'].includes(s.phase)&&Math.abs(sim.v)<.001&&Math.abs(sim.w)<.001;
 if(s.paused||s.phase!=='moving'&&!atObservationStop||trafficPeople().length||s.crowd||!TRAFFIC_TYPES[type])return false;
 const site=type==='occlusion'?occludedTrafficSite():trafficSite(type);
 if(!site){toast('当前路段没有足够安全的场景空间，请在其他路段尝试');log('多人场景未创建 → '+type+' / 空间检查不通过');return false;}
 resetTraffic();sim.traffic.type=type;sim.traffic.corridorWidth=site.corridorWidth??null;
 for(let i=0;i<site.pairs.length;i++){
  const [from,to]=site.pairs[i],path=site.paths[i].slice(1),a={id:'traffic-'+i,...from,start:{...from},target:{...to},path,speed:.48+i*.05,delay:i*.25,moving:false,walked:0,yaw:0,blockedFor:0,visibleToRobot:false,occludedSeen:false,reappeared:false};
  sim.traffic.people.push(a);
  if(!trafficModels[i]){trafficModels[i]=visitor([0x6f8c98,0xa37c68,0x839071][i%3],1.5);trafficModels[i].name='独立动态行人 '+(i+1);scene.add(trafficModels[i]);trafficModels[i].traverse(o=>o.castShadow=false);}
  trafficModels[i].visible=true;trafficModels[i].position.set(a.x,0,a.z);
 }
 log('多人动态场景 → '+TRAFFIC_TYPES[type]+' / '+site.pairs.length+'个独立实体');renderUI();return true;
}
function updateTraffic(dt){
 const traffic=sim.traffic;if(!traffic?.people.length)return;traffic.elapsed+=dt;
 for(const a of traffic.people){
  a.moving=false;a.delay-=dt;
  if(a.delay<=0&&a.path.length){
   const q=a.path[0],d=distance(a,q),move=Math.min(d,a.speed*dt),p={x:a.x+(q.x-a.x)*move/(d||1),z:a.z+(q.z-a.z)*move/(d||1)};
   const others=[...traffic.people,...freeVisitors,...s.party.members,...(!s.accepted?s.entrants:[])].filter(b=>b!==a&&b.active!==false);
   if(walkable(p,s.obstacles,.27)&&distance(p,s.pos)>.86&&others.every(b=>distance(p,b)>.58)&&(!s.crowd||distance(p,s.crowd.pos)>.7)){
    a.yaw=Math.atan2(p.x-a.x,p.z-a.z);Object.assign(a,p);a.walked+=move;a.moving=move>.00001;a.blockedFor=0;if(d<=move+.001)a.path.shift();
   }else a.blockedFor+=dt;
  }
  const d=distance(s.pos,a),bearing=Math.atan2(a.x-s.pos.x,a.z-s.pos.z);a.visibleToRobot=d<=MODEL.sensors.range.maxRange&&rayDistance(s.pos,bearing,d+.02,s.obstacles)>=d-.16;
  if(d<=MODEL.sensors.range.maxRange&&!a.visibleToRobot)a.occludedSeen=true;else if(a.visibleToRobot&&a.occludedSeen)a.reappeared=true;
 }
 if(!traffic.samples.length||traffic.elapsed-traffic.samples.at(-1).t>=.2){traffic.samples.push({t:traffic.elapsed,people:traffic.people.map(a=>({id:a.id,x:a.x,z:a.z,moving:a.moving,visibleToRobot:a.visibleToRobot,reappeared:a.reappeared}))});if(traffic.samples.length>1200){traffic.samples.shift();traffic.droppedSamples++;}}
 needsDraw=true;
}
function drawTraffic(dt){trafficPeople().forEach((a,i)=>{const m=trafficModels[i];if(!m)return;m.position.set(a.x,0,a.z);turnActor(m,a.yaw,dt);animateVisitor(m,a.walked,a.moving,dt);});}
function monitorTraffic(dt){
 const t=sim.traffic;if(!t?.people.length)return;
 const blocked=trafficBlocked();
 if(s.phase==='moving'&&blocked)beginCrowdWait();
 if(s.phase!=='crowd_wait')return;
 if(!blocked){t.clearFor+=dt;return;}t.clearFor=0;t.waited+=dt;
 if(t.waited>=MODEL.crowd.detourAfter&&!t.detourTried){t.detourTried=true;const ok=plan(t.people.map(a=>({...a,radius:.42})),true);if(ok){t.detoured=true;s.phase='moving';s.elapsed=0;log('多人动态绕行 → 路径通过队伍检查');}}
 if(t.waited>=MODEL.crowd.handoffAfter&&!s.faults.length)interrupt('manual','多人动态场景持续阻塞，请工作人员疏导');
}
$('traffic-inject').onclick=()=>injectTraffic();
$('traffic-type').onchange=()=>renderUI();
