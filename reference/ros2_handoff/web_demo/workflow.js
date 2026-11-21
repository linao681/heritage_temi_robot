'use strict';
function captureTask(){
 if(!s.returnTask){const phase=s.stopRequest?.originalPhase||s.phase;s.returnTask={phase,elapsed:s.elapsed,paused:s.paused,questionReturn:s.questionReturn,index:s.index,path:s.path.map(p=>({...p})),waypoint:s.waypoint};}
}
function controlledStop(action){
 if(s.phase==='estop')return false;
 if(s.stopRequest){if(action.kind==='fault')s.stopRequest.action=action;return true;}
 s.stopRequest={action,originalPhase:s.phase,startedAt:sim.time,initialV:sim.v,initialW:sim.w,initialPose:{...s.pos}};s.phase='stopping';silence();
 if(Math.abs(sim.v)<1e-6&&Math.abs(sim.w)<1e-6)finishControlledStop();else{show('06 / 平稳停车','正在减速，请稍候','按加速度约束降到零速后再处理请求。');renderUI();}return true;
}
function stoppingStep(dt){
 const v=ramp(sim.v,0,MODEL.motion.aMax,dt),w=ramp(sim.w,0,MODEL.motion.alphaMax,dt),yaw=s.yaw+(sim.w+w)*.5*dt;
 const travel=(sim.v+v)*.5*dt,p={x:s.pos.x+travel*Math.sin((s.yaw+yaw)/2),z:s.pos.z+travel*Math.cos((s.yaw+yaw)/2)};
 if(trafficNear(p,.86)||freeVisitors.some(a=>distance(p,a)<.78)||!walkable(p,s.obstacles)||s.party.members.some(m=>distance(p,m)<.67)||s.crowd&&distance(p,s.crowd.pos)<.78){hardStop();log('停车安全屏障触发 → 立即零速');}
 else{sim.v=v;sim.w=w;s.pos=p;s.yaw=angleDiff(yaw,0);s.trail.append(p.x,p.z);s.distanceMoved=travel>.00001;}
 if(Math.abs(sim.v)<1e-6&&Math.abs(sim.w)<1e-6)finishControlledStop();
}
function finishControlledStop(){
 const request=s.stopRequest;if(!request)return;s.stopRequest=null;const action=request.action;
 sim.stops.push({startedAt:request.startedAt,stoppedAt:sim.time,initialV:request.initialV,initialW:request.initialW,initialPose:request.initialPose,finalPose:{...s.pos},action:action.kind,finalV:sim.v,finalW:sim.w});
 if(action.kind==='pause'){s.phase=request.originalPhase;s.paused=true;show('06 / 暂停','已平稳停稳','位姿与任务已保留，点击继续恢复。');}
 else if(action.kind==='question'){s.phase=request.originalPhase;answerQuestion(action.question);return;}
 else if(action.kind==='clarify'){s.phase='clarifying';show('06 / 指令确认','已停稳，请再说一次','可重试语音或使用屏幕确认；连续两次失败将请求人工。');}
 else if(action.kind==='regroup'){s.phase='regroup';show('06 / 集合','已停稳，请提醒队尾归队','沿实际走过的轨迹集合，确认全部游客到齐后恢复。');}
 else if(action.kind==='fault'){s.phase=faultPhase();show('06 / 安全处置',states[s.phase]||'已停稳',action.reason+'。请通过工作人员工作台检查并处理。');}
 else if(action.kind==='crowd'){sim.metrics.crowdWaits++;s.phase='crowd_wait';if(s.crowd?.mode==='viewing')show('06 / 驻足游客避让','游客正在看展，正在规划绕行','机器人先停稳，检查游客与队伍安全距离；有安全路线再绕行。');else show('06 / 动态人流让行','已停稳，让行人先通过','持续畅通后恢复；持续占道尝试绕行或请求人工。');log('动态行人接近 → 停车让行');}
 else if(action.kind==='exit'){s.phase=request.originalPhase;beginExit(action.reason);return;}
 else if(action.kind==='end'){s.phase=request.originalPhase;endTour();return;}
 s.elapsed=0;renderUI();cameraForPhase();
}
function pause(){
 if(['idle','done','ended','stopping'].includes(s.phase))return;
 if(s.paused){s.paused=false;log('游客继续 → 从零速恢复当前任务');renderUI();return;}
 controlledStop({kind:'pause'});log('游客暂停 → 按减速度停车后冻结');
}
function ask(question){const q=question.trim();if(!q||s.paused||!['moving','speaking','question'].includes(s.phase))return;controlledStop({kind:'question',question:q});}
function unclearCommand(){
 if(s.paused||!s.accepted||s.phase==='estop')return;
 sim.unclear++;log('模拟语音未识别 → '+sim.unclear+' 次');
 if(sim.unclear>=2){interrupt('manual','连续两次未听清游客指令');return;}
 captureTask();controlledStop({kind:'clarify'});
}
function clarifySuccess(screen=false){if(s.phase!=='clarifying'||s.paused)return;sim.unclear=0;log(screen?'屏幕确认指令成功 → 恢复原任务':'语音重试成功 → 恢复原任务');restoreTask();}
function interrupt(kind,reason){
 if(['idle','done','ended'].includes(s.phase))return;
 reason=reason||({lost:'定位可靠性不足',perception:'观测质量不足',estop:'急停锁定',manual:'游客请求人工协助',blocked:'路线受阻'})[kind];
 if(s.faults.some(f=>f.kind===kind&&f.reason===reason))return;captureTask();s.faults.push({kind,reason,at:sim.time});
 if(kind==='estop'){
  if(s.endRequest){s.paused=s.endRequest.paused;s.endRequest=null;}
  s.pauseBeforeEstop=s.paused;s.paused=false;s.interruptedStop=s.stopRequest;s.stopRequest=null;hardStop();s.phase='estop';s.elapsed=0;
  show('06 / 急停','急停已锁定','请工作人员检查现场并确认安全后解除；叠加异常仍须分别处理。');
 }else if(s.phase!=='estop')controlledStop({kind:'fault',reason});
 openHandoff(reason);log('异常触发 → '+kind+' / '+reason);renderUI();cameraForPhase();
}
function applyStaffAction(action=$('staff-action').value){
 const h=s.handoff;if(!h||h.status!=='pending'||s.phase==='stopping')return false;
 h.safetyConfirmed=false;$('staff-safe').checked=false;
 if(action==='clear')clearObstacles();
 else if(action==='regroup'){if(s.regroup)gather();else if(!queueIntact()){toast('队伍未完整，请先处理集合');return false;}}
 else if(action==='localize'){if(!requestRelocalization())return false;}
 else if(action==='replan'){if(!plan([],true)){toast('仍无安全路径，不能恢复');h.replanned=false;return false;}h.replanned=true;}
 else if(action==='takeover'){h.takeoverRequested=true;}
 else if(action==='exit'){h.exitRequested=true;if(!plan([],true)){toast('当前任务路线仍受阻，请清障后规划出口');return false;}}
 else if(action!=='review')return false;
 h.handling.push({action,t:sim.time,revision:h.revision,by:s.autoAssist?'demo-script':'simulated-staff'});log((s.autoAssist?'演示脚本模拟工作人员':'模拟工作人员')+'执行 → '+action);renderUI();return true;
}
function resume(){
 const h=s.handoff;if(!h||h.status!=='pending'||!s.faults.length||s.stopRequest)return;
 if(!h.handling.some(a=>a.revision===h.revision)||!$('staff-safe').checked){toast('请先执行处理动作，再勾选现场安全确认');return;}
 h.safetyConfirmed=true;
 if(s.phase==='estop'&&s.faults.some(f=>f.kind!=='estop')){
  s.faults=s.faults.filter(f=>f.kind!=='estop');hardStop();s.paused=!!s.pauseBeforeEstop;s.pauseBeforeEstop=false;log('工作人员确认安全 → 解除急停');
  if(s.faults.length){s.phase=faultPhase();renderUI();return;}
 }
 if(s.paused||s.endRequest){toast('请先取消暂停或结束确认');return;}
 if(s.accepted&&s.party.members.length&&(s.regroup||!queueIntact())){toast('须先集合并核实全员到齐');return;}
 const crowdLimit=s.crowd?.mode==='viewing'&&s.crowd.detoured?.90:MODEL.crowd.clearDistance;
 if(trafficNear(s.pos,.95)||s.crowd&&distance(s.pos,s.crowd.pos)<crowdLimit){toast('人流仍占道，请先疏导');return;}
 const kinds=s.faults.map(f=>f.kind);
 if(kinds.includes('perception')&&(sim.sensor.profile||s.confidence<.82)){toast('请执行重定位检查并等待观测质量恢复');return;}
 if(!sim.localization.ready||sim.localization.recovering){toast('请等待连续可靠观测完成定位恢复');return;}
 if(kinds.includes('battery')||h.takeoverRequested){
  if(!h.takeoverRequested){toast('低电量不能恢复机器人导览，请选择人工接续游客服务');return;}
  if(kinds.includes('blocked')&&!h.replanned){toast('请先处理受阻并核实安全通路');return;}
  s.faults=[];closeHandoff();endRobotService('工作人员确认接续游客服务','staff');return;
 }
 if((kinds.includes('blocked')||s.returnTask?.phase==='moving')&&!h.replanned){toast('请先执行重新规划动作');return;}
 if(s.accepted&&!plan([],true)){toast('路径仍不可达，不能恢复');return;}
 if(kinds.includes('perception'))sim.metrics.sensorRecoveries++;
 s.faults=[];s.freeCrowdWait=null;s.freeClearFor=0;if(!s.interruptedStop)sim.unclear=0;closeHandoff();log('人工处理动作、安全、队列与路径核实通过 → 恢复');
 if(s.interruptedStop?.action.kind==='clarify'){s.interruptedStop=null;s.phase='clarifying';show('06 / 指令确认','急停已解除，请重试原指令','已保留中断前的指令确认和导览任务。');renderUI();return;}s.interruptedStop=null;
 if(h.exitRequested){s.returnTask=null;beginExit('工作人员协助前往出口');}else restoreTask();
}
function exitBearing(){
 const angle=angleDiff(Math.atan2(EXIT.x-s.pos.x,EXIT.z-s.pos.z),s.yaw),labels=['正前方','右前方','右侧','右后方','正后方','左后方','左侧','左前方'];
 return labels[(Math.round(angle/(Math.PI/4))+8)%8];
}
function step(dt){
 s.distanceMoved=false;if(s.faults.some(f=>f.kind==='estop')&&s.phase!=='estop'){s.phase='estop';s.stopRequest=null;hardStop();renderUI();}
 if(s.paused){hardStop();return;}updateFreeVisitors(dt);updateTraffic(dt);if(['done','ended'].includes(s.phase)){sim.time+=dt;hardStop();return;}
 const before={...s.pos,yaw:s.yaw};sim.time+=dt;s.elapsed+=dt;
 if(!s.accepted){if(s.phase==='stopping')stoppingStep(dt);if(s.phase==='estop')hardStop();if(!s.paused)updateReception(dt);updateSensing(dt,before);if(s.auto)autoAdvance();return;}
 updateCrowd(dt);monitorCrowd(dt);
 if(s.phase==='stopping')stoppingStep(dt);else if(s.phase==='moving'||s.phase==='parking')drive(dt);else if(s.phase==='docking')dock(dt);else hardStop();
 if(s.phase!=='estop')updateFollowers(dt);updateSensing(dt,before);if(!s.serviceOutcome)updateMetrics(dt,before);
 sim.battery=Math.max(0,sim.battery-distance(before,s.pos)*MODEL.battery.percentPerMetre-dt*MODEL.battery.percentPerSecond);handleLowBattery();
 if(s.regroup&&s.regroup.elapsed>MODEL.queue.regroupTimeout&&!s.faults.some(f=>f.reason.includes('集合超时')))interrupt('manual','游客集合超时，需要工作人员确认人数');
 const last=sim.trajectory.at(-1);if(!last||sim.time-last.t>=MODEL.performance.trajectorySeconds){sim.trajectory.push({t:sim.time,...s.pos,yaw:s.yaw,v:sim.v,w:sim.w,phase:s.phase,estimatedPose:{...sim.localization.estimate},confidence:s.confidence,members:s.party.members.map(m=>({id:m.id,x:m.x,z:m.z,progress:m.progress,lag:m.lag}))});if(sim.trajectory.length>MODEL.performance.maxTrajectory){sim.trajectory.shift();sim.droppedTrajectory++;}}
 if(s.auto)autoAdvance();
}
function autoAdvance(){
 const narrating=$('voice').checked&&window.speechSynthesis&&(window.speechSynthesis.speaking||window.speechSynthesis.pending);if(narrating&&['greeting','speaking','question','feedback'].includes(s.phase))return;
 const fast=sim.testMode==='fast-demo';
 if(s.phase==='greeting'&&s.elapsed>1.3)acceptTour();
 else if(s.phase==='confirming'&&s.elapsed>1.2&&s.reception.stableFor>1&&s.entrants.every(a=>!a.path.length)){const n=s.reception.count;$('audience').value=n===1?'individual':$('audience').value==='family'?'family':'group';$('party-size').value=String(n);confirmParty();}
 else if(s.phase==='moving'){
  if(!s.obstacleDone&&s.elapsed>1){if(freeVisitors.length){s.obstacleDone=true;log('混合人流演示 → 使用已在馆游客进行避让，不重复注入演练行人');}else if(injectCrowd('viewing'))s.obstacleDone=true;}
  if(s.index===1&&!s.questionDone&&s.elapsed>5){s.questionDone=true;ask('请问出口在哪里？');}
 }else if(s.phase==='speaking'&&s.index===3&&!s.humanDone&&s.elapsed>(fast?3:5)){s.humanDone=true;ask('这件作品值多少钱？');}
 else if(s.phase==='speaking'&&s.index<5&&!s.exploration.completed.includes(s.index)&&s.elapsed>2){if($('quiz').hidden)openExploration();else answerExploration(EXPLORATION_TASKS[s.index].correct);}
 else if(s.phase==='speaking'&&s.elapsed>(fast?4:8))next();
 else if(s.phase==='question'&&s.elapsed>(fast?3:6))next();
 else if(s.phase==='manual'&&s.autoAssist&&s.elapsed>3){
  log('演示脚本：模拟工作人员核实未知问题；未连接远程人工');applyStaffAction('review');applyStaffAction('replan');$('staff-safe').checked=true;resume();s.autoAssist=false;
 }else if(s.phase==='feedback'&&s.elapsed>(fast?2:5))next();
}
