'use strict';
// Static geometry only. Keep translucent cases, original fixture roots and visibility groups.
function batchStaticScene(){
 scene.updateMatrixWorld(true);
 const groups=new Map(),originalGeometries=new Set();let sourceMeshes=0;
 scene.traverse(object=>{
  if(!object.isMesh||object.isInstancedMesh||object.name||Array.isArray(object.material)||object.material.transparent||object.material.isShaderMaterial||!object.geometry.attributes.normal||!object.geometry.attributes.uv)return;
  let owner=scene;
  for(let p=object.parent;p&&p!==scene;p=p.parent)if(p===ceilingGroup||p===zoneFloorGroup||p===recommendedRouteGroup)owner=p;
  const position=new THREE.Vector3().setFromMatrixPosition(object.matrixWorld);
  const key=[owner.uuid,object.material.id,object.castShadow,object.receiveShadow,Math.floor(position.x/10),Math.floor(position.z/10)].join('/');
  if(!groups.has(key))groups.set(key,{owner,material:object.material,castShadow:object.castShadow,receiveShadow:object.receiveShadow,objects:[]});
  groups.get(key).objects.push(object);
 });
 let batches=0;
 for(const group of groups.values()){
  if(group.objects.length<2)continue;
  const geometry=new THREE.BufferGeometry(),pieces=[];let vertices=0;
  const inverse=new THREE.Matrix4().copy(group.owner.matrixWorld).invert();
  for(const object of group.objects){
   const piece=object.geometry.index?object.geometry.toNonIndexed():object.geometry.clone();piece.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inverse,object.matrixWorld));pieces.push(piece);vertices+=piece.attributes.position.count;
  }
  for(const [name,size] of [['position',3],['normal',3],['uv',2]]){
   const values=new Float32Array(vertices*size);let offset=0;
   for(const piece of pieces){values.set(piece.attributes[name].array,offset);offset+=piece.attributes[name].array.length;}
   geometry.setAttribute(name,new THREE.BufferAttribute(values,size));
  }
  geometry.computeBoundingSphere();const batch=new THREE.Mesh(geometry,group.material);batch.castShadow=group.castShadow;batch.receiveShadow=group.receiveShadow;group.owner.add(batch);
  group.objects.forEach(o=>{originalGeometries.add(o.geometry);o.removeFromParent();});pieces.forEach(g=>g.dispose());sourceMeshes+=group.objects.length;batches++;
 }
 // Geometry can be shared. Dispose only after all remaining scene users have been checked.
 scene.traverse(o=>{if(o.geometry)originalGeometries.delete(o.geometry);});originalGeometries.forEach(g=>g.dispose());
 scene.userData.batchStats={sourceMeshes,batches,savedDraws:sourceMeshes-batches};
}
