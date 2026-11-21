'use strict';
// Synthetic range observations and wheel odometry are deliberately separate from the true pose.
let sensorSeed=20261108; // Configured repeatable noise; not an empirical sensor distribution.
function sensorRandom(){sensorSeed=(Math.imul(sensorSeed,1664525)+1013904223)>>>0;return sensorSeed/4294967296;}
function resetSensing(){
 sensorSeed=MODEL.sensors.seed;sim.sensor={accumulator:0,rays:[],validRatio:1,inlierRatio:1,innovation:0,confidence:1,glassInfluence:0,profile:null,previous:[]};
 sim.localization={estimate:{...ENTRY,yaw:ENTRY_YAW},sigma:.015,ready:true,profile:null,recovering:false,consistent:0,residual:null};
}
function injectGlassNoise(){if(!s.accepted||s.paused)return;sim.sensor.profile='reflection';log('模拟反光：射线丢失、离群回波、跳变增强；等待观测质量阈值触发');}
function injectLocalizationLoss(){if(!s.accepted||s.paused)return;sim.localization.profile='wheel-slip';log('模拟轮式里程计漂移与不确定性增长；等待定位可靠性阈值触发');}
function updateSensing(dt,before){
 const loc=sim.localization,move=distance(before,s.pos),dyaw=angleDiff(s.yaw,before.yaw),slip=loc.profile==='wheel-slip';
 const bias=slip?.30:.003;
 loc.estimate.x+=move*Math.sin(before.yaw+dyaw/2)*(1+bias)+(slip?.06:0)*dt;
 loc.estimate.z+=move*Math.cos(before.yaw+dyaw/2)*(1+bias);
 loc.estimate.yaw=angleDiff(loc.estimate.yaw+dyaw+(slip?.035:.00003)*dt,0);
 loc.sigma+=move*(slip?.12:.0005)+dt*(slip?.035:.00002);
 const sensor=sim.sensor;sensor.accumulator+=dt;if(sensor.accumulator<1/MODEL.sensors.range.hz)return;sensor.accumulator=0;
 const glass=activeMap.glassRegions.reduce((v,f)=>Math.max(v,Math.max(0,1-fixtureDistance(s.pos,f)/(f.influence+1.0))),0);sensor.glassInfluence=glass;
 const severity=sensor.profile==='reflection'?.95:.08*glass;
 const obstacles=[...s.obstacles,...[...freeVisitors,...trafficPeople()].map(a=>({x:a.x,z:a.z,radius:.27})),...(s.crowd?[{...s.crowd.pos,radius:.27}]:[])];
 const rays=[];let valid=0,inlier=0,innovation=0,jumps=0;
 for(let i=0;i<MODEL.sensors.range.rays;i++){
  const a=i*THREE.MathUtils.degToRad(MODEL.sensors.range.fovDegrees)/MODEL.sensors.range.rays,actual=rayDistance(s.pos,s.yaw+a,MODEL.sensors.range.maxRange,obstacles),drop=sensorRandom()<severity*.48;
  let measured=actual+(sensorRandom()-.5)*(.018+severity*.15);
  if(sensorRandom()<severity*.38)measured=.25+sensorRandom()*4.5;
  measured=drop?null:Math.max(.05,Math.min(5,measured));
  const expected=rayDistance(loc.estimate,loc.estimate.yaw+a,5,obstacles),error=measured===null?null:Math.abs(measured-expected);
  if(measured!==null){valid++;innovation+=Math.min(1,error);if(error<.20)inlier++;const old=sensor.previous[i];if(old!=null&&Math.abs(old-measured)>.8)jumps++;}
  rays.push({angle:a,distance:measured,expected,innovation:error});
 }
 sensor.rays=rays;sensor.previous=rays.map(r=>r.distance);sensor.validRatio=valid/MODEL.sensors.range.rays;sensor.inlierRatio=valid?inlier/valid:0;sensor.innovation=valid?innovation/valid:1;
 const quality=sensor.validRatio*(.55+.45*sensor.inlierRatio)*Math.max(.4,1-jumps/MODEL.sensors.range.rays);
 sensor.confidence+=.28*(quality-sensor.confidence);s.confidence=sensor.confidence;
 if(s.accepted&&!s.stopRequest&&!s.faults.some(f=>f.kind==='perception')&&sensor.confidence<.60)interrupt('perception','观测有效率与地图一致性下降，感知受限');
 if(s.accepted&&!s.faults.some(f=>f.kind==='lost')&&(loc.sigma>.18||sensor.innovation>.35&&loc.profile)){
  loc.ready=false;interrupt('lost','里程计不确定性或观测残差超阈值');
 }
 if(loc.recovering)relocalizationStep();
}
function requestRelocalization(){
 if(Math.abs(sim.v)>.001||Math.abs(sim.w)>.001){toast('请等机器人停稳后重定位');return false;}
 sim.sensor.profile=null;sim.localization.profile=null;sim.localization.recovering=true;sim.localization.ready=false;sim.localization.consistent=0;sim.localization.matchLevel=0;sim.localization.recoveryStartedAt=sim.time;
 log('工作人员启动预置地图扫描匹配 → 等待连续可靠观测；非 SLAM');return true;
}
function scanCost(p){
 const rays=sim.sensor.rays.filter(r=>r.distance!==null),errors=[];
 // Keep every valid bearing: percentile trimming can discard the few rays that
 // distinguish positions along a corridor. Cap outliers without deleting bearings.
 for(const r of rays)errors.push(Math.min(.30,Math.abs(rayDistance(p,p.yaw+r.angle,MODEL.sensors.range.maxRange,s.obstacles)-r.distance)));
 return errors.reduce((v,e)=>v+e,0)/(errors.length||1);
}
function relocalizationStep(){
 const loc=sim.localization,sensor=sim.sensor;if(sensor.validRatio<.85||sensor.profile){loc.consistent=0;return;}
 if(loc.matchLevel<3){
  const step=[.15,.05,.015][loc.matchLevel],range=loc.matchLevel===0?4:2,angleStep=[.12,.025,.008][loc.matchLevel],base={...loc.estimate};
  let best={...base},score=scanCost(best);
  for(let x=-range;x<=range;x++)for(let z=-range;z<=range;z++)for(let a=-2;a<=2;a++){
   const candidate={x:base.x+x*step,z:base.z+z*step,yaw:base.yaw+a*angleStep};if(!walkable(candidate,s.obstacles))continue;const cost=scanCost(candidate);if(cost<score){score=cost;best=candidate;}
  }
  loc.estimate=best;loc.residual=score;loc.matchLevel++;
 }
 loc.residual=scanCost(loc.estimate);
 if(loc.residual<.06&&sensor.inlierRatio>.85){loc.consistent++;loc.sigma=Math.max(.02,loc.sigma*.78);}else loc.consistent=0;
 if(loc.consistent>=8&&loc.sigma<.06){loc.ready=true;loc.recovering=false;sim.metrics.localizationRecoveries++;sim.localization.recoverySeconds=sim.time-loc.recoveryStartedAt;sim.metrics.localizationRecoverySeconds.push(sim.localization.recoverySeconds);log('地图匹配连续 8 帧一致 → 定位可恢复，残差 '+loc.residual.toFixed(3)+' m');renderUI();}
}
function updatePerception(){
 const sensor=sim.sensor;if(!sensor)return;const vertices=[];let minimum=5;
 for(const r of sensor.rays){const d=r.distance??0,a=s.yaw+r.angle;minimum=Math.min(minimum,r.distance??5);vertices.push(s.pos.x,.16,s.pos.z,s.pos.x+Math.sin(a)*d,.16,s.pos.z+Math.cos(a)*d);}
 if(vertices.length){
  if(!sensorLines){sensorLines=new THREE.LineSegments(new THREE.BufferGeometry(),new THREE.LineBasicMaterial({color:0xe7b766,transparent:true,opacity:.24}));scene.add(sensorLines);}
  const current=sensorLines.geometry.attributes.position;if(!current||current.array.length!==vertices.length)sensorLines.geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));else{current.array.set(vertices);current.needsUpdate=true;}sensorLines.geometry.computeBoundingSphere();sensorLines.visible=$('sensors').checked;
 }
 sim.range=minimum;const canvas=$('depth-view'),ctx=canvas.getContext('2d');ctx.fillStyle='#272523';ctx.fillRect(0,0,canvas.width,canvas.height);
 sensor.rays.forEach((r,i)=>{ctx.fillStyle=r.distance===null?'#ae5142':s.confidence<.6?'#d89662':'#d3b17a';const h=r.distance===null?5:8+(1-r.distance/5)*60;ctx.fillRect(i*8,76-h,7,h);});
 $('velocity').textContent=sim.v.toFixed(2)+' m/s';$('omega').textContent=sim.w.toFixed(2)+' rad/s';$('nearest').textContent=minimum.toFixed(2)+' m';$('power').textContent=sim.battery.toFixed(1)+'%';
 const loc=sim.localization;$('topics').textContent='模拟射线 / 有效率 '+(sensor.validRatio*100).toFixed(0)+'% / 一致率 '+(sensor.inlierRatio*100).toFixed(0)+'%\n观测置信度 '+s.confidence.toFixed(2)+' / 里程计 σ '+loc.sigma.toFixed(3)+' m\n估计位姿 x '+loc.estimate.x.toFixed(2)+' / z '+loc.estimate.z.toFixed(2)+'\n定位异常监测/恢复演示；导航仍用仿真真值\n测距360°/36线；前向人数108°；ROS/SDK未接入';if(sensorLines?.visible)needsDraw=true;renderUpgradeUI();
}
