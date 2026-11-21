'use strict';
// The official coordinates are preserved as one immutable authoring configuration.
const officialLayout=(()=>{
const PLAN={rect:[185,15,865,445],scale:Math.sqrt(780/(680*430)),height:4.2,center:[525,230]};
function planPoint(x,y){return {x:(x-PLAN.center[0])*PLAN.scale,z:(y-PLAN.center[1])*PLAN.scale};}
function planBox(id,x0,y0,x1,y1,kind,extra={}){
 return {id,...planPoint((x0+x1)/2,(y0+y1)/2),w:(x1-x0)*PLAN.scale,d:(y1-y0)*PLAN.scale,kind,pixels:[x0,y0,x1,y1],...extra};
}
const PLAN_ZONES=[
 {id:1,label:'非遗概览区',color:0xc8ac82,polygon:[[201,100],[249,100],[263,135],[294,158],[291,319],[267,335],[249,355],[246,426],[201,426]],goal:[312,280],labelAt:[245,246],exhibit:[213,248]},
 {id:2,label:'传统工艺制作技艺区',color:0xb8c49b,polygon:[[257,25],[625,25],[625,126],[593,149],[326,149],[299,166],[275,131],[263,104]],goal:[443,157],labelAt:[436,78],exhibit:[444,106]},
 {id:3,label:'非遗代表作品展示区',color:0x8eafc2,polygon:[[341,387],[379,360],[629,360],[658,386],[658,429],[341,429]],goal:[462,378],labelAt:[493,391],exhibit:[474,410]},
 {id:4,label:'传承人与历史故事区',color:0xb6a5c2,polygon:[[621,140],[660,140],[705,182],[780,182],[780,358],[643,358],[606,328],[606,167]],goal:[651,298],labelAt:[704,220],exhibit:[701,252]},
 {id:5,label:'互动体验 / 文创延伸区',color:0xd4a5ac,polygon:[[629,22],[858,22],[858,365],[798,365],[798,182],[705,182],[660,136],[629,136]],goal:[714,127],labelAt:[744,143],exhibit:[722,80]},
];
const PLAN_ROOMS=[
 planBox('room-nw',193,23,249,91,'room',{label:'储藏间 / 设备间',door:'south'}),
 planBox('room-wc',747,373,804,435,'room',{label:'卫生间',door:'west'}),
 planBox('room-se',809,373,863,435,'room',{label:'储藏间 / 设备间',door:'west'}),
];
const PLAN_FIXTURES=[
 // Two long central cabinets, a small south-west cabinet and the lacquer island.
 planBox('case-west',343,170,377,262,'glass',{count:3}),
 planBox('case-east',553,167,589,303,'glass',{count:4}),
 planBox('case-small',344,298,382,349,'glass',{count:1}),
 planBox('case-lacquer',413,306,533,352,'glass',{count:3,orientation:'horizontal',lacquer:true}),
 planBox('craft-back',311,25,588,52,'wall-cabinet',{count:12}),
 planBox('craft-table-1',317,98,386,127,'workbench'),
 planBox('craft-table-2',411,98,477,127,'workbench'),
 planBox('craft-tool-case',525,95,567,131,'tools'),
 planBox('overview-relief',199,145,211,323,'relief'),
 planBox('overview-kiosk',260,251,283,295,'kiosk'),
 planBox('works-front',353,397,649,428,'wall-cabinet',{count:12}),
 planBox('story-portraits',609,177,623,326,'portrait-wall'),
 planBox('story-screen',665,247,746,286,'story-screen'),
 planBox('story-counter',668,328,779,351,'wall-cabinet',{count:5}),
 planBox('story-side',774,204,786,326,'wall-cabinet',{count:5}),
 planBox('interactive-screen',672,26,779,45,'interactive-screen'),
 planBox('interactive-table',674,65,780,104,'touch-table'),
 planBox('interactive-shelf',836,83,856,248,'souvenir-shelf'),
 planBox('shop-front',812,275,853,358,'shop'),
 planBox('north-pier',630,30,650,102,'sign-pier'),
];
for(const [cx,cy] of [[330,91],[351,91],[374,91],[330,134],[351,134],[374,134],[424,91],[445,91],[466,91],[424,134],[445,134],[466,134]])PLAN_FIXTURES.push(planBox('stool-'+cx+'-'+cy,cx-3,cy-3,cx+3,cy+3,'stool'));
const PLAN_PARTITIONS=[
 {id:'story-north-a',a:[621,140],b:[660,140],height:.9},
 {id:'story-north-b',a:[660,140],b:[705,182],height:.9},
 {id:'story-north-c',a:[705,182],b:[780,182],height:.9},
 // The south story boundary and blue works-zone jogs are floor transitions,
 // not invented raised barriers. They are represented by the zone polygons.
];
const PLAN_CORE={id:'central-canopy',pixel:[463,234],radius:1.20,canopyRadius:2.40};
const PLAN_PORTALS={entry:{pixel:[289,442],range:[266,311]},exit:{pixel:[700,442],range:[678,723]}};
const PLAN_WAIT=[280,383];
// Docking order follows the submitted five-zone service plan. Intermediate points
// keep the train on the two aisles and outside the cabinet footprints.
const PLAN_APPROACH=[
 [[312,378],[315,302]],
 [[315,169],[329,156],[515,156],[526,184],[443,184]],
 [[315,157],[315,285],[314,366],[400,378]],
 [[584,376],[626,352],[643,317]],
 [[631,348],[596,338],[594,151],[620,121],[650,119],[683,119],[695,150],[714,150]],
 [[799,127],[799,200],[799,330],[797,361],[735,362],[700,397],[700,424]],
];
const PLAN_W=(PLAN.rect[2]-PLAN.rect[0])*PLAN.scale,PLAN_D=(PLAN.rect[3]-PLAN.rect[1])*PLAN.scale;
function segmentFixture(id,a,b,height=1,thickness=.16){
 const p=planPoint(...a),q=planPoint(...b);
 return {id,x:(p.x+q.x)/2,z:(p.z+q.z)/2,w:Math.hypot(q.x-p.x,q.z-p.z),d:thickness,angle:Math.atan2(-(q.z-p.z),q.x-p.x),height,kind:'partition',pixelSegment:[a,b]};
}
const PLAN_WALLS=[
 segmentFixture('outer-west',[188,19],[188,441],4.2),segmentFixture('outer-east',[864,19],[864,441],4.2),segmentFixture('outer-north',[188,19],[864,19],4.2),
 ...[[188,266],[311,678],[723,864]].map(([a,b],i)=>segmentFixture('outer-front-'+i,[a,441],[b,441],1.05)),
];
const MAP_FIXTURES=[...PLAN_FIXTURES,...PLAN_ROOMS,...PLAN_PARTITIONS.map(p=>segmentFixture(p.id,p.a,p.b,p.height)),...PLAN_WALLS,{...planPoint(...PLAN_CORE.pixel),...PLAN_CORE,kind:'core'}];

return {PLAN,PLAN_ZONES,PLAN_ROOMS,PLAN_FIXTURES,PLAN_PARTITIONS,PLAN_CORE,PLAN_PORTALS,PLAN_WAIT,PLAN_APPROACH,PLAN_WALLS,PLAN_W,PLAN_D,MAP_FIXTURES};
})();

const MAP_CONFIGS={official:{id:'official',name:'官方赛题平面图',...officialLayout},adaptive:null};
const cloneMap=value=>JSON.parse(JSON.stringify(value));
// Independent plan: west workshop wing, central collection gallery, east story wing,
// and south-east interactive lounge. No transform of the official coordinates.
const adaptive=(()=>{
 const PLAN={rect:[185,15,785,515],center:[485,265],scale:Math.sqrt(780/(600*500)),height:4.2};
 const pixel=(x,z)=>[x/PLAN.scale+PLAN.center[0],z/PLAN.scale+PLAN.center[1]];
 const box=(id,x,z,w,d,kind,extra={})=>({id,x,z,w,d,kind,pixels:[...pixel(x-w/2,z-d/2),...pixel(x+w/2,z+d/2)],...extra});
 const zone=(id,polygon,goal,exhibit,labelAt)=>({id,label:officialLayout.PLAN_ZONES[id-1].label,color:officialLayout.PLAN_ZONES[id-1].color,polygon:polygon.map(p=>pixel(...p)),goal:pixel(...goal),exhibit:pixel(...exhibit),labelAt:pixel(...labelAt)});
 const PLAN_ZONES=[
  zone(1,[[-14.7,2.6],[-5,2.6],[-5,11.8],[-14.7,11.8]],[-10,5.4],[-14,5.4],[-11,8.6]),
  zone(2,[[-14.7,-11.9],[-4,-11.9],[-4,1],[-14.7,1]],[-9,-2],[-9,-6.5],[-9,-8.4]),
  zone(3,[[-2.6,-11],[5,-11],[5,3.5],[-2.6,3.5]],[1,-3],[1,-7],[1,-9]),
  zone(4,[[6.3,-11.9],[14.7,-11.9],[14.7,1],[6.3,1]],[9,-3],[9,-6.5],[9,-9.4]),
  zone(5,[[4,3.5],[14.7,3.5],[14.7,11.9],[4,11.9]],[9,6],[9,9],[9,10.8]),
 ];
 const PLAN_FIXTURES=[
  box('overview-relief',-14.3,5.5,.55,6.5,'relief'),box('overview-kiosk',-12.1,5.5,.85,1.6,'kiosk'),
  box('craft-back',-14.3,-5.5,7.0,.75,'wall-cabinet',{count:10,angle:Math.PI/2}),
  box('craft-table-1',-11.5,-6.4,2.7,1.25,'workbench',{angle:Math.PI/2}),
  box('craft-table-2',-7.1,-6.4,2.7,1.25,'workbench',{angle:Math.PI/2}),
  box('craft-tool-case',-6.1,-10.0,1.6,1.2,'tools'),
  box('case-west',-.8,-7,3.1,1.35,'glass',{count:3,orientation:'horizontal'}),
  box('case-east',3,-7,2.0,1.35,'glass',{count:2,orientation:'horizontal'}),
  box('case-lacquer',.9,.3,4.5,1.5,'glass',{count:3,orientation:'horizontal',lacquer:true}),
  box('case-small',-.8,3.1,1.3,1.4,'glass',{count:1}),
  box('works-front',1,-11.5,6.6,.8,'wall-cabinet',{count:8,angle:Math.PI}),
  box('story-portraits',9.3,-11.7,.6,5.0,'portrait-wall',{angle:Math.PI/2}),
  box('story-screen',9,-6.5,3.8,1.55,'story-screen'),
  box('story-counter',14.0,-5.0,5.0,.85,'wall-cabinet',{count:5,angle:-Math.PI/2}),
  box('story-side',9.1,-.1,5.7,.8,'wall-cabinet',{count:6,angle:Math.PI}),
  box('interactive-screen',8,11.5,4.8,.6,'interactive-screen',{angle:Math.PI}),
  box('interactive-table',9,9,4.0,1.6,'touch-table',{angle:Math.PI}),
  box('interactive-shelf',14.1,6.4,.8,5.5,'souvenir-shelf'),
  box('shop-front',5.1,8.8,.8,3.8,'shop',{angle:Math.PI}),
  box('north-pier',6.0,4.0,.55,1.0,'sign-pier'),
 ];
 for(const x of [-12.55,-10.45,-8.15,-6.05])for(const z of [-7.1,-5.7])PLAN_FIXTURES.push(box('stool-'+x+'-'+z,x,z,.31,.31,'stool'));
 const PLAN_ROOMS=[box('room-nw',-12.8,-10.5,3.1,2.6,'room',{label:'设备间',door:'south'}),box('room-wc',13.2,-10.5,2.5,2.6,'room',{label:'卫生间',door:'west'}),box('room-se',.2,10.7,3,2.4,'room',{label:'储藏间',door:'west'})];
 const PLAN_PARTITIONS=[
  {id:'workshop-spine',a:pixel(-3.6,-11.8),b:pixel(-3.6,-4.3),height:2.4},
  {id:'lobby-spine',a:pixel(-4.3,4.4),b:pixel(-4.3,11.9),height:1.25},
  {id:'story-spine-back',a:pixel(5.8,-11.8),b:pixel(5.8,-5),height:2.4},
  {id:'story-spine-front',a:pixel(5.8,-.5),b:pixel(5.8,2.2),height:1.25},
 ];
 const W=600*PLAN.scale,D=500*PLAN.scale,front=D/2-.12;
 const wall=(id,a,b,height=4.2)=>({id,x:(a[0]+b[0])/2,z:(a[1]+b[1])/2,w:Math.hypot(b[0]-a[0],b[1]-a[1]),d:.16,angle:Math.atan2(-(b[1]-a[1]),b[0]-a[0]),kind:'partition',height,pixelSegment:[pixel(...a),pixel(...b)]});
 const PLAN_WALLS=[wall('outer-west',[-W/2+.1,-D/2+.1],[-W/2+.1,front]),wall('outer-east',[W/2-.1,-D/2+.1],[W/2-.1,front]),wall('outer-north',[-W/2+.1,-D/2+.1],[W/2-.1,-D/2+.1]),...[[ -W/2+.1,-12.2],[-9.8,10.2],[12.6,W/2-.1]].map(([a,b],i)=>wall('outer-front-'+i,[a,front],[b,front],1.05))];
 const portal=(x)=>({pixel:pixel(x,front+.04),range:[pixel(x-1.2,0)[0],pixel(x+1.2,0)[0]],outward:1});
 const PLAN_PORTALS={entry:portal(-11),exit:portal(11.4)};
 const PLAN_APPROACH=[[],[[-10,1],[-9,-2]],[[-6,-2],[-2,-3]],[[5,-3]],[[12.5,-3],[12.5,3],[9,4.5]],[[11.4,9],[11.4,11.4]]].map(a=>a.map(p=>pixel(...p)));
 return {id:'adaptive',name:'独立布局 · 分馆式回廊',PLAN,PLAN_ZONES,PLAN_FIXTURES,PLAN_ROOMS,PLAN_PARTITIONS,PLAN_WALLS,PLAN_CORE:{id:'central-canopy',pixel:pixel(-4,2),radius:1.2,canopyRadius:2.4},PLAN_PORTALS,PLAN_WAIT:pixel(-11,9.2),PLAN_APPROACH,PLAN_W:W,PLAN_D:D,
 routes:[[[-11,front],[-11,9.2],[-10,5.4],[-10,1],[-9,-2],[-2,-3],[1,-3],[5,-3],[9,-3],[11,-3],[11,3],[9,6],[11.4,9],[11.4,front]]].map(a=>a.map(p=>pixel(...p))),
 arrows:[[[ -10,2],0],[[ -3,-3],Math.PI/2],[[11,1],Math.PI],[[11.4,11],Math.PI]].map(([p,a])=>[pixel(...p),a]),
 hall:{position:[-12.8,4.0,11.3],target:[0,1,-2]},crowdPixels:[pixel(-10,1),pixel(5,-3)],
 freeRoamStops:[
  [[-12.8,7.8],[-12.5,10.8],[-12.5,2.0]],
  [[-9.3,-5.8],[-9.3,-8.5],[-5.3,-6.0]],
  [[-1.2,-4.6],[3.3,-4.6],[.5,1.8]],
  [[7.2,-4.5],[10.6,-4.4],[8.7,-9.8]],
  [[7.4,7.3],[10.8,7.2],[12.5,5.3]],
 ].map(a=>a.map(p=>pixel(...p)))};
})();
MAP_CONFIGS.adaptive=adaptive;
MAP_CONFIGS.official.routes=[[[289,442],[280,383],[315,337],[315,188],[329,156],[595,156],[626,124],[651,110]],[[714,127],[799,127],[799,200],[799,330],[797,361],[735,362],[700,397],[700,442]]];
MAP_CONFIGS.official.arrows=[[[315,220],0],[[455,150],Math.PI/2],[[646,112],Math.PI/2],[[799,260],Math.PI],[[753,362],-Math.PI/2],[[700,413],Math.PI]];
MAP_CONFIGS.official.hall={position:[-12.3,2.35,9.3],target:[-1,1.5,-2]};
MAP_CONFIGS.official.crowdPixels=[[315,188],[598,320]];
MAP_CONFIGS.official.freeRoamStops=[[[238,357],[238,401],[259,331]],[[345,73],[435,73],[535,74]],[[350,374],[520,382],[620,382]],[[704,226],[742,304],[655,220]],[[697,116],[760,125],[814,225]]];
let activeMap,PLAN,PLAN_ZONES,PLAN_ROOMS,PLAN_FIXTURES,PLAN_PARTITIONS,PLAN_CORE,PLAN_PORTALS,PLAN_WAIT,PLAN_APPROACH,PLAN_WALLS,PLAN_W,PLAN_D,MAP_FIXTURES;
function planPoint(x,y){return {x:(x-PLAN.center[0])*PLAN.scale,z:(y-PLAN.center[1])*PLAN.scale};}
function fixtureLocal(p,b){const dx=p.x-b.x,dz=p.z-b.z,c=Math.cos(b.angle||0),sn=Math.sin(b.angle||0);return {x:c*dx-sn*dz,z:sn*dx+c*dz};}
function fixtureDistance(p,b){if(b.radius!==undefined)return Math.max(0,Math.hypot(p.x-b.x,p.z-b.z)-b.radius);const q=fixtureLocal(p,b);return Math.hypot(Math.max(0,Math.abs(q.x)-b.w/2),Math.max(0,Math.abs(q.z)-b.d/2));}
function segmentFixture(id,a,b,height=1,thickness=.16){const p=planPoint(...a),q=planPoint(...b);return {id,x:(p.x+q.x)/2,z:(p.z+q.z)/2,w:Math.hypot(q.x-p.x,q.z-p.z),d:thickness,angle:Math.atan2(-(q.z-p.z),q.x-p.x),height,kind:'partition',pixelSegment:[a,b]};}
function selectMapConfig(id){
 activeMap=MAP_CONFIGS[id];if(!activeMap)throw Error('Unknown map '+id);
 ({PLAN,PLAN_ZONES,PLAN_ROOMS,PLAN_FIXTURES,PLAN_PARTITIONS,PLAN_CORE,PLAN_PORTALS,PLAN_WAIT,PLAN_APPROACH,PLAN_WALLS,PLAN_W,PLAN_D}=activeMap);
 MAP_FIXTURES=[...PLAN_FIXTURES,...PLAN_ROOMS,...PLAN_PARTITIONS.map(p=>segmentFixture(p.id,p.a,p.b,p.height)),...PLAN_WALLS,{...planPoint(...PLAN_CORE.pixel),...PLAN_CORE,kind:'core'}];
 activeMap.MAP_FIXTURES=MAP_FIXTURES;
 activeMap.exhibitIds=['overview-relief','craft-table-2','case-lacquer','story-screen','interactive-table'];
 activeMap.glassRegions=PLAN_FIXTURES.filter(f=>f.kind==='glass').map(f=>({...f,influence:.85}));
 activeMap.crowdRegions=activeMap.crowdPixels.map(p=>planPoint(...p));
 for(const p of Object.values(PLAN_PORTALS)){p.outward=p.outward||1;p.jambs=p.range.map(x=>[x,p.pixel[1]-p.outward]);}
}
selectMapConfig('adaptive');
selectMapConfig('official');
