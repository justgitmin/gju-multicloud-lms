export function frontierOf(ranges:unknown):number;
export function advance(input:{position:number,lastPosition:number,frontier:number,elapsed:number,duration:number,completed:boolean}):{frontier:number,resume:number,completed:boolean};
export function parseRange(header:string|null,size:number):{start:number,end:number}|null;
