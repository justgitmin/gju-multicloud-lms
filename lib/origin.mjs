export function sameOrigin(origin,host,configured){
 try{
  if(!origin||!host)return false;
  const parsed=new URL(origin);
  if(!['http:','https:'].includes(parsed.protocol)||parsed.origin!==origin)return false;
  if(configured)return parsed.origin===new URL(configured).origin;
  return parsed.host.toLowerCase()===host.toLowerCase();
 }catch{return false;}
}
