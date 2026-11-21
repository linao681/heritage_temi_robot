'use strict';
Object.assign(states,{done:'导览已完成',parking:'机器人独立靠边',battery:'低电量 · 等待人工接续',arriving:'等待稳定入场检测',forming:'实际形成队列',stopping:'按约束减速停车',clarifying:'停稳后重试指令'});
function renderUpgradeUI(){
 if(!s||!sim.sensor)return;
 $('visit-choice').hidden=s.phase!=='done'||!!s.serviceOutcome;
 $('layout-caption').textContent=activeMap.id==='adaptive'?'独立布局 · 分馆式回廊 · 同主题五区展厅':'以官方赛题平面图为布局依据，参考视频优化材质与场景细节';
 $('map-select').disabled=!['idle','done','ended'].includes(s.phase);
 $('arrival-count').disabled=s.accepted;$('add-arrival').disabled=!['idle','arriving','greeting','confirming'].includes(s.phase)||s.entrants.filter(a=>a.active!==false).length>=3||s.reception.departing;
 $('start').disabled=!sceneReady||s.phase!=='idle';$('auto').disabled=$('start').disabled;
 $('party-size').disabled=s.accepted||$('audience').value==='individual';
 $('clarify-card').hidden=s.phase!=='clarifying';
 $('intake-readout').textContent='自由参观 '+freeVisitors.filter(a=>a.active!==false&&!a.leaving).length+' 人 · 自主离馆 '+freeVisitors.filter(a=>a.active!==false&&a.leaving).length+' 人 · 当前接待检测 '+s.reception.count+' 人 · 稳定 '+s.reception.stableFor.toFixed(1)+' s · 跟踪 '+s.reception.tracks.filter(t=>sim.time-t.lastSeen<.22).map(t=>t.id).join('、');
 $('free-visit-readout').textContent=freeVisitors.filter(a=>a.active!==false).map(a=>(a.freeIndex+1)+'号：'+(a.leaving?'自主离馆 / ':a.assistance==='staff'?'人工接续 / ':'')+(a.roamState==='viewing'?(a.targetZone+1)+'区看展':a.roamState==='yielding'?'让行中（目标'+(a.targetZone+1)+'区）':a.roamState==='waiting'?'等通道（目标'+(a.targetZone+1)+'区）':'前往'+(a.targetZone+1)+'区')+' · 已访 '+a.visitedZones.join('、')).join(' / ');
 $('run-mode').textContent=sim.testMode==='fast-demo'?'快速演示 · 模拟时间 3× · 自动模拟游客与工作人员':sim.testMode==='full-demo'?'完整演示 · 正常时间 · 自动模拟游客与工作人员':'交互仿真 · 正常时间';
 if(s.phase==='stopping')for(const id of ['next','skip','repeat','interact','pause','resume','end-tour','unclear','block','crowd','straggler'])$(id).disabled=true;
 if(s.phase==='clarifying')for(const id of ['next','skip','repeat','interact'])$(id).disabled=true;
 $('confirm-party').disabled=s.paused||sim.battery<=MODEL.battery.low;
 $('accept-tour').disabled=s.paused||sim.battery<=MODEL.battery.low;
 $('unclear').disabled=s.paused||!s.accepted||!['moving','speaking','question','clarifying'].includes(s.phase);
 if(s.regroup){$('queue-detail').textContent=s.party.members.map(m=>(m.index+1)+'号 '+m.role+' / 实际落后 '+m.lag.toFixed(2)+' m').join('；')+' · 全员稳定 '+s.regroup.stable.toFixed(1)+' s';$('confirm-regroup').disabled=s.paused||!s.regroup.collecting||!queueIntact()||s.regroup.stable<.5;}
 const h=s.handoff;$('staff-controls').hidden=!h||h.status!=='pending';
 if(h){$('staff-state').textContent='观测 '+s.confidence.toFixed(2)+' / 定位 '+(sim.localization.ready?'可靠':'待恢复')+' / 队列 '+(!s.accepted?'尚未成队':queueIntact()?'完整':'待核实')+' / 本轮处理 '+(h.handling.filter(a=>a.revision===h.revision).map(x=>({review:'核实现场',clear:'清障',regroup:'集合',localize:'重定位',replan:'重新规划',takeover:'人工接续',exit:'按意愿协助离馆'})[x.action]).join('、')||'待处理');$('handoff-detail').textContent='工单 '+h.id+'\n原因：'+h.reasons.join('；')+'\n原问题：'+(h.question||'无')+'\n地图 '+h.mapId+' / 展区 '+(h.zoneId||'出口')+'\n位姿 '+h.pose.x.toFixed(2)+', '+h.pose.z.toFixed(2)+' / 朝向 '+h.pose.yaw.toFixed(2)+' rad\n人数 '+h.party.length+' / 电量 '+h.battery.toFixed(1)+'% / 观测 '+h.sensorConfidence.toFixed(2)+'\n原任务 '+(h.returnTask?.phase||h.deviceState)+' / 创建于 '+h.openedAt.toFixed(2)+' s\n状态 '+h.status;}
 renderMetrics();renderExploration();
}
function switchMap(id){
 if(!MAP_CONFIGS[id]||!['idle','done','ended'].includes(s.phase)){toast('服务进行中禁止换图，请先完成任务或重置');$('map-select').value=activeMap.id;return false;}
 $('map-select').value=id;
 if(id===activeMap.id)return true;clock?.stop();disposeScene();fixtureBounds.clear();selectMapConfig(id);refreshMapBindings();boot();log('地图切换完成 → 场景、碰撞、栅格、目标、入口、出口与传感器均已重建');return sceneReady;
}
