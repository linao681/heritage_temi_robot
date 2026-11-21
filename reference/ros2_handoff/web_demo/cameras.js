'use strict';
let fixtureBounds=new Map();
function cacheFixtureBounds(){fixtureBounds=new Map();scene.updateMatrixWorld(true);for(const f of MAP_FIXTURES){const o=scene.getObjectByName(f.id);if(o)fixtureBounds.set(f.id,new THREE.Box3().setFromObject(o));}}
function serviceBounds(mode='exhibit'){
 const bounds=new THREE.Box3().setFromCenterAndSize(new THREE.Vector3(s.pos.x,.82,s.pos.z),new THREE.Vector3(.85,1.64,.85));
 for(const m of s.accepted?s.party.members:s.entrants.filter(a=>a.active!==false)){
  const h=m.role==='child'?1.1:1.65;bounds.union(new THREE.Box3().setFromCenterAndSize(new THREE.Vector3(m.x,h/2,m.z),new THREE.Vector3(.65,h,.65)));
 }
 if(mode==='exhibit'&&s.accepted&&s.index<5){const exhibit=fixtureBounds.get(activeMap.exhibitIds[s.index]);if(exhibit)bounds.union(exhibit);}
 return bounds;
}
function fitServiceCamera(mode='exhibit'){
 const bounds=serviceBounds(mode),center=bounds.getCenter(new THREE.Vector3()),size=bounds.getSize(new THREE.Vector3());
 const vfov=THREE.MathUtils.degToRad(camera.fov),hfov=2*Math.atan(Math.tan(vfov/2)*camera.aspect),radius=size.length()/2;
 const distance=radius/Math.sin(Math.min(vfov,hfov)/2)*1.13;
 const zone=zones[Math.min(s.index,4)],base=mode==='exhibit'&&s.accepted?Math.atan2(s.pos.x-zone.x,s.pos.z-zone.z):s.yaw+Math.PI;
 let fallback=null;
 for(const elevation of [38,52,68,82])for(const offset of [.38,-.38,0,.85,-.85,Math.PI]){
  const phi=THREE.MathUtils.degToRad(elevation),a=base+offset;
  const position=new THREE.Vector3(center.x+Math.sin(a)*distance*Math.cos(phi),center.y+distance*Math.sin(phi),center.z+Math.cos(a)*distance*Math.cos(phi));
  const candidate={target:center,position,bounds};fallback=candidate;
  if(Math.abs(position.x)>PLAN_W/2-.2||Math.abs(position.z)>PLAN_D/2+3)continue;
  if([...fixtureBounds.values()].some(b=>b.clone().expandByScalar(.16).containsPoint(position)))continue;
  // Avoid a tall cabinet between camera and the robot/visitors. Low showcases remain visible from above.
  const subjects=[new THREE.Vector3(s.pos.x,1.0,s.pos.z),...(s.accepted?s.party.members:s.entrants).map(m=>new THREE.Vector3(m.x,1.0,m.z))];
  const hidden=subjects.some(target=>{const ray=new THREE.Ray(position,target.clone().sub(position).normalize()),len=position.distanceTo(target);return [...fixtureBounds.entries()].some(([id,b])=>{if(id===activeMap.exhibitIds[s.index]&&mode==='exhibit')return false;const hit=ray.intersectBox(b,new THREE.Vector3());return hit&&hit.distanceTo(position)<len-.4;});});
  if(!hidden)return candidate;
 }
 return fallback;
}
function cameraForPhase(){if(!$('auto-camera').checked)return;selectCamera(s.phase==='moving'?'follow':['arriving','forming','greeting','confirming','speaking','question','manual','clarifying','regroup'].includes(s.phase)?'exhibit':'overview');}
function cameraFramingReport(mode='exhibit'){
 const fit=fitServiceCamera(mode),probe=camera.clone();probe.position.copy(fit.position);probe.lookAt(fit.target);probe.updateMatrixWorld(true);const b=fit.bounds,points=[];
 for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z])points.push(new THREE.Vector3(x,y,z).project(probe));
 return {maxNdcX:Math.max(...points.map(p=>Math.abs(p.x))),maxNdcY:Math.max(...points.map(p=>Math.abs(p.y))),allVisible:points.every(p=>Math.abs(p.x)<.94&&Math.abs(p.y)<.94&&p.z<1&&p.z> -1),position:fit.position.toArray(),bounds:{min:b.min.toArray(),max:b.max.toArray()}};
}
