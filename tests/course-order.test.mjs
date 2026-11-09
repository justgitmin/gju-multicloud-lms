import test from 'node:test';
import assert from 'node:assert/strict';
import {modules} from '../lib/curriculum.ts';
import {coursePositions,reorderCourse} from '../lib/course-order.mjs';
import {canOpenLesson} from '../lib/lesson-prerequisite.mjs';
test('old AWS-first order swaps safely without touching media or versions; repeat is idempotent',async()=>{
 const rows=coursePositions(modules).map(l=>({...l,position:l.position<=8?l.position+8:l.position-8,videoKey:l.id+'.mp4',version:3}));
 let writes=0;const tx={lesson:{findMany:async()=>rows,update:async({where,data})=>{assert.deepEqual(Object.keys(data),['position']);assert(!rows.some(r=>r.id!==where.id&&r.position===data.position));Object.assign(rows.find(r=>r.id===where.id),data);writes++;}},lab:{updateMany:async()=>{}},course:{update:async()=>{}}};
 await reorderCourse(tx,modules);assert.equal(writes,32);assert.deepEqual(rows.map(({id,position})=>({id,position})),coursePositions(modules));assert(rows.every(r=>r.version===3&&r.videoKey===r.id+'.mp4'));await reorderCourse(tx,modules);assert.equal(writes,32);
});
test('unknown or missing lesson IDs prevent writes',async()=>{await assert.rejects(()=>reorderCourse({lesson:{findMany:async()=>[{id:'unknown',position:1}]}},modules),/differ/);assert.throws(()=>coursePositions([{id:'nhn',lessons:[]},{id:'aws',lessons:Array(16)}]),/eight/);});
test('reordering preserves completed AWS replay but locks unfinished lessons',()=>{const nhn={id:'nhn-01',version:1},aws={id:'aws-01',version:2};const p=[{lessonId:aws.id,version:2,completedAt:new Date()}];assert(canOpenLesson(aws,[nhn],p));assert(!canOpenLesson(aws,[nhn],[{...p[0],version:1}]));assert(!canOpenLesson(aws,[nhn],[]));assert(canOpenLesson(aws,[nhn],[{lessonId:nhn.id,version:1,completedAt:new Date()}]));});
