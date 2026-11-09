export function coursePositions(modules){
 const ids=modules.flatMap(m=>m.lessons.map((_,i)=>`${m.id}-${String(i+1).padStart(2,'0')}`));
 if(modules.length!==2||modules.some(m=>m.lessons.length!==8)||ids.length!==16||new Set(ids).size!==16||modules[0]?.id!=='nhn'||modules[1]?.id!=='aws')throw new Error('Expected NHN then AWS, eight lessons each');
 return ids.map((id,i)=>({id,position:i+1}));
}
export async function reorderCourse(tx,modules,courseId='gju-multicloud-2026'){
 const desired=coursePositions(modules);
 const existing=await tx.lesson.findMany({where:{courseId},select:{id:true,position:true}});
 if(existing.length!==desired.length||existing.some(l=>!desired.some(d=>d.id===l.id)))throw new Error('Course lessons differ from expected sixteen IDs; seed/inspect course first');
 if(existing.some(l=>desired.find(d=>d.id===l.id).position!==l.position)){
  const base=Math.max(0,...existing.map(l=>l.position))+desired.length+1;
  // Stage outside both old/new position ranges to preserve the unique(courseId,position) index.
  for(const [i,item] of desired.entries())await tx.lesson.update({where:{id:item.id},data:{position:base+i}});
  for(const item of desired)await tx.lesson.update({where:{id:item.id},data:{position:item.position}});
 }
 await tx.lab.updateMany({where:{courseId,id:'nhn-lab'},data:{position:1}});
 await tx.lab.updateMany({where:{courseId,id:'aws-lab'},data:{position:2}});
 await tx.course.update({where:{id:courseId},data:{title:'NHN Cloud·AWS 멀티클라우드 운영'}});
 return desired;
}
