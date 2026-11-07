export function frontierOf(ranges){return Array.isArray(ranges)&&Array.isArray(ranges[0])&&ranges[0][0]===0&&Number.isFinite(ranges[0][1])?Math.max(0,ranges[0][1]):0;}
export function advance({position,lastPosition,frontier,elapsed,duration,completed}){
 if(!Number.isFinite(position)||!Number.isFinite(duration)||duration<=0||position<0||position>duration+.1)throw new Error('INVALID_POSITION');
 if(!completed){
  const allowance=Math.min(Math.max(elapsed,0),15)*1.1+.25;
  // Seeking inside the already watched prefix is permitted; unseen time must follow real elapsed time.
  if(position>frontier+.05&&(lastPosition>frontier+.1||position-lastPosition>allowance))throw new Error('SEEK_BLOCKED');
 }
 const next=completed?duration:Math.min(duration,Math.max(frontier,position));
 return {frontier:next,resume:Math.min(position,duration),completed:completed||next>=duration*.95};
}
export function parseRange(header,size){
 if(!header)return null;
 const match=/^bytes=(\d*)-(\d*)$/.exec(header);
 if(!match||(!match[1]&&!match[2]))throw new Error('INVALID_RANGE');
 let start=match[1]?Number(match[1]):Math.max(0,size-Number(match[2]));
 let end=match[1]?(match[2]?Number(match[2]):size-1):size-1;
 if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<0||start>=size||end<start)throw new Error('INVALID_RANGE');
 end=Math.min(end,size-1);return {start,end};
}
