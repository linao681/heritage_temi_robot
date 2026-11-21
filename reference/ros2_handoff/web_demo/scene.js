'use strict';
// New visual scene authored from the supplied presentation images.
// Right handed; Y up; ground X/Z; robot local +Z forward; conceptual metres.
let ceilingGroup,robotScreen,robotScreenCanvas,robotScreenTexture,robotStatusMaterial;
let robotScreenKey='';
const panelCache=new Map();
function imagePanel(name){
 if(panelCache.has(name))return panelCache.get(name);
 const t=new THREE.TextureLoader().load(REFERENCE_PANELS[name],()=>{needsDraw=true;});
 t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=renderer.capabilities.getMaxAnisotropy();
 const m=material(0xffffff,{map:t,roughness:.85,side:THREE.DoubleSide});panelCache.set(name,m);return m;
}
function setupMaterials(){
 Object.assign(mats,{
  ivory:material(0xd5c8b0),wood:material(0x664932,{roughness:.48}),darkWood:material(0x34281f),
  gold:material(0xb99356,{metalness:.7,roughness:.3}),bronze:material(0x98733c,{metalness:.7,roughness:.33}),
  paper:material(0xe5d7bd),red:material(0xb04b39),tire:material(0x1e2224),
  skin:material(0xcaa88a),hair:material(0x272221),pants:material(0x3d4248),
  glass:material(0xd4e6ed,{transparent:true,opacity:.10,roughness:.08,metalness:.18,depthWrite:false}),
  lamp:new THREE.MeshBasicMaterial({color:0xffdfa0}),white:material(0xe7e9e6,{roughness:.25,metalness:.12}),
  black:material(0x111b22,{roughness:.23,metalness:.2}),blue:new THREE.MeshBasicMaterial({color:0x78d8ff}),
  silver:material(0xaeb5ba,{roughness:.28,metalness:.38}),silverEdge:material(0xb7bdc0,{roughness:.24,metalness:.65}),
  stone:material(0x666056,{roughness:.23,metalness:.2}),lacquer:material(0x201b17,{roughness:.2,metalness:.25}),
 });
}
function lathe(profile,mat,parent,x=0,y=0,z=0){
 return mesh(new THREE.LatheGeometry(profile.map(p=>new THREE.Vector2(...p)),48),mat,parent,x,y,z);
}
function rounded(w,h,d,r,mat,parent,x=0,y=0,z=0){
 const a=w/2,b=h/2,s=new THREE.Shape();
 s.moveTo(-a+r,-b);s.lineTo(a-r,-b);s.quadraticCurveTo(a,-b,a,-b+r);s.lineTo(a,b-r);
 s.quadraticCurveTo(a,b,a-r,b);s.lineTo(-a+r,b);s.quadraticCurveTo(-a,b,-a,b-r);
 s.lineTo(-a,-b+r);s.quadraticCurveTo(-a,-b,-a+r,-b);
 const geo=new THREE.ExtrudeGeometry(s,{depth:d,bevelEnabled:true,bevelSize:.012,bevelThickness:.012,bevelSegments:2,curveSegments:8});geo.translate(0,0,-d/2);
 return mesh(geo,mat,parent,x,y,z);
}
function textTexture(title,subtitle='',kind='board'){
 const c=document.createElement('canvas');c.width=1024;c.height=kind==='screen'?512:256;
 const ctx=c.getContext('2d');const screen=kind==='screen';
 ctx.fillStyle=screen?'#12222f':'#d9c7a6';ctx.fillRect(0,0,c.width,c.height);
 ctx.fillStyle=screen?'#84dbff':'#4a3825';ctx.textAlign='center';ctx.font='500 62px "Microsoft YaHei",sans-serif';ctx.fillText(title,512,screen?190:110);
 ctx.fillStyle=screen?'#c9dbe2':'#786343';ctx.font='28px "Microsoft YaHei",sans-serif';ctx.fillText(subtitle,512,screen?300:177);
 ctx.fillStyle=screen?'#5695ac':'#b09460';ctx.fillRect(180,screen?340:210,664,3);
 const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;return t;
}
function plaque(parent,text,x,y,z,w=3,angle=0){
 const g=new THREE.Group();g.position.set(x,y,z);g.rotation.y=angle;parent.add(g);
 box(w,.46,.05,mats.darkWood,g);mesh(new THREE.PlaneGeometry(w-.08,.4),new THREE.MeshBasicMaterial({map:textTexture(text)}),g,0,0,.031);
}
function litStrip(parent,w,x,y,z){box(w,.035,.055,mats.lamp,parent,x,y,z);}
function urn(parent,x,y,z,scale=1,kind=0){
 const g=new THREE.Group();g.position.set(x,y,z);g.scale.setScalar(scale);parent.add(g);
 const profile=kind===1?[[.13,0],[.18,.03],[.30,.15],[.30,.45],[.17,.6],[.12,.68],[.12,.9],[.22,.96]]:
  [[.14,0],[.19,.04],[.25,.12],[.31,.32],[.28,.56],[.17,.67],[.13,.75],[.19,.81]];
 lathe(profile,kind===2?mats.paper:mats.bronze,g);
 for(const h of [.12,.35,.59]){const ring=mesh(new THREE.TorusGeometry(h===.35?.307:.23,.014,6,40),mats.gold,g,0,h,0);ring.rotation.x=Math.PI/2;}
 if(kind===1)for(const side of [-1,1]){const handle=mesh(new THREE.TorusGeometry(.15,.026,8,24,Math.PI*1.7),mats.gold,g,side*.28,.60,0);handle.rotation.y=Math.PI/2;}
}
// Geometry is generated from layout.js; no independent exhibit coordinates.
let zoneFloorGroup,recommendedRouteGroup;
function planPolygon(parent,points,mat,y=.04){
 const shape=new THREE.Shape();points.forEach(([x,z],i)=>{const p=planPoint(x,z);i?shape.lineTo(p.x,-p.z):shape.moveTo(p.x,-p.z);});shape.closePath();
 const m=mesh(new THREE.ShapeGeometry(shape),mat,parent,0,y,0);m.rotation.x=-Math.PI/2;return m;
}
function wallText(parent,text,w,h,x,y,z,angle=0){
 const group=new THREE.Group();group.position.set(x,y,z);group.rotation.y=angle;parent.add(group);
 mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:textTexture(text,'非遗展厅','board')}),group,0,0,.02);
 return group;
}
// Exhibit illustrations and display content; no room photographs embedded in displays.
function exhibitPanel(kind,index=0){
 if(kind==='story'||kind==='story-screen')return storyPanel(kind,index);
 const key='exhibit-'+kind+'-'+index;if(panelCache.has(key))return panelCache.get(key);
 const gallery=['craft','work'].includes(kind),c=document.createElement('canvas');
 c.width=gallery?480:1536;c.height=gallery?360:kind==='table'?512:864;
 const a=c.getContext('2d');a.fillStyle=kind==='interactive'?'#183747':'#eee5d6';a.fillRect(0,0,c.width,c.height);
 const text=(t,x,y,size,color='#4c3a27')=>{a.fillStyle=color;a.font='500 '+size+'px "Microsoft YaHei",sans-serif';a.textAlign='left';a.fillText(t,x,y);};
 const pot=(x,y,scale,color='#476b72')=>{
  a.save();a.translate(x,y);a.scale(scale,scale);a.fillStyle=color;a.beginPath();a.moveTo(-35,-90);a.lineTo(35,-90);a.lineTo(25,-55);a.bezierCurveTo(90,-25,95,65,57,82);a.lineTo(-57,82);a.bezierCurveTo(-95,65,-90,-25,-25,-55);a.closePath();a.fill();a.strokeStyle='#c7a365';a.lineWidth=5;for(const z of [-32,15,58]){a.beginPath();a.moveTo(-55,z);a.lineTo(55,z);a.stroke();}a.restore();
 };
 const tool=(x,y,scale)=>{a.save();a.translate(x,y);a.scale(scale,scale);a.rotate(-.5);a.fillStyle='#8e633a';a.fillRect(-12,-105,24,183);a.fillStyle='#b29a6b';a.fillRect(-55,65,110,35);a.restore();};
 if(gallery){
  const titles={craft:['材料','工具','操作','观察','传习','成品'],work:['器形','纹样','装饰','材料','结构','细节']}[kind];
  a.fillStyle='#dbccb3';a.fillRect(16,16,448,328);text(titles[index%6],30,63,34);
  if(kind==='craft'&&index%3!==2)tool(240,193,1);else pot(240,198,1.05,index%2?'#496d73':'#99743b');
  text(kind==='craft'?'材料 — 工具 — 工序':'观察形态与制作细节',58,324,22,'#75624a');
 }else if(kind==='interactive'){
  text('互动体验 · 纹样观察',62,90,53,'#f3e5ca');
  a.strokeStyle='#c8ac72';a.lineWidth=8;
  for(const r of [180,228,278]){a.beginPath();a.arc(424,437,r,0,Math.PI*2);a.stroke();}
  for(let i=0;i<12;i++){a.save();a.translate(424,437);a.rotate(i*Math.PI/6);a.fillStyle=i%2?'#7dabb2':'#cbb67e';a.beginPath();a.ellipse(0,-118,42,100,0,0,Math.PI*2);a.fill();a.restore();}
  ['认识纹样','观察工具','探索工序'].forEach((t,i)=>{a.fillStyle='#2b505e';a.fillRect(850,212+i*157,590,115);text(String(i+1).padStart(2,'0'),885,287+i*157,42,'#cbb67e');text(t,1002,287+i*157,42,'#f3e5ca');});
  text('真实动手体验请由工作人员指导',62,817,34,'#c4d7d6');
 }else{
  a.fillStyle='#243b46';a.fillRect(0,0,1536,102);text('从工具与工序了解一门技艺',48,69,43,'#f6ead5');
  ['材料','工具','操作','成品'].forEach((t,i)=>{a.fillStyle=i%2?'#d5ddda':'#dfd0b3';a.fillRect(42+i*373,135,332,304);text(t,72+i*373,187,32);if(i===1||i===2)tool(207+i*373,300,.65);else pot(207+i*373,306,.70);});
  text('先观察，再提问；真实体验请听从工作人员指导。',48,487,29,'#7f6b4e');
 }
 const texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;
 const mat=new THREE.MeshBasicMaterial({map:texture,toneMapped:false});panelCache.set(key,mat);return mat;
}

function pictureGallery(parent,w,h,columns,x,y,z,angle=0,kind='craft'){
 const group=new THREE.Group();group.position.set(x,y,z);group.rotation.y=angle;parent.add(group);
 box(w,h,.10,mats.paper,group);
 const rows=2,cw=w/columns,ch=h/rows;
 for(let row=0;row<rows;row++)for(let col=0;col<columns;col++){
  const px=-w/2+cw*(col+.5),py=h/2-ch*(row+.5);
  box(cw*.82,ch*.84,.035,mats.ivory,group,px,py,.07);
  const iw=Math.min(cw*.72,ch*.52*4/3);
  const image=mesh(new THREE.PlaneGeometry(iw,iw*3/4),exhibitPanel(kind,(row*columns+col)%6),group,px,py+.07,.10);
  box(cw*.64,.018,.01,mats.darkWood,group,px,py-ch*.28,.10);
  box(cw*.54,.012,.01,mats.gold,group,px,py-ch*.36,.10);
 }return group;
}
function glassCaseAt(f,parent){
 const w=f.w,d=f.d;
 box(w,.58,d,mats.wood,parent,0,.32,0);box(w,.06,d,mats.lacquer,parent,0,.64,0);box(w-.09,.025,d-.09,mats.paper,parent,0,.69,0);
 const glass=box(w-.045,1.6,d-.045,mats.glass,parent,0,1.51,0);glass.castShadow=false;
 glass.add(new THREE.LineSegments(new THREE.EdgesGeometry(glass.geometry),new THREE.LineBasicMaterial({color:0x948570,transparent:true,opacity:.64})));
 for(const side of [-1,1]){
  box(w,.035,.035,mats.silverEdge,parent,0,2.33,side*d/2);box(.035,.035,d,mats.silverEdge,parent,side*w/2,2.33,0);
  box(w-.06,.012,.018,mats.lamp,parent,0,2.307,side*(d/2-.03));
 }
 for(const z of [-d/2,d/2])litStrip(parent,w-.04,0,.10,z);
 const horizontal=f.orientation==='horizontal',n=f.count||1;
 for(let i=0;i<n;i++){
  const span=horizontal?w:d,pos=(i-(n-1)/2)*(span/n),x=horizontal?pos:0,z=horizontal?0:pos;
  if(f.lacquer&&i===Math.floor(n/2)){
   const cw=w/n*.75;box(cw,.44,d*.55,mats.lacquer,parent,x,1.04,z);
   for(const y of [.83,1.25])box(cw+.03,.025,d*.58,mats.gold,parent,x,y,z);
   for(const dx of [-cw*.42,cw*.42])box(.025,.45,d*.57,mats.gold,parent,x+dx,1.04,z);
   const ring=mesh(new THREE.TorusGeometry(.13,.018,6,24),mats.gold,parent,x,1.05,z+d*.28);
  }else urn(parent,x,.71,z,n===1?1.05:.82,i%3);
  const label=box(.30,.018,.18,mats.paper,parent,x+.24,.72,z+.36);label.rotation.x=-.12;
 }
}
function shelfAt(f,parent,wallPictures=false){
 const horizontal=f.w>f.d,len=horizontal?f.w:f.d,depth=horizontal?f.d:f.w;
 const g=new THREE.Group();g.rotation.y=horizontal?(['works-front','story-counter'].includes(f.id)?Math.PI:0):-Math.PI/2;parent.add(g);
 box(len,.75,depth,mats.wood,g,0,.40,0);box(len,.055,depth,mats.lacquer,g,0,.81,0);
 litStrip(g,len-.05,0,.12,depth/2+.015);
 const n=f.count||5;
 for(let i=0;i<n;i++){
  const x=(i+.5)*len/n-len/2;box(len/n-.055,.035,depth-.08,mats.paper,g,x,.86,0);
  urn(g,x,.88,0,.40,i%3);
  if(i<n-1)box(.035,.7,depth,mats.gold,g,x+len/n*.5,.4,0);
 }
 if(wallPictures){
  box(len,2.8,.10,mats.ivory,g,0,2.10,-depth/2+.04);litStrip(g,len,0,3.48,-depth/2+.11);
  pictureGallery(g,len-.2,1.85,Math.max(3,Math.round(len/1.15)),0,2.32,-depth/2+.11,0,f.id==='works-front'?'work':'craft');
 }
}
function roomAt(f,parent){
 const h=PLAN.height,th=.16,w=f.w,d=f.d;
 box(w,.035,d,mats.stone,parent,0,.025,0);
 box(w,h,th,mats.ivory,parent,0,h/2,-d/2);
 box(th,h,d,mats.ivory,parent,w/2,h/2,0);
 if(f.door==='south'){
  box(th,h,d,mats.ivory,parent,-w/2,h/2,0);
  const doorway=Math.min(1.05,w*.48),side=(w-doorway)/2;
  for(const sign of [-1,1])box(side,h,th,mats.ivory,parent,sign*(doorway+side)/2,h/2,d/2);
  box(doorway,h-2.2,th,mats.ivory,parent,0,2.2+(h-2.2)/2,d/2);
  box(doorway,2.15,.05,mats.darkWood,parent,0,1.1,d/2-.05);
  wallText(parent,f.label,w-.1,.6,0,2.9,d/2+.09);
 }else{
  box(w,h,th,mats.ivory,parent,0,h/2,d/2);
  const doorway=1.0,side=(d-doorway)/2;
  for(const sign of [-1,1])box(th,h,side,mats.ivory,parent,-w/2,h/2,sign*(doorway+side)/2);
  box(th,h-2.2,doorway,mats.ivory,parent,-w/2,2.2+(h-2.2)/2,0);
  box(.05,2.15,doorway,mats.darkWood,parent,-w/2+.04,1.1,0);
  wallText(parent,f.label,d-.1,.6,-w/2-.09,2.9,0,-Math.PI/2);
 }
}
// Zone 1 uses authored exhibit content, rather than a photograph of another zone.
function overviewPanel(kind){
 const key='overview-'+kind;if(panelCache.has(key))return panelCache.get(key);
 const c=document.createElement('canvas');c.width=kind==='kiosk'?1536:2048;c.height=kind==='kiosk'?864:900;
 const ctx=c.getContext('2d');ctx.fillStyle='#eee5d5';ctx.fillRect(0,0,c.width,c.height);ctx.textAlign='left';ctx.textBaseline='alphabetic';
 const text=(value,x,y,size,color='#493825')=>{ctx.font='500 '+size+'px "Microsoft YaHei",sans-serif';ctx.fillStyle=color;ctx.fillText(value,x,y);};
 if(kind==='kiosk'){
  ctx.fillStyle='#243e4a';ctx.fillRect(0,0,c.width,126);text('非遗概览 · 展厅导览',54,82,52,'#f6ead2');
  const scale=1.29,px=x=>66+(x-PLAN.rect[0])*scale,py=y=>184+(y-PLAN.rect[1])*scale;
  ctx.fillStyle='#d5d2c8';ctx.fillRect(46,164,922,596);
  const colors=['#cab48f','#b8c49b','#9ebdca','#b9aac5','#d7aeb5'];
  PLAN_ZONES.forEach((zone,i)=>{ctx.beginPath();zone.polygon.forEach(([x,y],j)=>j?ctx.lineTo(px(x),py(y)):ctx.moveTo(px(x),py(y)));ctx.closePath();ctx.fillStyle=colors[i];ctx.fill();});
  ctx.fillStyle='#81725e';for(const f of PLAN_FIXTURES){const [x0,y0,x1,y1]=f.pixels;ctx.fillRect(px(x0),py(y0),(x1-x0)*scale,(y1-y0)*scale);}
  ctx.beginPath();ctx.arc(px(PLAN_CORE.pixel[0]),py(PLAN_CORE.pixel[1]),27,0,Math.PI*2);ctx.fillStyle='#97733d';ctx.fill();
  PLAN_ZONES.forEach((zone,i)=>text(String(i+1),px(zone.labelAt[0])-9,py(zone.labelAt[1])+9,30,'#302e29'));
  text('入口',px(270),py(442)+38,28);text('出口',px(681),py(442)+38,28);
  text('依次走近五个展区',1020,198,36);
  ['非遗概览','传统工艺','代表作品','传承故事','互动体验'].forEach((label,i)=>{ctx.fillStyle=colors[i];ctx.fillRect(1020,236+i*103,430,82);text(String(i+1).padStart(2,'0'),1042,290+i*103,33);text(label,1120,290+i*103,32);});
  text('认识非遗  ·  理解传承  ·  尊重多样文化',54,830,30,'#796446');
 }else{
  text('认识非遗，走近活态传承',72,110,64);
  const wrap=(value,x,y,width)=>{let line='';for(const char of value){const next=line+char;if(ctx.measureText(next).width>width&&line){ctx.fillText(line,x,y);line=char;y+=49;}else line=next;}if(line)ctx.fillText(line,x,y);};
  GUIDE_CARDS[0].forEach((part,i)=>{const y=212+i*150;ctx.fillStyle='#ab824b';ctx.fillRect(74,y-42,7,104);text(GUIDE_PARTS[i],106,y,43);ctx.font='34px "Microsoft YaHei",sans-serif';ctx.fillStyle='#6d5b43';wrap(part.text,420,y-2,1530);});
  text('参观顺序  概览 → 工艺 → 作品 → 传承 → 互动',74,848,34,'#8d714b');
 }
 const texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;
 const mat=new THREE.MeshBasicMaterial({map:texture,toneMapped:false});panelCache.set(key,mat);return mat;
}
function overviewMapPanel(){
 const mat=imagePanel('overview-relief-source');
 if(mat.map){
  // UV crop of the provided reference: relief only, excluding the photographed kiosk.
  mat.map.repeat.set(198/1304,143/734);mat.map.offset.set(10/1304,1-287/734);mat.map.needsUpdate=true;
 }
 return mat;
}
function overviewWallAt(f,g){
 const w=f.w,d=f.d;box(w,3.1,d,mats.ivory,g,0,1.55,0);
 const face=new THREE.Group();face.position.set(w/2+.025,0,0);face.rotation.y=Math.PI/2;g.add(face);
 const map=mesh(new THREE.PlaneGeometry(3.05,2.2),overviewMapPanel(),face,-(d/2-1.74),1.42,.016);map.name='overview-relief-map';
 mesh(new THREE.PlaneGeometry(d-3.75,2.15),overviewPanel('wall'),face,1.60,1.42,.017);
 box(d-.10,.035,.035,mats.lamp,face,0,2.97,.04);box(d-.10,.04,.04,mats.gold,face,0,.25,.025);
}
function overviewKioskAt(f,g){
 const width=Math.min(f.d-.18,1.72),height=width*9/16;
 box(f.w*.65,.08,width*.78,mats.black,g,0,.06,0);
 box(f.w*.30,.84,width*.34,mats.black,g,-.10,.48,0);
 const top=new THREE.Group();top.name='overview-kiosk-head';top.position.set(0,1.14,0);
 // Yaw around world up first, then pitch around the display's own horizontal axis.
 top.rotation.order='YXZ';top.rotation.y=Math.PI/2;top.rotation.x=-.82;g.add(top);
 rounded(width,height,.10,.035,mats.gold,top);
 rounded(width-.045,height-.045,.105,.028,mats.black,top,0,0,.01);
 const screen=mesh(new THREE.PlaneGeometry(width-.11,(width-.11)*9/16),overviewPanel('kiosk'),top,0,0,.09);screen.name='overview-kiosk-screen';
}

function fixtureAt(f){
 const g=new THREE.Group();g.name=f.id;g.userData.fixtureId=f.id;g.userData.planPixels=f.pixels||f.pixelSegment;g.position.set(f.x,0,f.z);g.rotation.y=f.angle||0;scene.add(g);
 const w=f.w,d=f.d;
 if(f.kind==='glass')glassCaseAt(f,g);
 else if(f.kind==='room')roomAt(f,g);
 else if(f.kind==='partition'){
  box(w,f.height,d,mats.ivory,g,0,f.height/2,0);box(w,.055,d+.035,mats.darkWood,g,0,f.height+.025,0);
 }else if(f.kind==='wall-cabinet')shelfAt(f,g,['craft-back','works-front'].includes(f.id));
 else if(f.kind==='workbench'){
  box(w,.12,d,mats.wood,g,0,.89,0);box(w-.06,.028,d-.06,mats.paper,g,0,.963,0);
  for(const x of [-w*.43,w*.43])for(const z of [-d*.38,d*.38])box(.09,.84,.09,mats.wood,g,x,.42,z);
  for(let i=0;i<7;i++){const tool=box(.045,.035,.34,mats.gold,g,-w*.35+i*w*.11,.999,d*.12);tool.rotation.y=i*.23;}
  urn(g,-w*.27,.99,-d*.17,.31);box(w*.3,.04,d*.40,mats.wood,g,w*.20,1.0,-d*.1);
 }else if(f.kind==='stool'){
  cylinder(w/2,w/2,.08,mats.wood,g,0,.44,0);for(const x of [-w*.28,w*.28])for(const z of [-d*.28,d*.28])box(.045,.40,.045,mats.wood,g,x,.20,z);
 }else if(f.kind==='tools'){
  box(w,.74,d,mats.wood,g,0,.4,0);box(w-.08,.04,d-.08,mats.paper,g,0,.81,0);
  for(let i=0;i<6;i++){const tool=box(.055,.055,d*.46,mats.gold,g,-w*.36+i*w*.14,.86,0);tool.rotation.y=.2;}
  const cover=box(w-.08,.37,d-.08,mats.glass,g,0,1.025,0);cover.castShadow=false;
  cover.add(new THREE.LineSegments(new THREE.EdgesGeometry(cover.geometry),new THREE.LineBasicMaterial({color:0x9f8b6d,transparent:true,opacity:.75})));
  for(const x of [-w*.3,0,w*.3])urn(g,x,.86,-d*.24,.17,1);
 }else if(f.kind==='relief')overviewWallAt(f,g);
 else if(f.kind==='kiosk'){overviewKioskAt(f,g);
 }else if(f.kind==='portrait-wall'){
  box(w,3,d,mats.ivory,g,0,1.5,0);pictureGallery(g,d-.1,2.2,6,-w/2-.06,1.8,0,-Math.PI/2,'story');
 }else if(f.kind==='story-screen'){
  // Low multimedia island as drawn in the plan, without an invented full-height wall.
  box(w,.64,d,mats.wood,g,0,.35,0);box(w-.08,.06,d-.08,mats.darkWood,g,0,.70,0);
  const sw=w*.91,sh=sw*9/16,top=new THREE.Group();top.position.set(0,.80+sh*Math.cos(.95)/2,0);top.rotation.x=-.95;g.add(top);
  rounded(sw,sh,.10,.04,mats.black,top);
  const display=mesh(new THREE.PlaneGeometry(sw-.12,(sw-.12)*9/16),exhibitPanel('story-screen'),top,0,0,.085);display.name='story-display-surface';
  litStrip(g,w-.1,0,.16,d/2+.03);
 }else if(f.kind==='interactive-screen'){
  const sw=w-.30,sh=sw*9/16;
  box(w,3.35,d,mats.wood,g,0,1.68,0);box(sw,sh,.09,mats.black,g,0,1.75,d/2+.07);
  const display=mesh(new THREE.PlaneGeometry(sw-.12,(sw-.12)*9/16),exhibitPanel('interactive'),g,0,1.75,d/2+.13);display.name='interactive-display-surface';
 }else if(f.kind==='touch-table'){
  box(w,.78,d,mats.wood,g,0,.42,0);litStrip(g,w-.1,0,.13,d/2+.02);
  const top=new THREE.Group();top.position.set(0,.96,.07);top.rotation.x=-1.19;g.add(top);
  rounded(w-.16,d*.94,.09,.08,mats.black,top);
  const display=mesh(new THREE.PlaneGeometry(w-.33,(w-.33)/3),exhibitPanel('table'),top,0,0,.08);display.name='interactive-table-surface';
 }else if(['souvenir-shelf','shop'].includes(f.kind)){
  // Open west-facing shelving, not artifacts buried in a solid wooden block.
  const count=f.kind==='shop'?4:6;
  box(.07,3.3,d,mats.wood,g,w/2-.035,1.65,0);box(w,.12,d,mats.wood,g,0,.10,0);
  for(let col=0;col<=count;col++)box(w,3.18,.05,mats.wood,g,0,1.69,-d/2+col*d/count);
  for(let row=0;row<3;row++){
   const y=.66+row*.87;box(w,.055,d,mats.paper,g,0,y,0);box(.022,.026,d-.08,mats.lamp,g,-w/2+.03,y-.06,0);
   for(let col=0;col<count;col++)urn(g,-w*.10,y+.04,(col+.5)*d/count-d/2,.34,(row+col)%3);
  }
  if(f.kind==='shop')wallText(g,'文创商店',d-.1,.5,-w/2-.04,3.55,0,-Math.PI/2);
 }else if(f.kind==='sign-pier'){
  box(w,3.6,d,mats.wood,g,0,1.8,0);wallText(g,'互动体验',d-.12,.6,-w/2-.03,2.1,0,-Math.PI/2);
 }return g;
}
function buildZone(zone,index){
 const data=PLAN_ZONES[index],p=planPoint(...data.labelAt);
 label((index+1)+' '+data.label,new THREE.Vector3(p.x,3.5,p.z));
}
function buildCanopy(){
 const center=planPoint(...PLAN_CORE.pixel),g=new THREE.Group();g.name=PLAN_CORE.id;g.position.set(center.x,0,center.z);scene.add(g);
 cylinder(1.20,1.20,.15,mats.wood,g,0,.10,0);cylinder(1.10,1.20,.16,mats.paper,g,0,.25,0);
 const r=PLAN_CORE.canopyRadius,profile=[[.48,.30],[.48,2.65],[.56,2.98],[.76,3.28],[1.10,3.55],[1.52,3.75],[r,3.95]];
 lathe(profile.slice(0,2),mats.wood,g);lathe(profile.slice(1),mats.canopy,g);
 for(let i=0;i<64;i++){const a=i*Math.PI/32,points=profile.map(([radius,y])=>new THREE.Vector3(Math.sin(a)*(radius+.018),y,Math.cos(a)*(radius+.018)));mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points),22,.019,5,false),mats.gold,g);}
 for(const [radius,y] of [[1.15,.34],[r,3.97],[r-.24,3.995]]){const ring=mesh(new THREE.TorusGeometry(radius,.027,8,96),mats.lamp,g,0,y,0);ring.rotation.x=-Math.PI/2;}
 cylinder(r+.04,r+.04,.065,mats.wood,g,0,4.035,0);
 const spokes=[];for(let i=0;i<112;i++){const a=i*Math.PI*2/112;spokes.push(Math.sin(a)*.48,4.075,Math.cos(a)*.48,Math.sin(a)*(r-.03),4.075,Math.cos(a)*(r-.03));}
 const radial=new THREE.BufferGeometry();radial.setAttribute('position',new THREE.Float32BufferAttribute(spokes,3));
 g.add(new THREE.LineSegments(radial,new THREE.LineBasicMaterial({color:0xc6a16a})));
 const crown=mesh(new THREE.TorusGeometry(r-.07,.025,8,96),mats.gold,g,0,4.075,0);crown.rotation.x=Math.PI/2;
 plaque(g,'焕发非遗新活力',0,1.75,.49,.85);
 const lamp=new THREE.PointLight(0xffdda8,1.5,9,2);lamp.position.y=3.8;g.add(lamp);
}
function buildHall(){
 const nx=24,nz=16,tw=PLAN_W/nx,td=PLAN_D/nz;
 // Seven original stone shades share one geometry and seven instanced draws.
 const tileGeometry=new THREE.BoxGeometry(tw-.007,.04,td-.007),matrix=new THREE.Matrix4();
 for(let shade=0;shade<7;shade++){
  const cells=[];for(let i=0;i<nx;i++)for(let j=0;j<nz;j++)if((i*11+j*7)%7===shade)cells.push([i,j]);
  const m=material(new THREE.Color(0x676b6d).multiplyScalar(.96+shade*.006),{roughness:.18,metalness:.22});
  const tiles=new THREE.InstancedMesh(tileGeometry,m,cells.length);tiles.receiveShadow=true;tiles.userData.floorTile=true;
  cells.forEach(([i,j],k)=>{matrix.makeTranslation(-PLAN_W/2+(i+.5)*tw,0,-PLAN_D/2+(j+.5)*td);tiles.setMatrixAt(k,matrix);});scene.add(tiles);
 }
 zoneFloorGroup=new THREE.Group();zoneFloorGroup.name='按原图分区';scene.add(zoneFloorGroup);
 for(const z of PLAN_ZONES){
  planPolygon(zoneFloorGroup,z.polygon,material(z.color,{transparent:true,opacity:.66,depthWrite:false,side:THREE.DoubleSide}),.028);
  const points=z.polygon.map(p=>{const q=planPoint(...p);return new THREE.Vector3(q.x,.035,q.z);});
  zoneFloorGroup.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:0xe0d7c2,transparent:true,opacity:.7})));
 }
 zoneFloorGroup.visible=true;
 recommendedRouteGroup=new THREE.Group();recommendedRouteGroup.name='原图推荐动线';scene.add(recommendedRouteGroup);
 for(const pixels of activeMap.routes){
  const points=pixels.map(p=>{const v=planPoint(...p);return new THREE.Vector3(v.x,.055,v.z);});
  const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineDashedMaterial({color:0xffffff,dashSize:.25,gapSize:.14,transparent:true,opacity:.8}));line.computeLineDistances();recommendedRouteGroup.add(line);
 }
 for(const [pixel,heading] of activeMap.arrows){
  const p=planPoint(...pixel),arrow=new THREE.Mesh(new THREE.ConeGeometry(.13,.38,3),new THREE.MeshBasicMaterial({color:0xffffff}));
  arrow.position.set(p.x,.065,p.z);arrow.rotation.set(-Math.PI/2,0,-heading);recommendedRouteGroup.add(arrow);
 }
 recommendedRouteGroup.visible=false;

 for(const f of MAP_FIXTURES)if(f.kind!=='core')fixtureAt(f);
 buildCanopy();
 ceilingGroup=new THREE.Group();ceilingGroup.name='木格栅顶面';scene.add(ceilingGroup);
 box(PLAN_W,.06,PLAN_D,mats.darkWood,ceilingGroup,0,4.23,0);
 const count=104;for(let i=0;i<count;i++)box(.10,.12,PLAN_D-.1,mats.wood,ceilingGroup,-PLAN_W/2+(i+.5)*PLAN_W/count,4.13,0);
 for(const x of [-13,-7,0,7,13])for(const z of [-8,-2,5,9])cylinder(.065,.065,.03,mats.lamp,ceilingGroup,x,4.04,z);
 ceilingGroup.traverse(o=>{if(o.isMesh)o.castShadow=false;});ceilingGroup.visible=false;
 for(const [name,portal] of Object.entries(PLAN_PORTALS)){
  const p=planPoint(...portal.pixel);label(name==='entry'?'入口 / 待命点':'出口',new THREE.Vector3(p.x,.3,p.z),'zone-label door-label');
  for(const pixel of portal.jambs){const q=planPoint(...pixel);box(.13,2.9,.16,mats.wood,scene,q.x,1.45,q.z);}
  const arrow=mesh(new THREE.ConeGeometry(.14,.42,3),new THREE.MeshBasicMaterial({color:0xb44936}),scene,p.x,.065,p.z+portal.outward*.36);arrow.rotation.set(-Math.PI/2,0,(name==='entry'?0:Math.PI)+(activeMap.id==='adaptive'?Math.PI:0));
 }
 const waiting=planPoint(...PLAN_WAIT),ring=mesh(new THREE.RingGeometry(.47,.52,40),new THREE.MeshBasicMaterial({color:0xf5eee0,side:THREE.DoubleSide}),scene,waiting.x,.055,waiting.z);ring.rotation.x=-Math.PI/2;
 for(const room of PLAN_ROOMS)label(room.label,new THREE.Vector3(room.x,4.4,room.z));
 const core=planPoint(...PLAN_CORE.pixel);label('中央天幕柱',new THREE.Vector3(core.x,4.5,core.z));
}

function buildRobot(){
 const g=new THREE.Group();g.name='temi V3 · 非遗导览仿真原型';scene.add(g);
 Object.assign(g.userData,{platform:'temi V3',visualSource:'robotemi.com/product/temi-sales-contact/; supplied official product photograph',hasArms:false,hasHead:false,nominalDimensions:{width:.35,depth:.45,height:1},sdkConnected:false});
 const shell=material(0xe6e8e9,{roughness:.32,metalness:.08}),trim=material(0xb9bfc4,{roughness:.3,metalness:.35});
 const rubber=material(0x17191c,{roughness:.8}),glass=material(0x111419,{roughness:.18,metalness:.12});
 // Horizontal superellipse sections provide the rounded, tapered product silhouette.
 function hull(name,sections,mat,rows=24){
  const shape=new THREE.CatmullRomCurve3(sections.map(a=>new THREE.Vector3(a[1],a[2],a[3])));
  const heights=new THREE.CatmullRomCurve3(sections.map(a=>new THREE.Vector3(a[0],0,0)));
  const vertices=[],indices=[],segments=64;
  for(let j=0;j<=rows;j++){
   const t=j/rows,p=shape.getPoint(t),y=heights.getPoint(t).x;
   for(let i=0;i<segments;i++){const a=i/segments*Math.PI*2,c=Math.cos(a),s=Math.sin(a);vertices.push(p.x/2*Math.sign(c)*Math.sqrt(Math.abs(c)),y,p.z+p.y/2*Math.sign(s)*Math.sqrt(Math.abs(s)));}
  }
  for(let j=0;j<rows;j++)for(let i=0;i<segments;i++){const a=j*segments+i,b=j*segments+(i+1)%segments,c=b+segments,d=a+segments;indices.push(a,d,b,b,d,c);}
  for(const [j,top] of [[0,false],[rows,true]]){
   const p=shape.getPoint(j/rows),center=vertices.length/3;vertices.push(0,heights.getPoint(j/rows).x,p.z);
   for(let i=0;i<segments;i++){const a=j*segments+i,b=j*segments+(i+1)%segments;indices.push(...(top?[center,b,a]:[center,a,b]));}
  }
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.setIndex(indices);geo.computeVertexNormals();
  const o=mesh(geo,mat,g);o.name=name;return o;
 }
 function panel(w,h,d,r,mat,parent,x=0,y=0,z=0){
  const a=w/2,b=h/2,s=new THREE.Shape();
  s.moveTo(-a+r,-b);s.lineTo(a-r,-b);s.quadraticCurveTo(a,-b,a,-b+r);s.lineTo(a,b-r);s.quadraticCurveTo(a,b,a-r,b);
  s.lineTo(-a+r,b);s.quadraticCurveTo(-a,b,-a,b-r);s.lineTo(-a,-b+r);s.quadraticCurveTo(-a,-b,-a+r,-b);
  const bevel=Math.min(.002,d/4),geo=new THREE.ExtrudeGeometry(s,{depth:d,bevelEnabled:true,bevelSize:bevel,bevelThickness:bevel,bevelSegments:3,curveSegments:10});geo.translate(0,0,-d/2);
  return mesh(geo,mat,parent,x,y,z);
 }
 const base=hull('圆角白色驱动底盘',[[.018,.307,.401,0],[.035,.338,.435,0],[.080,.350,.450,0],[.12,.341,.426,-.002],[.15,.301,.367,-.012],[.168,.235,.267,-.025]],shell);
 for(const side of [-1,1]){
  const positions=[],indices=[],source=base.geometry.attributes.position;
  for(let row=3;row<=17;row++)for(let k=-10;k<=10;k++){const i=row*64+((side>0?k:32+k)+64)%64;positions.push(source.getX(i)*1.004,source.getY(i),source.getZ(i)*1.004);}
  for(let row=0;row<14;row++)for(let k=0;k<20;k++){const a=row*21+k,b=a+1,c=b+21,d=a+21;indices.push(a,d,b,b,d,c);}
  const coverGeo=new THREE.BufferGeometry();coverGeo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));coverGeo.setIndex(indices);coverGeo.computeVertexNormals();
  const cover=mesh(coverGeo,rubber,g);cover.name='贴合底盘曲面的黑色侧轮罩';
  const wheel=cylinder(.057,.057,.024,mats.tire,g,side*.148,.059,-.055);wheel.rotation.z=Math.PI/2;wheelModels.push(wheel);
 }
 const bumper=panel(.117,.028,.006,.012,glass,g,0,.058,.218);bumper.name='前部避障传感窗';
 for(const x of [-.122,.122])sphere(.004,glass,g,x,.073,.203);
 const mat=panel(.143,.161,.006,.023,rubber,g,0,.158,-.005);mat.rotation.x=-Math.PI/2;mat.name='底座防滑面';
 // The open fork leaves the lidar visible, rather than filling the lower pillar.
 const arch=new THREE.Shape();arch.moveTo(-.106,.156);arch.bezierCurveTo(-.094,.185,-.084,.285,-.080,.327);arch.quadraticCurveTo(0,.363,.080,.327);
 arch.bezierCurveTo(.084,.285,.094,.185,.106,.156);arch.lineTo(.052,.156);arch.lineTo(.043,.260);arch.bezierCurveTo(.039,.301,-.039,.301,-.043,.260);arch.lineTo(-.052,.156);arch.closePath();
 const archGeo=new THREE.ExtrudeGeometry(arch,{depth:.055,bevelEnabled:true,bevelSize:.004,bevelThickness:.004,bevelSegments:4,curveSegments:16});archGeo.translate(0,0,-.105);
 const fork=mesh(archGeo,shell,g);fork.name='下立柱雷达开口';
 cylinder(.031,.034,.037,rubber,g,0,.189,-.065);
 cylinder(.025,.026,.024,glass,g,0,.219,-.065);
 hull('弧面立柱',[[.304,.151,.057,-.074],[.37,.142,.061,-.072],[.46,.155,.064,-.063],[.55,.182,.069,-.048],[.65,.219,.080,-.022]],shell,28);
 hull('上部弧面机身',[[.608,.208,.080,-.024],[.635,.258,.103,-.013],[.69,.283,.122,-.001],[.75,.285,.119,-.012],[.787,.265,.104,-.027]],shell);
 const tray=panel(.296,.246,.012,.040,shell,g,0,.765,-.086);tray.rotation.x=-Math.PI/2;tray.name='后置托盘';
 const inset=panel(.274,.216,.003,.032,rubber,g,0,.774,-.086);inset.rotation.x=-Math.PI/2;
 hull('黑色屏幕支架',[[.697,.066,.012,.062],[.737,.077,.014,.062],[.779,.073,.018,.040],[.819,.058,.027,-.012],[.858,.054,.028,-.027]],rubber,20);
 const logoCanvas=document.createElement('canvas');logoCanvas.width=512;logoCanvas.height=128;
 const a=logoCanvas.getContext('2d');a.fillStyle='#9a9da1';a.font='56px Arial';a.textAlign='center';a.fillText('temi',256,88);
 const logoTexture=new THREE.CanvasTexture(logoCanvas);logoTexture.colorSpace=THREE.SRGBColorSpace;
 const logo=mesh(new THREE.PlaneGeometry(.047,.012),new THREE.MeshBasicMaterial({map:logoTexture,transparent:true,depthWrite:false}),g,0,.666,.058);logo.name='temi标识';
 const hinge=cylinder(.016,.016,.071,trim,g,0,.859,-.027);hinge.rotation.z=Math.PI/2;
 const tablet=new THREE.Group();tablet.name='13.3英寸横向交互屏';tablet.position.set(0,.900,-.027);tablet.rotation.x=-.14;g.add(tablet);
 panel(.320,.194,.016,.012,trim,tablet,0,0,-.002);
 panel(.322,.196,.010,.012,glass,tablet,0,0,.005);
 for(const x of [-.067,-.040,.040,.067])sphere(.0015,rubber,tablet,x,.088,.012);
 sphere(.004,glass,tablet,0,.088,.014);sphere(.002,trim,tablet,0,.088,.017);
 robotScreenCanvas=document.createElement('canvas');robotScreenCanvas.width=768;robotScreenCanvas.height=432;
 robotScreenTexture=new THREE.CanvasTexture(robotScreenCanvas);robotScreenTexture.colorSpace=THREE.SRGBColorSpace;
 robotScreen=mesh(new THREE.PlaneGeometry(.29376,.16524),new THREE.MeshBasicMaterial({map:robotScreenTexture}),tablet,0,-.003,.015);
 robotScreen.name='导览应用实时屏幕';
 robotStatusMaterial=new THREE.MeshBasicMaterial({color:0x60d7ce});sphere(.0025,robotStatusMaterial,tablet,.143,-.089,.014);
 robotScreenKey='';return g;
}

function updateRobotDisplay(){
 if(!robotScreenCanvas||!s)return;
 const halted=['manual','lost','estop','blocked','perception','crowd_wait'].includes(s.phase);
 const key=[s.phase,s.index,s.paused,$('mode').value].join('|');if(key===robotScreenKey)return;robotScreenKey=key;
 const ctx=robotScreenCanvas.getContext('2d'),w=768,h=432;
 const accent=halted?'#ef9d4b':s.paused?'#e8c363':'#61c9c7';
 ctx.fillStyle='#102230';ctx.fillRect(0,0,w,h);ctx.fillStyle=accent;ctx.fillRect(0,0,w,9);
 ctx.textAlign='left';ctx.font='26px "Microsoft YaHei"';ctx.fillStyle='#aac5d3';ctx.fillText('非遗智导',38,52);
 ctx.textAlign='center';ctx.font='500 45px "Microsoft YaHei"';ctx.fillStyle='#f6f7f2';
 const title=s.paused?'导览已暂停':s.phase==='crowd_wait'?'等待行人通过':halted?'等待工作人员':({arriving:'正在检测入场游客',forming:'请依次进入队列',stopping:'正在减速停车',clarifying:'请重试您的指令',regroup:'等待全员集合'})[s.phase]|| (s.phase==='idle'?'欢迎参观':['done','ended'].includes(s.phase)?'感谢您的参观':s.phase==='confirming'?'请确认游客人数':s.phase==='docking'?'到点停稳':s.phase==='moving'?'请跟随我':s.phase==='greeting'?'是否需要导览服务':zones[Math.min(s.index,4)].short+' · 导览讲解');
 ctx.fillText(title,w/2,151);ctx.font='24px "Microsoft YaHei"';ctx.fillStyle='#bacbd1';ctx.fillText(s.index<5?zones[s.index].name:'参观结束 · 前往出口',w/2,208);
 const labels=({idle:['入口待命','等待到访','人工协助'],arriving:['稳定检测','接待视场','人工协助'],greeting:['需要导览','暂不需要','人工协助'],confirming:['核实人数','游客类型','确认出发'],forming:['依次排队','等待全员','人工协助'],stopping:['正在停车','请稍候','急停'],clarifying:['重试指令','屏幕确认','人工协助'],regroup:['提醒归队','核实人数','人工协助']})[s.phase]||['重复讲解',s.paused?'继续导览':'暂停','人工协助'];
 labels.forEach((label,i)=>{ctx.fillStyle=['#31636d','#776641','#58547c'][i];ctx.fillRect(43+i*239,270,208,103);ctx.fillStyle='#f7f4ed';ctx.font='25px "Microsoft YaHei"';ctx.fillText(label,147+i*239,333);});
 ctx.font='18px "Microsoft YaHei"';ctx.fillStyle='#8fa8b4';ctx.fillText('屏幕与导览状态同步 · 仿真显示',w/2,416);
 robotScreenTexture.needsUpdate=true;robotStatusMaterial.color.set(accent);needsDraw=true;
}
