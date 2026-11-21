'use strict';

// World: right-handed, Y up, ground X/Z, one unit ≈ one conceptual metre.
// Robot and visitor roots share local +Z forward. Trail distances are world units.
class SimulationClock {
 constructor(update, draw, onError) {
  this.update=update;
  this.draw=draw;
  this.onError=onError;
  this.frameId=null;
  this.previous=null;
  this.running=false;
  this.frames=0;
  this.tick=this.tick.bind(this);
 }
 start() {
  if(this.running)return;
  this.running=true;
  this.previous=null;
  this.frameId=requestAnimationFrame(this.tick);
 }
 stop() {
  this.running=false;
  if(this.frameId!==null)cancelAnimationFrame(this.frameId);
  this.frameId=null;
  this.previous=null;
 }
 rebase() { this.previous=null; }
 tick(now) {
  this.frameId=null;
  if(!this.running)return;
  try{
   const delta=this.previous===null?0:Math.max(0,Math.min((now-this.previous)/1000,.25));
   this.previous=now;
   // Substeps constrain displacement without accumulating background-tab debt.
   let remaining=delta*(this.simRate||1);
   while(remaining>1e-6){
    const dt=Math.min(remaining,1/60);
    this.update(dt);
    remaining-=dt;
   }
   this.draw(delta);
   this.frames++;
   if(this.running)this.frameId=requestAnimationFrame(this.tick);
  }catch(error){
   this.stop();
   this.onError(error);
  }
 }
}

const VISITOR_GAPS=[1.15,1.95,2.75];
class TourTrail {
 constructor(entry) {
  this.distance=0;
  this.points=[{...ENTRY_QUEUE,distance:-Math.hypot(ENTRY_QUEUE.x-entry.x,ENTRY_QUEUE.z-entry.z)},{...entry,distance:0}];
 }
 append(x,z) {
  const last=this.points[this.points.length-1];
  const length=Math.hypot(x-last.x,z-last.z);
  if(length<1e-9)return;
  this.distance+=length;
  this.points.push({x,z,distance:this.distance});
  while(this.points.length>2&&this.points[1].distance<this.distance-12)this.points.shift();
 }
 sample(gap) {
  const distance=this.distance-gap;
  let i=this.points.length-2;
  while(i>0&&this.points[i].distance>distance)i--;
  const a=this.points[i],b=this.points[i+1];
  const weight=Math.max(0,Math.min(1,(distance-a.distance)/(b.distance-a.distance)));
  return {x:a.x+(b.x-a.x)*weight,z:a.z+(b.z-a.z)*weight,yaw:Math.atan2(b.x-a.x,b.z-a.z)};
 }
}
