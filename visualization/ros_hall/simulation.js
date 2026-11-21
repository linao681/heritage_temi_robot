'use strict';
// Workflow and fault recovery have one owner. External events are simulated inputs.
const sim={time:0,battery:MODEL.battery.initial,unclear:0,records:[],qaRecords:[],handoffs:[],trajectory:[],docks:[],question:null,v:0,w:0,range:5,droppedEvents:0,droppedTrajectory:0};
let sensorLines,sensorAccumulator=0,crowdActor,taskSerial=0;
function resetTelemetry(){
 Object.assign(sim,{time:0,battery:MODEL.battery.initial,unclear:0,fault:null,records:[],qaRecords:[],handoffs:[],trajectory:[],docks:[],question:null,v:0,w:0,range:5,droppedEvents:0,droppedTrajectory:0,taskId:'SIM-'+new Date().toISOString().replace(/\D/g,'')+'-'+(++taskSerial)});
 if(crowdActor)crowdActor.visible=false;
}
function openHandoff(reason){
 if(s.handoff?.status==='pending'){if(!s.handoff.reasons.includes(reason))s.handoff.reasons.push(reason);s.handoff.revision++;s.handoff.safetyConfirmed=false;s.handoff.replanned=false;$('staff-safe').checked=false;return;}
 const ticket={id:sim.taskId+'-H'+(sim.handoffs.length+1),taskId:sim.taskId,zoneId:s.index<5?s.index+1:null,pose:{...s.pos,yaw:s.yaw},question:sim.question,reason,reasons:[reason],battery:sim.battery,deviceState:s.phase,returnTask:s.returnTask?{...s.returnTask}:null,path:s.path.map(p=>({...p})),party:s.party.members.map(m=>({...m})),mapId:activeMap.id,sensorConfidence:s.confidence,localization:cloneMap(sim.localization),queueIntact:queueIntact(),revision:1,handling:[],safetyConfirmed:false,replanned:false,status:'pending',openedAt:sim.time};
 s.handoff=ticket;$('staff-safe').checked=false;sim.handoffs.push(ticket);log('生成人工工单 → '+ticket.id+' / '+reason);
}
function closeHandoff(){if(s.handoff?.status==='pending'){s.handoff.status='resolved';s.handoff.resolvedAt=sim.time;log('工作人员确认处理 → '+s.handoff.id);}}
function renderHandoff(){
 $('handoff-card').hidden=!s.handoff;if(!s.handoff)return;const h=s.handoff;
 $('handoff-detail').textContent='任务 '+h.taskId+'\n展区 '+(h.zoneId||'出口')+' / 坐标 '+h.pose.x.toFixed(2)+', '+h.pose.z.toFixed(2)+'\n原因：'+h.reasons.join('；')+'\n问题：'+(h.question||'无')+'\n状态：'+(h.status==='pending'?'待工作人员处理':'已确认处理');
}

function faultPhase(){return s.faults.some(f=>f.kind==='estop')?'estop':s.faults[0]?.kind||'manual';}

function restoreTask(){
 const task=s.returnTask;s.returnTask=null;s.elapsed=task?.elapsed||0;s.paused=!!task?.paused;s.questionReturn=task?.questionReturn||null;
 if(s.accepted&&sim.battery<=MODEL.battery.low){handleLowBattery();return;}
 if(!task||['moving','crowd_wait','blocked'].includes(task.phase)||(task.phase==='question'&&task.questionReturn==='moving'))travel();
 else{s.phase=task.phase;if(['speaking','question','docking'].includes(s.phase)){s.phase='speaking';explanation();}renderUI();cameraForPhase();}
}

function endTour(){
 if(s.phase==='stopping')return;
 if((Math.abs(sim.v)>.001||Math.abs(sim.w)>.001)&&!s.endRequest){controlledStop({kind:'end'});return;}
 if(['idle','done','ended'].includes(s.phase)||s.endRequest||s.phase==='estop')return;
 s.endRequest={paused:s.paused};s.paused=true;hardStop();silence();show('08 / 结束确认','结束机器人导览，改为自由参观吗？','确认后在当前位置解除队列，继续留馆参观；取消可继续原任务。');log('游客提出结束 → 等待确认意愿');renderUI();
}
function confirmEnd(yes){
 if(!s.endRequest)return;const prior=s.endRequest;
 if(yes&&(s.faults.length||s.regroup)){toast('请先处理安全异常或确认队伍集合');return;}
 s.endRequest=null;s.paused=prior.paused;
 if(!yes){log('取消结束请求 → 保留原任务');renderUI();return;}
 s.paused=false;s.auto=false;if(!s.accepted){releaseReception('游客取消尚未启动的导览',false);return;}endRobotService('游客提前结束机器人导览','free');
}
function endRobotService(reason,mode){
 hardStop();silence();s.auto=false;s.autoAssist=false;s.paused=false;s.path=[];s.returnTask=null;s.questionReturn=null;s.endRequest=null;s.endReason=reason;
 if(s.phase!=='done')s.phase='ended';s.serviceEndedAt=sim.time;
 const guests=releaseGuidedVisitors(mode);s.serviceOutcome={mode,reason,at:sim.time,guests};
 show('08 / 服务结束',mode==='staff'?'工作人员已接续游客服务':mode==='leave'?'您已选择自行离馆':'机器人导览已结束，请自由参观',mode==='staff'?'工作人员已核实人数与现场，接续后续讲解或参观安排；机器人保持停车。当前为本地交接流程模拟。':mode==='leave'?'游客自行按出口通道离馆，机器人不再带队；通道受阻时等待，不穿过行人或墙体。':'已在当前位置解除队列。您可以继续参观各展区，原导览记录已保留。');
 log(reason+' → '+(mode==='staff'?'人工接续':mode==='leave'?'游客自主离馆':'留馆自由参观'));drawRoute();renderUI();cameraForPhase();
}
function chooseVisit(mode){
 if(s.phase!=='done'||s.serviceOutcome||s.faults.length||!['free','leave'].includes(mode))return;
 endRobotService('完整导览后游客选择'+(mode==='free'?'继续参观':'自行离馆'),mode);
 if(mode==='leave'){
  const q=planPoint(...PLAN_PORTALS.exit.pixel),out=PLAN_PORTALS.exit.outward;
  for(const dx of [-2,2,0]){
   const target=navPoint({x:q.x+dx,z:q.z-out*2});
   if(!walkable(target,s.obstacles)||freeVisitors.some(a=>a.active!==false&&distance(a,target)<1.1))continue;
   s.parking={target};s.approachOverride=[];
   if(plan([],true)){s.phase='parking';show('08 / 自主离馆','机器人先靠边，让出出口通道','服务已结束，机器人独立靠边；游客随后自行离馆，不再跟随机器人。');log('游客选择自行离馆 → 机器人独立靠边让出出口');renderUI();return;}
  }
  s.parking=null;s.approachOverride=null;s.path=[];hardStop();
 }
}
function beginExit(reason){
 if(Math.abs(sim.v)>.001||Math.abs(sim.w)>.001){controlledStop({kind:'exit',reason});return;}
 hardStop();silence();s.index=5;s.waypoint=0;s.approachOverride=null;s.questionReturn=null;s.path=[];s.endReason=reason;s.exitPending=false;log(reason+' → 安全规划出口路线');travel();
}
function arrive(){
 hardStop();s.elapsed=0;s.phase='docking';s.dockStable=0;
 show('03 / 到点停靠','正在停稳','按实际位置确认停靠误差，平稳转向展项后开始服务。');log('进入停靠 → 实际位置误差 '+distance(s.pos,goal()).toFixed(4)+' m');renderUI();
}
function dock(dt){
 const z=zones[s.index],center=partyCenter(),target=z&&center?Math.atan2(center.x-s.pos.x,center.z-s.pos.z):s.yaw,e=angleDiff(target,s.yaw),cfg=MODEL.motion;
 sim.v=0;sim.w=ramp(sim.w,Math.max(-cfg.wMax,Math.min(cfg.wMax,e*cfg.headingGain)),cfg.alphaMax,dt);s.yaw=angleDiff(s.yaw+sim.w*dt,0);
 if(Math.abs(e)<.04&&Math.abs(sim.w)<.04&&s.party.members.every(m=>m.lag<.13))s.dockStable+=dt;else s.dockStable=0;
 if(s.dockStable<cfg.settleSeconds)return;
 hardStop();const error=distance(s.pos,goal());s.dockError=error;
 sim.docks.push({zoneId:z?s.index+1:null,target:{...goal()},actual:{...s.pos,yaw:s.yaw},error,time:sim.time});log('停稳完成 → 实测仿真误差 '+error.toFixed(4)+' m');
 if(s.index>=5){s.phase='done';s.auto=false;s.completedAt=sim.time;show('08 / 导览完成','导览已完成，接下来由您选择','已到达出口服务区，本次访问 '+s.visited.size+' 个展区。您可以继续自由参观，也可以自行离馆；未选择前不会安排离馆。');log('任务完成 → 出口服务区；等待游客选择自由参观或自行离馆');}
 else{s.phase='speaking';s.elapsed=0;s.visited.add(s.index);explanation();}
 drawRoute();renderUI();cameraForPhase();
}
function answerQuestion(question){
 const q=question.trim();if(!q||s.paused||!['moving','speaking','question'].includes(s.phase))return;
 if(s.phase==='moving'){s.questionReturn='moving';log('途中提问 → 已减速停稳，保留原路线');}
 sim.question=q;sim.unclear=0;const intent=q.replace(/[？?！!。．.\s]/g,'');
 const safety=/着火|火灾|受伤|晕倒|危险|踩踏|烟雾|急救|救命|紧急/.test(q);
 let answer,ids=['CASE'];const unsupported=/多少钱|价格|作者|哪年|年代|家族|师承|营业|几点|开放时间|具体传承人|鉴定|估值|真伪|修复方案|历史争议/.test(q);
 if(!safety&&!unsupported){
  if(/出口.*(哪|怎么|如何)|怎么.*出去|怎样.*离开/.test(intent))answer='出口在我当前朝向的'+exitBearing()+'；我会按安全路线送往出口。现场请遵循场馆标识。';
  else if(/几个展区|参观顺序|参观路线|接下来.*去哪|导览路线/.test(intent))answer='主线依次为概览、工艺、作品、传承故事、互动体验，最后前往出口。';
  else if(/^(请问|能介绍一下|给我讲讲)?(什么是非遗|非遗是什么|非物质文化遗产是什么)$/.test(intent)){answer=GUIDE_CARDS[0][0].text;ids=['U1'];}
  else if(s.index<5&&/^(请问|能|可以|给我)?(介绍一下|介绍|讲讲|说说)?(这里的|这个展区的|本展区的|这些|这个)?(工序|工艺|怎么制作|如何制作|制作过程|文化价值|有什么意义|历史背景|有什么历史|展项|展项介绍|本展区|当前展区|这是什么工艺)(吗|呢)?$/.test(intent)){
   const part=/历史/.test(q)?1:/工序|工艺|制作/.test(q)?2:/文化价值|意义/.test(q)?3:0;answer=GUIDE_CARDS[s.index][part].text;ids=[GUIDE_CARDS[s.index][part].source];
  }
 }
 const decision=answer?'answered':'handoff';const intentClass=safety?'safety':unsupported?'professional-or-unverified':answer?'supported-rule':'unknown';if(!answer)answer='当前资料没有足够依据，我不会猜测。请工作人员核实。';
 s.phase='question';s.elapsed=0;$('question').value='';sim.qaRecords.push({t:sim.time,zoneId:s.index<5?s.index+1:null,pose:{...s.pos},question:q,answer,sourceIds:decision==='answered'?ids:[],decision,intentClass,matchConfidence:answer&&decision==='answered'?'规则命中且有审核来源；非概率置信度':'依据不足，不推测'});
 show('05 / 受控问答',q,answer);if(decision==='answered'){renderSources(ids);log('问答命中 → '+ids.join(','));renderUI();}
 else{interrupt('manual',safety?'安全问题需现场人工处置':'问题超出已核实知识范围');s.autoAssist=s.auto&&!safety;}
}



function injectCrowd(mode='crossing'){
 if(s.paused||s.phase!=='moving'||s.crowd)return false;
 const route=[s.pos,...s.path];let accumulated=0;
 for(let i=1;i<route.length;i++){
  const a=route[i-1],b=route[i],len=distance(a,b);
  for(let t=.2;t<=len;t+=.2){
   const ahead=accumulated+t;if(ahead<(mode==='viewing'?2.2:1.9)||ahead>4)continue;
   const p={x:a.x+(b.x-a.x)*t/len,z:a.z+(b.z-a.z)*t/len};if(distance(p,goal())<(mode==='viewing'?1.25:.9))continue;
   const normal={x:-(b.z-a.z)/len,z:(b.x-a.x)/len};
   for(const sign of [1,-1]){
    const end={x:p.x+normal.x*1.9*sign,z:p.z+normal.z*1.9*sign};
    if((mode!=='viewing'&&!segmentClear(p,end,s.obstacles))||!walkable(p,s.obstacles)||distance(p,s.pos)<1.85||s.party.members.some(m=>distance(m,p)<.9)||freeVisitors.some(a=>distance(a,p)<.9))continue;
    s.crowd={mode,start:{...p},pos:{...p},end,t:0,waited:0,clearFor:0,detourTried:false,stationary:mode!=='crossing',detoured:false};
    if(mode==='viewing'){
     const originalPath=s.path;
     const canBypass=plan([{...p,radius:MODEL.crowd.radius+.15}],true);
     s.path=originalPath;drawRoute();
     if(!canBypass){s.crowd=null;continue;}
    }
    if(mode==='viewing')s.crowd.focus=PLAN_FIXTURES.filter(b=>['relief','kiosk','glass','wall-cabinet','tools','workbench'].includes(b.kind)).sort((a,b)=>distance(a,p)-distance(b,p))[0];
    if(!crowdActor&&sceneReady)crowdActor=visitor(0x586a7a,1.62);
    if(crowdActor){crowdActor.visible=true;crowdActor.position.set(p.x,0,p.z);}
    log('动态行人注入 → '+(mode==='viewing'?'游客驻足看展，机器人主动绕行':mode==='crossing'?'独立穿越轨迹':'持续占道，尝试局部绕行'));renderUI();return true;
   }
  }accumulated+=len;
 }toast('当前路段不足以安全放置行人，请在下一段重试');return false;
}
function updateCrowd(dt){
 const c=s.crowd;if(!c)return;c.t+=dt;
 if(!c.stationary&&c.releasedAt===undefined&&(s.phase==='crowd_wait'||c.t>12))c.releasedAt=c.t;
 if(!c.stationary&&c.releasedAt!==undefined&&c.t-c.releasedAt>.5&&distance(c.pos,c.end)>.001){
  const d=distance(c.pos,c.end),travel=Math.min(d,MODEL.crowd.speed*dt),p={x:c.pos.x+(c.end.x-c.pos.x)*travel/d,z:c.pos.z+(c.end.z-c.pos.z)*travel/d};
  if(walkable(p,s.obstacles)&&distance(p,s.pos)>.85&&s.party.members.every(m=>distance(p,m)>.7)&&freeVisitors.every(a=>distance(p,a)>.74))c.pos=p;
 }
 if(crowdActor){crowdActor.position.set(c.pos.x,0,c.pos.z);const focus=c.focus||c.end;crowdActor.rotation.y=Math.atan2(focus.x-c.pos.x,focus.z-c.pos.z);animateVisitor(crowdActor,distance(c.start,c.pos),!c.stationary&&c.releasedAt!==undefined&&distance(c.pos,c.end)>.01,dt);}
 if(!c.stationary&&distance(c.pos,c.end)<.01&&distance(s.pos,c.pos)>MODEL.crowd.clearDistance&&s.party.members.every(m=>distance(m,c.pos)>1)){
  s.crowd=null;if(crowdActor)crowdActor.visible=false;log('动态行人完成穿越并离开队列安全区域');
 }
}
function beginCrowdWait(){if(s.phase==='crowd_wait'||s.phase==='stopping')return;controlledStop({kind:'crowd'});}
function monitorCrowd(dt){
 if(trafficPeople().length&&trafficBlocked()){monitorTraffic(dt);return;}
 const freeBlocked=freeVisitorsNearRoute();s.freeClearFor=freeBlocked?0:(s.freeClearFor||0)+dt;
 if(freeBlocked){
  if(s.phase==='moving')beginCrowdWait();
  if(s.phase==='crowd_wait'){
   const w=s.freeCrowdWait||(s.freeCrowdWait={elapsed:0,lastAttempt:0,attempts:0,detours:0});w.elapsed+=dt;
   if(w.elapsed>=30){interrupt('manual','累计等待30秒，通道仍反复受阻，请工作人员协助疏导自由游客');s.autoAssist=false;return;}
   if(w.elapsed-w.lastAttempt>=MODEL.crowd.detourAfter){
    w.lastAttempt=w.elapsed;w.attempts++;
    const people=freeVisitors.filter(a=>distance(a,s.pos)<4||s.party.members.some(m=>distance(a,m)<2));
    if(plan(people.map(a=>({...a,radius:.46,freePerson:true})),true)){w.detours++;s.phase='moving';s.elapsed=0;log('自由游客绕行通过队列安全检查 → 继续原展区');renderUI();return;}
    show('06 / 自由游客避让','正在等待通道，并重试绕行','等待 '+w.elapsed.toFixed(0)+' 秒，已检查 '+w.attempts+' 次路线；不穿越行人或展柜。');
   }
  }return;
 }
 if(s.freeClearFor>=MODEL.crowd.clearSeconds)s.freeCrowdWait=null;
 const c=s.crowd;if(!c){if(s.phase==='crowd_wait'&&s.freeClearFor>=MODEL.crowd.clearSeconds){s.phase='moving';s.elapsed=0;log('行人已安全离开 → 继续原路线');renderUI();}return;}const near=distance(s.pos,c.pos),membersNear=s.party.members.some(m=>distance(m,c.pos)<.85);
 if(s.phase==='moving'&&!c.detoured&&(near<(c.mode==='viewing'?3.5:MODEL.crowd.stopDistance)||membersNear))beginCrowdWait();
 if(s.phase!=='crowd_wait')return;c.waited+=dt;
 const clear=(c.mode!=='viewing'||c.detoured)&&near>MODEL.crowd.clearDistance&&!membersNear;c.clearFor=clear?c.clearFor+dt:0;
 if(c.clearFor>=MODEL.crowd.clearSeconds){s.phase='moving';s.elapsed=0;log('动态安全间距持续恢复 → 继续原路线');renderUI();return;}
 if(c.stationary&&!c.detourTried&&c.waited>=MODEL.crowd.detourAfter){
  c.detourTried=true;log('持续人流 → 尝试保留队列的局部绕行');
  if(plan([{...c.pos,radius:MODEL.crowd.radius+.15}],true)){c.detoured=true;s.phase='moving';s.elapsed=0;log('动态绕行通过队列安全检查 → 继续原展区');renderUI();return;}
  log('局部绕行无安全路线 → 保持停车');
 }
 if(c.waited>=MODEL.crowd.handoffAfter){interrupt('manual','动态人流持续阻塞，无安全通路');s.autoAssist=false;}
}
function clearObstacles(){
 s.obstacles=[];resetTraffic();s.crowd=null;if(crowdActor)crowdActor.visible=false;drawObstacles();log('模拟工作人员清除临时障碍与占道人流');if(s.phase==='moving')plan();else if(s.phase==='crowd_wait'){s.phase='moving';plan();}renderUI();
}
function handleLowBattery(){
 if(!s.accepted&&sim.battery<=MODEL.battery.low){s.auto=false;show('06 / 电量检查','当前电量不足，暂不能开始导览','您可以自行参观或联系工作人员；机器人继续在入口待命。');renderUI();return;}
 if(sim.battery>MODEL.battery.low||s.lowBatteryHandled||!s.accepted||!s.party.members.length||['done','ended'].includes(s.phase))return;
 s.lowBatteryHandled=true;s.auto=false;s.autoAssist=false;
 if(s.endRequest){s.paused=s.endRequest.paused;s.endRequest=null;}
 interrupt('battery','电量不足，安全停车并请求工作人员接续游客服务');log('低电量阈值触发 → 停止接新任务，保留服务上下文，等待人工接续');
}


function renderEngineeringUI(){
 states.regroup='游客掉队 · 等待集合';const active=sceneReady&&!['idle','done','ended'].includes(s.phase),halted=s.faults.length>0||s.phase==='regroup';
 $('status').textContent=s.paused?'导览已暂停':states[s.phase];$('end-confirm').hidden=!s.endRequest;$('regroup-card').hidden=!s.regroup;
 $('end-tour').disabled=!active||!!s.serviceOutcome||s.phase==='estop'||!!s.endRequest;$('resume').disabled=s.paused||!s.faults.length||!!s.regroup||!!s.endRequest;
 for(const id of ['straggler','unclear','battery'])$(id).disabled=!active||s.paused||halted;
 $('straggler').disabled=$('straggler').disabled||s.phase!=='moving';$('crowd-persistent').disabled=$('crowd').disabled;
 if(halted||s.endRequest)for(const id of ['skip','next','repeat','interact'])$(id).disabled=true;
 if(s.regroup){$('queue-detail').textContent=s.party.members.map(m=>(m.index+1)+'号 '+(m.straggler?(m.lag>.02?'待归队 · 落后 '+m.lag.toFixed(2)+'m':'已到队尾，待确认'):'在队')).join(' / ')+'；确认人数 '+s.partyCount+' 人';$('confirm-regroup').disabled=s.paused||!s.regroup.collecting||s.party.members.some(m=>m.lag>.02);$('gather').disabled=s.paused;}
 if(!['speaking','question'].includes(s.phase)||s.exploration?.openZone!==s.index)$('quiz').hidden=true;
}
function dockStatistics(){const a=sim.docks.map(d=>d.error).sort((a,b)=>a-b);return {count:a.length,mean:a.length?a.reduce((x,y)=>x+y,0)/a.length:null,max:a.at(-1)??null,p50:a.length?a[Math.floor((a.length-1)*.5)]:null,p95:a.length?a[Math.ceil((a.length-1)*.95)]:null,unit:'m',scope:'integrated browser poses; not hardware accuracy'};}

function rayDistance(origin,angle,maxRange=5,obstacles=[],baseFixtures=fixtures){
 let nearest=maxRange;const dx=Math.sin(angle),dz=Math.cos(angle);
 for(const box of [...baseFixtures,...obstacles]){
  if(box.radius!==undefined){
   const x=origin.x-box.x,z=origin.z-box.z,b=x*dx+z*dz,c=x*x+z*z-box.radius*box.radius,disc=b*b-c;
   if(c<=0)nearest=0;else if(disc>=0&&-b-Math.sqrt(disc)>=0)nearest=Math.min(nearest,-b-Math.sqrt(disc));continue;
  }
  const p=fixtureLocal(origin,box),cs=Math.cos(box.angle||0),sn=Math.sin(box.angle||0),vx=cs*dx-sn*dz,vz=sn*dx+cs*dz;
  let lo=0,hi=maxRange;
  for(const [q,d,min,max] of [[p.x,vx,-box.w/2,box.w/2],[p.z,vz,-box.d/2,box.d/2]]){
   if(Math.abs(d)<1e-8){if(q<min||q>max){hi=-1;break;}}
   else{const a=(min-q)/d,c=(max-q)/d;lo=Math.max(lo,Math.min(a,c));hi=Math.min(hi,Math.max(a,c));}
  }if(hi>=lo&&hi>=0)nearest=Math.min(nearest,lo);
 }return nearest;
}


// Presentation instrumentation is separate from the workflow.
const drawScene=updateScene;
updateScene=function(dt){if(sceneReady&&!contextLost){sensorAccumulator+=dt;if(sensorAccumulator>=1/MODEL.performance.telemetryHz){sensorAccumulator=0;updatePerception();if(s.regroup)renderEngineeringUI();}}drawScene(dt);};
const disposeVisualScene=disposeScene;
disposeScene=function(){disposeVisualScene();sensorLines=null;crowdActor=null;trafficModels=[];panelCache.clear();ceilingGroup=null;zoneFloorGroup=null;recommendedRouteGroup=null;robotScreen=null;robotScreenCanvas=null;robotScreenTexture=null;robotStatusMaterial=null;robotScreenKey='';};
$('clear').onclick=clearObstacles;$('crowd').onclick=()=>injectCrowd();$('crowd-persistent').onclick=()=>injectCrowd('persistent');$('resume').onclick=()=>resume();
$('glass').onclick=()=>injectGlassNoise();$('straggler').onclick=()=>injectStraggler();$('gather').onclick=()=>gather();$('confirm-regroup').onclick=()=>confirmRegroup();
$('visit-free').onclick=()=>chooseVisit('free');$('visit-leave').onclick=()=>chooseVisit('leave');
$('end-confirm-yes').onclick=()=>confirmEnd(true);$('end-confirm-no').onclick=()=>confirmEnd(false);
$('unclear').onclick=()=>unclearCommand();
$('battery').onclick=()=>{sim.battery=15;log('模拟低电量注入 → 15%');handleLowBattery();renderUI();};
$('sensors').onchange=()=>{if(sensorLines)sensorLines.visible=$('sensors').checked;needsDraw=true;};
$('reference-open').onclick=()=>{if(!s.paused&&!['idle','done','ended'].includes(s.phase))pause();$('reference-dialog').showModal();};$('reference-close').onclick=()=>$('reference-dialog').close();
$('export-log').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(exportSnapshot(),null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=sim.taskId+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),0);};
$('interact').hidden=false;
