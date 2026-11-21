'use strict';
function partyCenter(){const a=s.party.members;if(!a.length)return null;return {x:a.reduce((t,m)=>t+m.x,0)/a.length,z:a.reduce((t,m)=>t+m.z,0)/a.length};}
function queueIntact(){return s.accepted&&s.party.members.length===s.partyCount&&s.party.members.every(m=>m.lag<.13);}
function updateFollowers(dt){
 if(!s.accepted)return;
 for(let i=0;i<s.party.members.length;i++){
  const m=s.party.members[i],desired=s.trail.distance-m.gap,remaining=desired-m.progress;
  const limit=(m.role==='child'?.76:i===s.partyCount-1?.91:1.02)*(m.speedFactor??1);
  const target=Math.min(limit,Math.max(0,remaining*2.5)),v=ramp(m.velocity||0,target,.75,dt),delta=Math.min(Math.max(0,remaining),v*dt);
  let progress=m.progress+delta;
  if(i)progress=Math.min(progress,s.party.members[i-1].progress-.62);
  const p=s.trail.sample(s.trail.distance-progress),previous={x:m.x,z:m.z};
  const clear=!trafficNear(p,.70)&&walkable(p,s.obstacles,.29)&&freeVisitors.every(a=>distance(p,a)>.67)&&distance(p,s.pos)>.68&&s.party.members.every(o=>o===m||distance(p,o)>.46)&&(!s.crowd||distance(p,s.crowd.pos)>.68);
  if(clear&&progress>=m.progress){Object.assign(m,p);m.progress=progress;m.velocity=v;m.moving=distance(previous,m)>.00001;}else{m.velocity=0;m.moving=false;}
  m.lag=Math.max(0,desired-m.progress);
 }
 const lag=Math.max(0,...s.party.members.map(m=>m.lag));
 if(!s.regroup&&s.phase==='moving'){
  s.lagStable=lag>1.02?(s.lagStable||0)+dt:0;
  if(s.lagStable>.45){const m=s.party.members.reduce((a,b)=>a.lag>b.lag?a:b);m.straggler=true;captureTask();s.regroup={memberId:m.id,collecting:false,elapsed:0,stable:0};sim.metrics.lagEvents++;controlledStop({kind:'regroup'});log('轨迹进度检测到落后 '+m.lag.toFixed(2)+' m → 减速停车集合');}
 }
 if(s.regroup){s.regroup.stable=queueIntact()?s.regroup.stable+dt:0;s.regroup.elapsed+=dt;}
}
function injectStraggler(){
 if(s.paused||!s.accepted||s.regroup||s.phase!=='moving')return;
 const m=s.party.members.at(-1);m.speedFactor=.08;log('模拟后排游客放慢脚步 → 独立步速 '+(m.role==='child'?.76:.91)*.08+' m/s；等待实际落后检测');
}
function gather(){if(s.regroup&&!s.paused){s.regroup.collecting=true;s.party.members.forEach(m=>m.speedFactor=1);log('提醒集合 → 游客沿实际历史轨迹追上队尾');renderUI();}}
function confirmRegroup(){
 if(!s.regroup||s.paused||!s.regroup.collecting||!queueIntact()||s.regroup.stable<.5){toast('须沿轨迹归队并稳定核实全员到齐');return;}
 s.party.members.forEach(m=>m.straggler=false);s.regroup=null;sim.metrics.regroups++;log('核实全员 '+s.partyCount+' 人到齐 → 恢复原任务');
 if(s.faults.length){s.phase=faultPhase();renderUI();return;}restoreTask();
}
function updateActors(dt){
 if(!sceneReady)return;robot.position.set(s.pos.x,0,s.pos.z);robot.rotation.y=s.yaw;
 if(!s.paused)for(const wheel of wheelModels)wheel.rotation.x+=sim.v*dt/.08;updateRobotDisplay();
 const atExhibit=s.index<5&&['docking','speaking','question'].includes(s.phase)&&s.questionReturn!=='moving';
 for(const member of s.accepted?s.party.members:s.entrants){
  const model=visitorModels[member.index];if(!model||member.active===false)continue;model.position.set(member.x,0,member.z);
  const z=zones[s.index],focus=atExhibit?{x:(z.x+s.pos.x)/2,z:(z.z+s.pos.z)/2}:null;
  if(!s.paused){turnActor(model,focus?Math.atan2(focus.x-member.x,focus.z-member.z):member.yaw,dt);animateVisitor(model,s.accepted?member.progress:member.walked,!!member.moving,dt);}
  model.userData.queueMarker.visible=!!member.straggler;
 }
 for(const a of freeVisitors){a.model.position.set(a.x,0,a.z);if(!s.paused){turnActor(a.model,a.yaw,dt);animateVisitor(a.model,a.walked,a.moving,dt);}}
 drawTraffic(s.paused?0:dt);
 if(freeVisitors.length)needsDraw=true;
if(!['idle','done'].includes(s.phase))needsDraw=true;
}
