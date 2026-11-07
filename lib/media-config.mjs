export function validMediaKey(key,backend){
 if(typeof key!=='string')return false;
 return backend==='s3'?/^courses\/2026-multicloud\/(aws|nhn)\/0[1-8]\/v[1-9][0-9]*\/(aws|nhn)-0[1-8]\.mp4$/.test(key):/^[a-zA-Z0-9_-]+\.mp4$/.test(key);
}
export function captionKey(key,backend){return backend==='s3'?key.replace(/[^/]+\.mp4$/,'captions-ko.vtt'):key.replace(/\.mp4$/,'.vtt');}
