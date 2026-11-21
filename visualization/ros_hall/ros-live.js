// Read-only ROS pose overlay. The original standalone demo remains unchanged.
(() => {
 const banner=document.createElement('div');
 banner.style.cssText='position:fixed;z-index:99999;top:0;left:0;right:0;padding:8px;text-align:center;background:#6c3028;color:white;font:16px sans-serif';
 banner.textContent='ROS 仿真联动：等待定位数据';
 document.body.appendChild(banner);
 const answer=document.createElement('div');
 answer.style.cssText='position:fixed;z-index:99998;right:16px;top:55px;max-width:420px;padding:12px;background:#fff8e9;color:#30291f;border:1px solid #b79b73;border-radius:8px;font:15px sans-serif;white-space:pre-wrap;display:none';
 document.body.appendChild(answer);
 document.body.style.paddingTop='40px';
 for(const selector of ['.upgrade-controls','.toolbar','.event-bar','aside','.tour-strip','details.responsibility']) {
  const el=document.querySelector(selector); if(el) el.style.display='none';
 }
 document.querySelectorAll('.sensor-caption').forEach(el=>el.style.display='none');
 const footer=document.querySelector('footer'); if(footer) footer.style.display='none';
 const hint=document.getElementById('scene-hint');
 if(hint) hint.textContent='拖动旋转 · 滚轮缩放 · 导览由 ROS 仿真启动，页面为只读展示';
 let selected=false;
 async function update(){
  try {
   const response=await fetch('/api/pose',{cache:'no-store'});
   const data=await response.json();
   if(!selected && data.layout && typeof switchMap==='function'){
    if(data.layout!==activeMap.id) switchMap(data.layout);
    selected=true;
   }
   if(!data.connected || !sceneReady){
    answer.style.display='none';
    banner.textContent='ROS 仿真联动：定位离线或数据过期（机器人位置暂停更新）';
    banner.style.background='#8a4923'; return;
   }
   s.pos={x:data.x,z:data.z}; s.yaw=data.yaw;
   robot.position.set(data.x,0,data.z); robot.rotation.y=data.yaw;
   needsDraw=true;
   const route=data.route;
   const labels={NAVIGATING:'前往',ARRIVED:'已到达并停车',COMPLETED:'路线完成',ERROR:'导航异常'};
   const tour=data.tour;
   const qa=tour && tour.qa_result;
   if(qa && qa.answer){
    answer.textContent='问答结果（模拟播报，无真实音频）\n'+qa.answer+'\n来源：'+((qa.source||{}).url||'无');
    answer.style.display='block';
   } else answer.style.display='none';
   const tourLabels={IDLE:'待命',GREETING:'迎宾',WAITING_CONSENT:'等待游客同意',PLANNING:'规划路线',NAVIGATING:'前往展区',EXPLAINING:'模拟讲解',QA:'互动问答',RETURNING:'前往出口',PAUSED:'已暂停',COMPLETED:'导览完成',ERROR:'导览异常'};
   const detail=tour ? ' · '+(tourLabels[tour.state]||tour.state||'')+' · '+(tour.reason||'')+
     (tour.qa_waiting?' · 等待提问或结束问答':'') : route ? ' · '+(labels[route.state]||'')+' '+(route.name||'')+
     (route.index ? ' ('+route.index+'/'+route.total+')' : '') : ' · 待命 / 无新鲜路线状态';
   const speed=data.speed_control;
   const speedText=speed ? ' · 速度 '+(speed.state||'')+
     (Number.isFinite(speed.target_speed_mps)?' · 目标 '+speed.target_speed_mps.toFixed(2)+' m/s':'')+
     (speed.actual_speed_source==='simulation' && Number.isFinite(speed.simulated_actual_speed_mps)?
       ' · 模拟速度 '+speed.simulated_actual_speed_mps.toFixed(2)+' m/s':'')+
     (speed.reason?' · '+speed.reason:'') : '';
   banner.textContent='ROS 仿真实时位置 · '+(data.layout==='official'?'官方展厅':'适配展厅')+detail+speedText;
   banner.style.background='#205d50';
  } catch(e) {
   answer.style.display='none';
   banner.textContent='ROS 仿真联动：连接中断（机器人位置暂停更新）';
   banner.style.background='#8a4923';
  }
 }
 setInterval(update,200); update();
})();
