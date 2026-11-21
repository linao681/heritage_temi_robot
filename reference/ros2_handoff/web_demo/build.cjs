const fs=require('node:fs');
const path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,name),'utf8');
let html=read('index.html');
html=html.replace('<link rel="stylesheet" href="style.css">',()=>'<style>'+read('style.css')+'</style>');
for(const file of ['vendor/three.min.js','config.js','motion.js','reference-assets.js','layout.js','content.js','people.js','app.js','story-data.js','story-panels.js','scene.js','details.js','performance.js','navigation.js','simulation.js','sensing.js','reception.js','crew.js','traffic.js','cameras.js','workflow.js','metrics.js','upgrade-ui.js','exploration.js','boot.js']){
 const marker='<script src="'+file+'"></script>';
 if(!html.includes(marker))throw Error('Missing '+file);
 html=html.replace(marker,()=>'<script>'+read(file).replace(/<\/script/gi,'<\\/script')+'</script>');
}
if(/<(script|link)[^>]+(?:src|href)=/.test(html))throw Error('External assets remain');
fs.writeFileSync(path.join(__dirname,'../具身智能非遗展厅导览仿真_优化验证版.html'),html);
fs.writeFileSync(path.join(__dirname,'../具身智能非遗展厅导览仿真_自主参观服务闭环版.html'),html);
console.log('Offline single-file build passed.');
