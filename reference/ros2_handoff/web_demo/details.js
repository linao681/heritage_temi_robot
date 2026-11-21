'use strict';
// Surface and exhibit detail pass. The authoritative floor plan is unchanged.
let floorReflection;
function detailTexture(kind){
 const c=document.createElement('canvas');c.width=1024;c.height=512;const a=c.getContext('2d');
 if(kind==='wood'){
  a.fillStyle='#79563b';a.fillRect(0,0,1024,512);
  for(let i=0;i<220;i++){const y=i*2.4;a.strokeStyle=i%3?'#98724f55':'#39281d55';a.lineWidth=.7+i%3*.5;a.beginPath();for(let x=0;x<=1024;x+=12){const py=y+Math.sin(x*.008+i)*2.8+Math.sin(x*.026+i*.3);x?a.lineTo(x,py):a.moveTo(x,py);}a.stroke();}
 }else{
  a.fillStyle='#264761';a.fillRect(0,0,1024,512);
  for(let j=0;j<4;j++)for(let i=0;i<9;i++){
   const x=40+i*120+(j%2)*50,y=45+j*138;a.save();a.translate(x,y);
   for(let k=0;k<8;k++){a.rotate(Math.PI/4);a.fillStyle=k%2?'#bc9856':'#d6b76e';a.beginPath();a.ellipse(0,-23,9,21,0,0,Math.PI*2);a.fill();}
   a.fillStyle='#e1c98d';a.beginPath();a.arc(0,0,8,0,Math.PI*2);a.fill();a.restore();
  }
  a.strokeStyle='#d4b56f';a.lineWidth=7;for(const y of [12,32,480,500]){a.beginPath();a.moveTo(0,y);a.lineTo(1024,y);a.stroke();}
 }
 const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;t.wrapS=t.wrapT=THREE.RepeatWrapping;return t;
}
const simpleMaterials=setupMaterials;
setupMaterials=function(){
 simpleMaterials();mats.wood.color.set(0xffffff);mats.wood.map=detailTexture('wood');mats.wood.roughness=.48;
 mats.enamel=material(0xffffff,{map:detailTexture('enamel'),roughness:.22,metalness:.22});
 mats.celadon=material(0x8aada5,{roughness:.21,metalness:.1});mats.canopy=material(0xd8be8d,{roughness:.4,metalness:.2,emissive:0x503918,emissiveIntensity:.2});
};
const simpleUrn=urn;
urn=function(parent,x,y,z,scale=1,kind=0){
 const before=parent.children.length;simpleUrn(parent,x,y,z,scale,kind);
 const g=parent.children[before];if(kind===1||kind===2){const body=g.children[0];body.material=kind===1?mats.enamel:mats.celadon;}
};
const simpleCase=glassCaseAt;
glassCaseAt=function(f,parent){
 simpleCase(f,parent);
 box(f.w+.012,.075,f.d+.012,mats.darkWood,parent,0,.085,0);
 box(f.w-.045,.025,f.d-.045,mats.gold,parent,0,.15,0);
 for(const sign of [-1,1]){
  box(.012,.49,.018,mats.gold,parent,sign*(f.w/2-.025),.40,f.d/2+.008);
  box(f.w-.05,.018,.013,mats.lamp,parent,0,.167,sign*(f.d/2+.012));
 }
};
const simpleShelf=shelfAt;
shelfAt=function(f,parent,pictures=false){
 simpleShelf(f,parent,pictures);
 // Replace the solid counter face with lit recessed exhibit bays within its footprint.
 const g=parent.children[0],horizontal=f.w>f.d,len=horizontal?f.w:f.d,depth=horizontal?f.d:f.w;
 const front=depth/2,n=Math.max(3,Math.round(len/1.25));
 const solid=g.children[0];g.remove(solid);solid.geometry.dispose();
 box(len,.12,depth,mats.wood,g,0,.12,0);box(len,.08,depth,mats.wood,g,0,.75,0);box(len,.62,.07,mats.wood,g,0,.43,-depth/2+.035);
 for(let i=0;i<=n;i++)box(.06,.62,depth,mats.wood,g,-len/2+i*len/n,.43,0);
 for(let i=0;i<n;i++){
  const x=(i+.5)*len/n-len/2,w=len/n-.10;
  box(w,.45,.018,mats.darkWood,g,x,.43,-depth/2+.075);
  box(w,.025,.025,mats.lamp,g,x,.675,front-.08);
  box(w,.035,.09,mats.paper,g,x,.20,front-.10);
  urn(g,x,.23,front-.18,.22,i%3);
 }
};
function createFloorReflection(){
 // Project a mirrored camera onto the actual floor; no painted reference image.
 const target=new THREE.WebGLRenderTarget(512,320,{minFilter:THREE.LinearFilter,magFilter:THREE.LinearFilter});
 target.samples=0;
 const reflected=new THREE.PerspectiveCamera(),textureMatrix=new THREE.Matrix4();
 const bias=new THREE.Matrix4().set(.5,0,0,.5,0,.5,0,.5,0,0,.5,.5,0,0,0,1);
 const uniforms={map:{value:target.texture},matrix:{value:textureMatrix},eye:{value:new THREE.Vector3()}};
 const colorChunk=THREE.ShaderChunk.colorspace_fragment?'colorspace_fragment':'encodings_fragment';
 const mat=new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,
  vertexShader:'uniform mat4 matrix; varying vec4 projected; varying vec3 worldPos; void main(){vec4 p=modelMatrix*vec4(position,1.);worldPos=p.xyz;projected=matrix*p;gl_Position=projectionMatrix*viewMatrix*p;}',
  fragmentShader:'uniform sampler2D map; uniform vec3 eye; varying vec4 projected; varying vec3 worldPos; void main(){vec3 viewDir=normalize(eye-worldPos);float grazing=pow(1.-max(viewDir.y,0.),3.);vec2 uv=projected.xy/projected.w;vec2 step=vec2(1.4/512.,1.4/320.);vec3 reflection=texture2D(map,uv).rgb*.4;reflection+=(texture2D(map,uv+vec2(step.x,0.)).rgb+texture2D(map,uv-vec2(step.x,0.)).rgb+texture2D(map,uv+vec2(0.,step.y)).rgb+texture2D(map,uv-vec2(0.,step.y)).rgb)*.15;gl_FragColor=vec4(reflection,(.12+.20*grazing));\n#include <tonemapping_fragment>\n#include <'+colorChunk+'>\n}'
 });
 const plane=new THREE.Mesh(new THREE.PlaneGeometry(PLAN_W-.3,PLAN_D-.3),mat);plane.name='石材实时反射';plane.rotation.x=-Math.PI/2;plane.position.y=.023;scene.add(plane);
 const ground=scene.children.filter(o=>o.userData.floorTile),clip=new THREE.Plane(new THREE.Vector3(0,1,0),-.025);
 let capturing=false,lastCapture=-Infinity;
 plane.onBeforeRender=(r,world,view)=>{
  if(capturing||cameraMode==='overview'||view!==camera)return;
  const now=performance.now();if(now-lastCapture<1000/(s.phase==='moving'?MODEL.performance.reflectionMovingHz:MODEL.performance.reflectionHz))return;lastCapture=now;
  capturing=true;const old=r.getRenderTarget(),planes=r.clippingPlanes,xr=r.xr.enabled;
  const saved=ground.map(o=>o.visible);plane.visible=false;ground.forEach(o=>o.visible=false);
  try{
   const look=new THREE.Vector3();view.getWorldDirection(look);look.add(view.position);
   reflected.copy(view);reflected.position.copy(view.position);reflected.position.y=2*plane.position.y-view.position.y;
   look.y=2*plane.position.y-look.y;reflected.up.copy(view.up);reflected.up.y*=-1;reflected.lookAt(look);reflected.updateMatrixWorld();
   textureMatrix.copy(bias).multiply(reflected.projectionMatrix).multiply(reflected.matrixWorldInverse);uniforms.eye.value.copy(view.position);
   r.xr.enabled=false;r.clippingPlanes=[clip];r.setRenderTarget(target);r.clear();r.render(world,reflected);
  }finally{r.setRenderTarget(old);r.clippingPlanes=planes;r.xr.enabled=xr;plane.visible=true;ground.forEach((o,i)=>o.visible=saved[i]);capturing=false;}
 };
 return {plane,target};
}
const simpleHall=buildHall;
buildHall=function(){simpleHall();floorReflection=createFloorReflection();};
const cleanDetailScene=disposeScene;
disposeScene=function(){floorReflection?.target.dispose();floorReflection=null;cleanDetailScene();};
