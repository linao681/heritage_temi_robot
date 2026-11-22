// ROS live view with explicitly enabled tour controls.
(() => {
 const banner=document.createElement('div');
 banner.style.cssText='position:fixed;z-index:99999;top:0;left:0;right:0;padding:8px;text-align:center;background:#6c3028;color:white;font:16px sans-serif';
 banner.textContent='DEMO_SIMULATED · 本地演示，等待 ROS 实时源';
 document.body.appendChild(banner);
 const answer=document.createElement('div');
 answer.style.cssText='position:fixed;z-index:99998;right:16px;top:55px;max-width:420px;padding:12px;background:#fff8e9;color:#30291f;border:1px solid #b79b73;border-radius:8px;font:15px sans-serif;white-space:pre-wrap;display:none';
 document.body.appendChild(answer);
 const evidence=document.createElement('section');
 evidence.style.cssText='position:fixed;z-index:99996;left:12px;top:52px;width:min(390px,44vw);max-height:48vh;overflow:auto;padding:10px 12px;background:#f7f1e5;color:#30291f;border:1px solid #b79b73;border-radius:8px;box-shadow:0 4px 18px #0002;font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap;pointer-events:none';
 document.body.appendChild(evidence);
 const interaction=document.createElement('section');
 interaction.style.cssText='position:fixed;z-index:99997;bottom:16px;right:16px;width:min(390px,90vw);padding:14px;background:#f7f1e5;border:1px solid #b79b73;border-radius:8px;color:#30291f;display:none;box-shadow:0 4px 20px #0002';
 interaction.innerHTML='<h3 style="margin:0 0 8px">游客交互 · ROS 实时</h3><div id="ros-interaction-state"></div><div id="ros-interaction-actions" style="display:flex;gap:6px;flex-wrap:wrap;margin:8px 0"></div><div id="ros-interaction-question" style="display:flex;gap:6px"><input aria-label="游客提问" maxlength="500" placeholder="例如：潮州音乐有哪些类型？" style="min-width:0;flex:1"><button>提问</button></div><p aria-live="polite" id="ros-interaction-feedback" style="margin:8px 0 0"></p>';
 document.body.appendChild(interaction);
 const actions=interaction.querySelector('#ros-interaction-actions');
 const status=interaction.querySelector('#ros-interaction-state');
 const questionBox=interaction.querySelector('#ros-interaction-question');
 const input=questionBox.querySelector('input');
 const feedback=interaction.querySelector('#ros-interaction-feedback');
 const voiceButton=document.createElement('button');voiceButton.textContent='开启浏览器演示语音';interaction.appendChild(voiceButton);
 let voiceEnabled=false,lastSpeechId=null;
 voiceButton.onclick=()=>{voiceEnabled=!voiceEnabled;voiceButton.textContent=voiceEnabled?'关闭浏览器演示语音':'开启浏览器演示语音';if(!voiceEnabled)window.speechSynthesis?.cancel();};
 let sending=false;
 async function interact(action, question){
  if(sending)return;
  sending=true;feedback.textContent='等待 ROS 确认…';
  try{
   const response=await fetch('/api/interact',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,question})});
   const result=await response.json();
   feedback.textContent=result.message||'未收到确认';
   if(result.success&&action==='ask')input.value='';
  }catch(e){feedback.textContent='连接失败，请查看当前状态后重试';}
  finally{sending=false;}
 }
 questionBox.querySelector('button').onclick=()=>interact('ask',input.value);
 const controls=[['start','接待游客'],['arm_visitor','等待游客到来'],['accept','同意导览'],['refuse','暂不需要'],['pause','暂停'],['resume','继续导览'],['straggle','队尾放慢'],['gather','提醒集合'],['finish_qa','结束问答'],['manual_takeover','人工接管'],['cancel','结束导览']];
 for(const [action,label] of controls){const button=document.createElement('button');button.textContent=label;button.dataset.action=action;button.onclick=()=>interact(action);actions.appendChild(button);}
 function updateInteraction(data){
  const tour=data.tour, assist=tour?.visitor_assist||{};
  interaction.style.display=data.interactive?'block':'none';
  const live=Boolean(data.connected&&tour), state=tour?.state;
  status.textContent=live?(tour.reason||state)+' · 团队确认人数 '+(assist.expected_count||0):'等待实时导览状态';
  const allowed={arm_visitor:assist.can_arm,accept:state==='WAITING_CONSENT'&&(!assist.active||assist.can_accept),refuse:state==='WAITING_CONSENT',pause:['NAVIGATING','RETURNING','EXPLAINING','QA'].includes(state),resume:state==='PAUSED'&&(!assist.active||assist.can_resume),finish_qa:state==='QA'&&tour?.qa_waiting,manual_takeover:!['IDLE','COMPLETED','ERROR'].includes(state),cancel:!['IDLE','COMPLETED','ERROR'].includes(state)};
  allowed.straggle=data.team?.count===3&&['NAVIGATING','RETURNING'].includes(state);
  allowed.start=state==='IDLE'&&data.team?.count===3;
  allowed.gather=data.team?.count===3;
  if(data.team){status.textContent+=' · 队伍 '+data.team.state+' · 落后 '+(data.team.lag_m||0).toFixed(1)+' m';allowed.resume=allowed.resume&&data.team.gathered;}
  actions.querySelectorAll('button').forEach(button=>button.disabled=!live||sending||!allowed[button.dataset.action]);
  questionBox.querySelector('button').disabled=!live||sending||state!=='QA'||!tour?.qa_waiting;
 }
 document.body.style.paddingTop='40px';
 for(const selector of ['.upgrade-controls','.toolbar','.event-bar','aside','.tour-strip','details.responsibility']) {
  const el=document.querySelector(selector); if(el) el.style.display='none';
 }
 document.querySelectorAll('.sensor-caption').forEach(el=>el.style.display='none');
 const footer=document.querySelector('footer'); if(footer) footer.style.display='none';
 const hint=document.getElementById('scene-hint');
 if(hint) hint.textContent='拖动旋转 · 滚轮缩放 · 导览由 ROS 仿真启动，页面为只读展示';
 let selected=false,liveSourceSeen=false;
 let liveScene=null, liveVisitors=new Map();
 function age(sample){return Number.isFinite(sample?.age_sec)?(sample.age_sec*1000).toFixed(0)+' ms':'无数据';}
 function updateEvidence(data){
  const e=data.evidence||{}, rows=['ROS 技术证据 · 结构化数据（未接入相机视频）'];
  const rgb=e.rgb_camera_info, depth=e.depth_camera_info;
  rows.push('CameraInfo RGB '+(rgb?.fresh&&rgb.value?.valid?rgb.value.frame_id+' '+rgb.value.width+'×'+rgb.value.height+' · '+age(rgb):'无效/过期 · '+age(rgb)));
  rows.push('CameraInfo Depth '+(depth?.fresh&&depth.value?.valid?depth.value.frame_id+' '+depth.value.width+'×'+depth.value.height+' · '+age(depth):'无效/过期 · '+age(depth)));
  const depthImage=e.depth_image;
  rows.push(depthImage?.fresh&&depthImage.value?.valid?'Depth有效像素 '+depthImage.value.valid_pixels+'/'+depthImage.value.total_pixels+' · '+(depthImage.value.valid_fraction*100).toFixed(1)+'% · 中位数 '+depthImage.value.median_m.toFixed(2)+' m · '+age(depthImage):'Depth有效像素 无效/过期 · '+age(depthImage));
  const cameraTf=e.camera_tf,tfValue=cameraTf?.value;
  rows.push(tfValue?.valid?'Camera TF '+tfValue.source_frame+' → '+tfValue.target_frame+' · '+(tfValue.is_static?'静态':'动态 '+age(cameraTf))+' · '+tfValue.translation_m.z.toFixed(2)+' m':'Camera TF 无效/不可用');
  const tracks=e.tracks;
  if(tracks?.fresh&&tracks.value?.valid){
   const people=tracks.value.tracks||[];
   rows.push('YOLOX 匿名跟踪 '+people.length+' 人 · '+age(tracks));
   for(const p of people.slice(0,5)){
    const distance=p.distance_valid&&Number.isFinite(p.distance_m)?p.distance_m.toFixed(2)+' m':'距离无效';
    const box=Array.isArray(p.bbox)?p.bbox.map(v=>Number(v).toFixed(2)).join(','):'框无效';
    rows.push('  '+p.track_id+' '+p.observation_state+' · '+distance+' · bbox '+box);
   }
  }else rows.push('YOLOX 匿名跟踪 无效/过期 · '+age(tracks));
  const team=e.team_observation, tv=team?.value;
  rows.push(tv?('视觉团队 '+(team.fresh?tv.observation_state:'过期')+' · '+(tv.observed_count??'—')+'/'+(tv.expected_count??'—')+' · '+tv.source+' · '+age(team)):'视觉团队 无数据');
  if(tv)rows.push('  人工确认 '+(tv.requires_manual_confirmation?'需要':'未请求')+' · '+(tv.reason||''));
  const scripted=data.team;
  rows.push(scripted?'Gazebo脚本真值 '+(scripted.count??'—')+' 人 · '+(scripted.state||'')+'（与视觉分开）':'Gazebo脚本真值 无数据/过期');
  const fused=e.fused, fv=fused?.value;
  rows.push(fv&&fused.fresh?'Fusion '+fv.source+' · '+(fv.valid?'有效':'无效')+' · '+age(fused)+' · '+(fv.warning||fv.error||'无告警'):'Fusion 无效/过期 · '+age(fused));
  const scan=e.scan;
  rows.push(scan?.fresh&&scan.value?.valid?'LaserScan 最近障碍 '+scan.value.minimum_distance_m.toFixed(2)+' m · '+scan.value.frame_id+' · '+age(scan):'LaserScan 无效/过期 · '+age(scan));
  const speed=data.speed_control, cmd=e.cmd_vel, odom=e.odom;
  rows.push(speed?'速度控制 '+(speed.state||'—')+' · target '+(Number.isFinite(speed.target_speed_mps)?speed.target_speed_mps.toFixed(2)+' m/s':'无效')+' · '+(speed.reason||''):'速度控制 无数据/过期');
  rows.push(cmd?.fresh?'cmd_vel '+cmd.value.linear_speed_mps.toFixed(2)+' m/s · '+cmd.value.angular_speed_rps.toFixed(2)+' rad/s · '+age(cmd):'cmd_vel 无效/过期 · '+age(cmd));
  rows.push(odom?.fresh?'odom 实际 '+odom.value.linear_speed_mps.toFixed(2)+' m/s · '+odom.value.angular_speed_rps.toFixed(2)+' rad/s · '+age(odom):'odom 实际速度 无效/过期 · '+age(odom));
  if(speed)rows.push('安全状态 '+(speed.stop_confirmed?'STOP_CONFIRMED':speed.state||'—')+' · 动态停车距离 '+(Number.isFinite(speed.dynamic_stop_distance_m)?speed.dynamic_stop_distance_m.toFixed(2)+' m':'无效')+' · UUID '+(speed.navigation_session_id||'无'));
  rows.push('Nav2 限速独立回读：'+(e.nav2_limit_readback?.valid?'有效':'当前接口未提供'));
  evidence.textContent=rows.join('\n');
 }
 function updateVisitors(poses){
  if(!sceneReady)return;
  if(scene!==liveScene){liveScene=scene;liveVisitors=new Map();}
  const seen=new Set();
  for(const p of poses||[]){
   if(!p.id||![p.x,p.z,p.yaw].every(Number.isFinite))continue;
   seen.add(p.id);
   let model=liveVisitors.get(p.id);
   if(!model){model=visitor(0xbd7352,1.65);liveVisitors.set(p.id,model);}
   const delta=Math.hypot(p.x-model.position.x,p.z-model.position.z);
   model.userData.liveTravel=(model.userData.liveTravel||0)+(model.visible?delta:0);
   model.visible=true;model.position.set(p.x,0,p.z);model.rotation.y=p.yaw;
   animateVisitor(model,model.userData.liveTravel,delta>.015,.2);
  }
  for(const [id,model] of liveVisitors)if(!seen.has(id))model.visible=false;
  needsDraw=true;
 }
 async function update(){
  try {
   const response=await fetch('/api/pose',{cache:'no-store'});
   const data=await response.json();
   liveSourceSeen=true;
   updateInteraction(data);
   updateEvidence(data);
   if(data.speech?.task_id&&data.speech.task_id!==lastSpeechId){
    lastSpeechId=data.speech.task_id;
    if(voiceEnabled&&window.speechSynthesis){const utterance=new SpeechSynthesisUtterance(data.speech.text);utterance.lang='zh-CN';speechSynthesis.cancel();speechSynthesis.speak(utterance);}
   }
   if(!selected && data.layout && typeof switchMap==='function'){
    if(data.layout!==activeMap.id) switchMap(data.layout);
    selected=true;
   }
   if(!data.connected || !sceneReady){
    updateVisitors(null);
    answer.style.display='none';
    banner.textContent='ROS 仿真联动：定位离线或数据过期（机器人位置暂停更新）';
    banner.style.background='#8a4923'; return;
   }
   s.pos={x:data.x,z:data.z}; s.yaw=data.yaw;
   robot.position.set(data.x,0,data.z); robot.rotation.y=data.yaw;
   needsDraw=true;
   updateVisitors(data.visitors);
   const route=data.route;
   const labels={NAVIGATING:'前往',ARRIVED:'已到达并停车',COMPLETED:'路线完成',ERROR:'导航异常'};
   const tour=data.tour;
   const qa=tour && tour.qa_result;
   if(tour?.state==='QA' && qa && qa.answer){
    answer.textContent='问答结果（模拟播报，无真实音频）\n'+qa.answer+'\n来源：'+((qa.source||{}).url||'无');
    answer.style.display='block';
   } else if(data.speech?.text){answer.textContent='机器人讲解（模拟播报）\n'+data.speech.text;answer.style.display='block';}
   else answer.style.display='none';
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
   const visitorsText=Array.isArray(data.visitors)?' · 场内游客 '+data.visitors.length+' 人（Gazebo 真值）':' · 游客位置暂无新鲜数据';
   banner.textContent='LIVE_ROS2 · ROS仿真实时位置 · '+(data.layout==='official'?'官方展厅':'适配展厅')+detail+speedText+visitorsText;
   banner.style.background='#205d50';
  } catch(e) {
   updateInteraction({interactive:interaction.style.display==='block',connected:false});
   updateEvidence({});
   updateVisitors(null);
   answer.style.display='none';
   banner.textContent=liveSourceSeen?'LIVE_ROS2 · 连接中断（数据无效，机器人位置暂停更新）':'DEMO_SIMULATED · ROS未连接，本地静态演示';
   banner.style.background='#8a4923';
  }
 }
 setInterval(update,200); update();
})();
