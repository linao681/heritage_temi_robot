'use strict';
// Authored museum visitors. +Z forward; 1.4 canonical height; pose never alters navigation roots.
let visitorResources=null;
function peopleResources(){
 if(visitorResources)return visitorResources;
 const sphere=new THREE.SphereGeometry(1,20,14),capsule=new THREE.CapsuleGeometry(1,4,5,12);
 const profile=[[.60,.105,.064],[.65,.120,.070],[.76,.119,.072],[.91,.137,.077],[1.035,.151,.074],[1.085,.135,.063],[1.116,.066,.045],[1.128,.036,.032]];
 const points=[],indices=[],segments=28;
 for(const [y,rx,rz] of profile)for(let j=0;j<=segments;j++){const a=j*Math.PI*2/segments;points.push(Math.sin(a)*rx,y,Math.cos(a)*rz);}
 for(let i=0;i<profile.length-1;i++)for(let j=0;j<segments;j++){const a=i*(segments+1)+j,b=a+segments+1;indices.push(a,a+1,b,a+1,b+1,b);}
 const torso=new THREE.BufferGeometry();torso.setAttribute('position',new THREE.Float32BufferAttribute(points,3));torso.setIndex(indices);torso.computeVertexNormals();
 const shadowData=new Uint8Array(64*64*4);for(let y=0;y<64;y++)for(let x=0;x<64;x++){const d=Math.hypot((x-31.5)/31.5,(y-31.5)/31.5),at=(y*64+x)*4;shadowData[at]=shadowData[at+1]=shadowData[at+2]=45;shadowData[at+3]=d<1?Math.round(Math.pow(1-d,2)*86):0;}
 const shadow=new THREE.DataTexture(shadowData,64,64);shadow.needsUpdate=true;
 visitorResources={sphere,capsule,torso,shadowMaterial:new THREE.MeshBasicMaterial({map:shadow,transparent:true,depthWrite:false,side:THREE.DoubleSide}),styles:new Map()};return visitorResources;
}
function visitorStyle(color,variant){
 const r=peopleResources(),key=color+'-'+variant;if(r.styles.has(key))return r.styles.get(key);
 const style={
  skin:material(variant==='short'?0xd8b197:0xe6bfa3,{roughness:.73}),
  hair:material(variant==='short'?0x302923:variant==='child'?0x47352b:0x382a26,{roughness:.77}),
  coat:material(variant==='short'?0x40596b:variant==='child'?0xc69b53:0xb2ab92,{roughness:.9}),
  pants:material(variant==='short'?0x383e49:variant==='child'?0x52656b:0x647367,{roughness:.9}),
  inner:material(0xf0e7d4,{roughness:.95}),shoe:material(variant==='short'?0x594a40:0xd8d4c5,{roughness:.7}),
  sole:material(0xe7e2d6,{roughness:.85}),eye:material(0x2f2926,{roughness:.45}),white:material(0xf4eee7),
  lips:material(0x9f6f60,{roughness:.82}),bag:material(variant==='long'?0x805e46:0x6b6653,{roughness:.8}),trim:material(0xc8ac75,{metalness:.2,roughness:.6})
 };if(color===0x586a7a)style.coat.color.set(0x62747b);
 r.styles.set(key,style);return style;
}
function personOval(parent,mat,x,y,z,sx,sy,sz){
 const mesh=new THREE.Mesh(peopleResources().sphere,mat);mesh.position.set(x,y,z);mesh.scale.set(sx,sy,sz);parent.add(mesh);return mesh;
}
function personLimb(parent,mat,x,y,z,radius,length){
 const mesh=new THREE.Mesh(peopleResources().capsule,mat);mesh.position.set(x,y,z);mesh.scale.set(radius,length/6,radius);parent.add(mesh);return mesh;
}
function personCurve(parent,mat,points,radius=.005){
 const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));
 const m=new THREE.Mesh(new THREE.TubeGeometry(curve,14,radius,6,false),mat);parent.add(m);return m;
}
function personHair(parent,mat,longHair){
 const vertices=[],indices=[],rings=12,segments=32;
 for(let i=0;i<=rings;i++)for(let j=0;j<=segments;j++){
  const az=j*Math.PI*2/segments,front=Math.max(0,Math.cos(az));
  const end=(longHair?1.98:1.83)-front*(longHair?.83:.62),a=end*i/rings;
  vertices.push(Math.sin(az)*Math.sin(a)*.090,Math.cos(a)*.116-.001,Math.cos(az)*Math.sin(a)*.091-.005);
 }
 for(let i=0;i<rings;i++)for(let j=0;j<segments;j++){const a=i*(segments+1)+j,b=a+segments+1;indices.push(a,b,a+1,a+1,b,b+1);}
 const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.setIndex(indices);geo.computeVertexNormals();const m=new THREE.Mesh(geo,mat);parent.add(m);
 // Swept side part, rather than a flat hemisphere sitting on the forehead.
 const fringe=personOval(parent,mat,-.025,.077,.052,.057,.024,.043);fringe.rotation.z=-.24;
 if(longHair){
  personCurve(parent,mat,[[0,.012,-.081],[.019,-.058,-.119],[.027,-.135,-.133]],.033);
  personOval(parent,mat,.024,-.13,-.13,.032,.052,.030);
 }
}
function createVisitor(color,height){
 const variant=height<1.2?'child':color===0x839b79?'long':'short',style=visitorStyle(color,variant),r=peopleResources();
 const group=new THREE.Group();group.name='museum-visitor-'+variant;
 const visual=new THREE.Group();visual.position.y=.027;group.add(visual);
 const body=new THREE.Mesh(r.torso,style.coat);visual.add(body);
 // Open cardigan/jacket and soft tee insert follow the chest surface.
 const insert=new THREE.BufferGeometry();insert.setAttribute('position',new THREE.Float32BufferAttribute([-.054,1.067,.086,.054,1.067,.086,-.036,.79,.086,.036,.79,.086],3));insert.setIndex([0,2,1,1,2,3]);insert.computeVertexNormals();visual.add(new THREE.Mesh(insert,style.inner));
 for(const side of [-1,1])personCurve(visual,style.inner,[[side*.066,1.071,.064],[side*.045,1.015,.079],[side*.033,.935,.079]],.006);
 for(const y of [.77,.83,.89])personOval(visual,style.trim,.021,y,.079,.004,.004,.003);
 personLimb(visual,style.skin,0,1.125,0,.035,.10);
 const head=new THREE.Group();head.position.set(0,1.273,0);visual.add(head);
 personOval(head,style.skin,0,0,0,.083,.104,.082);
 for(const side of [-1,1]){
  personOval(head,style.skin,side*.081,-.009,0,.015,.024,.014);
  personOval(head,style.white,side*.031,.012,.077,.017,.007,.004);
  personOval(head,style.eye,side*.031,.012,.082,.0055,.006,.003);
  personOval(head,style.white,side*.029,.014,.0845,.0015,.0016,.001);
  personCurve(head,style.hair,[[side*.015,.032,.079],[side*.030,.036,.078],[side*.047,.032,.072]],.0028);
 }
 personOval(head,style.skin,0,-.012,.084,.011,.016,.016);
 personCurve(head,style.lips,[[-.020,-.048,.072],[0,-.053,.080],[.020,-.048,.072]],.0024);
 personHair(head,style.hair,variant!=='short');
 if(variant==='child')personOval(head,style.trim,.075,.054,-.025,.020,.018,.014);
 personOval(visual,style.pants,0,.625,0,.117,.065,.062);
 const legs=[],knees=[],arms=[],elbows=[];
 for(const side of [-1,1]){
  const leg=new THREE.Group();leg.position.set(side*.067,.65,0);visual.add(leg);legs.push(leg);
  personLimb(leg,style.pants,0,-.165,0,.053,.34);
  const knee=new THREE.Group();knee.position.y=-.315;leg.add(knee);knees.push(knee);
  personLimb(knee,style.pants,0,-.133,0,.039,.28);
  personOval(knee,style.sole,0,-.300,.035,.052,.017,.103);
  personOval(knee,style.shoe,0,-.278,.034,.049,.032,.098);
  personCurve(knee,style.inner,[[-.022,-.258,.048],[.022,-.258,.048]],.003);
  const arm=new THREE.Group();arm.position.set(side*.162,1.055,0);arm.rotation.z=side*.08;visual.add(arm);arms.push(arm);
  personLimb(arm,style.coat,0,-.095,0,.038,.205);
  const elbow=new THREE.Group();elbow.position.y=-.19;elbow.rotation.x=-.10;arm.add(elbow);elbows.push(elbow);
  personLimb(elbow,variant==='child'?style.coat:style.skin,0,-.073,0,.027,.16);
  personOval(elbow,style.skin,0,-.174,.006,.027,.041,.021);
 }
 if(variant!=='child'){
  personCurve(visual,style.bag,[[.125,1.067,.044],[.031,.87,.085],[-.14,.68,.034]],.007);
  const bag=personOval(visual,style.bag,-.145,.635,.015,.055,.071,.036);bag.rotation.z=-.10;
  personOval(visual,style.trim,-.145,.657,.051,.009,.006,.003);
 }else{
  personCurve(visual,style.inner,[[-.06,1.068,.065],[0,1.035,.082],[.06,1.068,.065]],.009);
 }
 const shadow=new THREE.Mesh(new THREE.PlaneGeometry(.46,.36),r.shadowMaterial);shadow.rotation.x=-Math.PI/2;shadow.position.y=.06;group.add(shadow);
 const marker=new THREE.Mesh(new THREE.RingGeometry(.26,.36,32),new THREE.MeshBasicMaterial({color:0xf07432,side:THREE.DoubleSide,depthWrite:false}));marker.rotation.x=-Math.PI/2;marker.position.y=.068;marker.visible=false;group.add(marker);
 group.userData={legs,knees,arms,elbows,visual,head,body,contactShadow:shadow,queueMarker:marker,variant,role:null,posePhase:0};
 group.traverse(o=>{o.castShadow=false;});group.scale.setScalar(height/1.4);scene.add(group);setVisitorRole(group,height<1.2?'child':'adult');return group;
}
function setVisitorRole(model,role){
 const data=model.userData;data.groundY=.028/model.scale.y-.018;data.visual.position.y=data.groundY;data.contactShadow.position.y=.031/model.scale.y;if(data.role===role)return;data.role=role;
 const child=role==='child';data.head.scale.setScalar(child?1.12:1);data.head.position.y=child?1.252:1.273;data.body.scale.x=child?.93:1;
}
function animateVisitor(model,pathDistance,walking,dt){
 const d=model.userData,phase=pathDistance*12,blend=Math.min(1,dt*12);
 for(let i=0;i<2;i++){
  const cycle=phase+i*Math.PI,swing=walking?Math.sin(cycle)*.30:0,knee=walking?Math.max(0,-Math.sin(cycle))*.38:0;
  d.legs[i].rotation.x+=(swing-d.legs[i].rotation.x)*blend;
  d.knees[i].rotation.x+=(knee-d.knees[i].rotation.x)*blend;
  d.arms[i].rotation.x+=(-swing*.72-d.arms[i].rotation.x)*blend;
  d.elbows[i].rotation.x+=(-.10-Math.max(0,swing)*.25-d.elbows[i].rotation.x)*blend;
 }
 const bob=walking?.005*(1-Math.cos(phase*2)):0;d.visual.position.y+=(d.groundY+bob-d.visual.position.y)*blend;d.posePhase=phase;
}
