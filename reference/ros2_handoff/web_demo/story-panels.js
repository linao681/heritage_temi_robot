'use strict';
// Photos stay local/offline. Each photograph remains paired with its documented person/caption.
const storyImageCache=new Map();
function storyPhoto(id,paint){
 let entry=storyImageCache.get(id);
 if(!entry){
  const image=document.createElement('img');entry={image,ready:false,failed:false,callbacks:[]};storyImageCache.set(id,entry);
  image.onload=()=>{entry.ready=true;for(const fn of entry.callbacks)fn();entry.callbacks=[];};
  image.onerror=()=>{entry.failed=true;entry.callbacks=[];};image.src=STORY_PHOTOS[id];
 }
 if(entry.ready)paint();else entry.callbacks.push(paint);
 return entry;
}
function storyPhotosReady(){return storyImageCache.size>0&&[...storyImageCache.values()].every(e=>e.ready&&!e.failed);}
function storyPanel(kind,index=0){
 const key='documentary-'+kind+'-'+index;if(panelCache.has(key))return panelCache.get(key);
 const card=kind==='story',c=document.createElement('canvas');c.width=card?480:1536;c.height=card?360:864;
 const a=c.getContext('2d'),texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;
 const mat=new THREE.MeshBasicMaterial({map:texture,toneMapped:false});panelCache.set(key,mat);
 let alive=true;mat.addEventListener('dispose',()=>alive=false);
 const cards=[
  {photo:'hefuli',person:0,label:'何福礼 · 东阳竹编',caption:'1958年入厂学艺，参与倦勤斋修缮'},
  {photo:'yaojianping',person:1,label:'姚建萍 · 苏绣',caption:'师承徐志慧，培养年轻学习者'},
  {photo:'gaofenglian',person:2,label:'高凤莲 · 延川剪纸',caption:'十岁学剪花样，作品表现生活'},
  {photo:'hefuli',person:0,label:'何福礼 · 竹编实作',caption:'主持《九龙壁》编制，钻研竹编'},
  {photo:'yaojianping-teaching',person:1,label:'姚建萍与姚兰',caption:'姚建萍与女儿姚兰共同创作苏绣'},
  {photo:'gaofenglian-family',person:2,label:'高凤莲一家 · 剪纸',caption:'高凤莲与女儿、外孙女共同剪纸'}
 ];
 const item=cards[index%cards.length];
 const text=(value,x,y,size,color='#483a2b')=>{a.font='500 '+size+'px "Microsoft YaHei",sans-serif';a.textAlign='left';a.fillStyle=color;a.fillText(value,x,y);};
 const photo=(id,x,y,w,h)=>{
  a.fillStyle='#d4c7b3';a.fillRect(x,y,w,h);const entry=storyImageCache.get(id);if(!entry?.ready)return;
  const image=entry.image,ratio=Math.max(w/image.naturalWidth,h/image.naturalHeight),sw=w/ratio,sh=h/ratio;
  const sx=(image.naturalWidth-sw)/2,sy=(image.naturalHeight-sh)*.35;
  a.save();a.beginPath();a.rect(x,y,w,h);a.clip();a.filter=card?'blur(0.55px) saturate(0.76) sepia(0.13)':'blur(0.8px) saturate(0.80) sepia(0.10)';
  a.drawImage(image,sx,sy,sw,sh,x,y,w,h);a.filter='none';a.fillStyle='rgba(224,203,165,0.09)';a.fillRect(x,y,w,h);a.restore();
 };
 const wrap=(value,x,y,width,size=31,line=48)=>{
  a.font='400 '+size+'px "Microsoft YaHei",sans-serif';a.fillStyle='#6c5b45';let row='';
  for(const char of value){if(a.measureText(row+char).width>width&&row){a.fillText(row,x,y);row=char;y+=line;}else row+=char;}if(row)a.fillText(row,x,y);
 };
 const paint=()=>{
  if(!alive)return;a.filter='none';a.fillStyle='#eee4d2';a.fillRect(0,0,c.width,c.height);
  if(card){
   photo(item.photo,16,16,448,244);text(item.label,22,301,29);text(item.caption,22,337,20,'#8d7453');
  }else{
   a.fillStyle='#493c2e';a.fillRect(0,0,1536,112);text('传承人与历史故事',52,78,48,'#f4e8d2');
   photo('yaojianping',44,150,836,625);
   text('姚建萍 · 苏绣',936,218,46);text('从学艺到传艺',936,292,35,'#a47b48');
   wrap(STORY_PROFILES[1].story,936,360,536,31,49);
   a.fillStyle='#b89b6e';a.fillRect(936,520,536,2);
   photo('hefuli',936,556,250,166);photo('gaofenglian-family',1210,556,270,166);
   text('何福礼 · 竹编',936,762,27);text('高凤莲一家 · 剪纸',1210,762,25);
   text('公开资料选编 · 中国非遗网 / 国家图书馆 / 央广网',44,830,25,'#8b7658');
  }
  texture.needsUpdate=true;needsDraw=true;
 };
 paint();const ids=card?[item.photo]:['yaojianping','hefuli','gaofenglian-family'];ids.forEach(id=>storyPhoto(id,paint));return mat;
}
