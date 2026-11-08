import test from 'node:test';
import assert from 'node:assert/strict';
import {learningJourney} from '../lib/journey.mjs';
const course={lessons:[{id:'aws-01',title:'A',version:2},{id:'nhn-01',title:'B',version:1}],labs:[{id:'lab'}],quizzes:[{id:'quiz',version:2}]};
const enrollment={status:'APPROVED',progress:[],submissions:[],attempts:[]};
test('journey ignores stale versions and marks first unfinished lesson as next',()=>{
 const j=learningJourney(course,{...enrollment,progress:[{lessonId:'aws-01',version:1,completedAt:new Date()}],attempts:[{quizId:'quiz',version:1,score:100}]});
 assert.deepEqual(j.lessons.map(l=>l.state),['current','locked']);assert.equal(j.quizUnlocked,false);assert.equal(j.percent,0);assert.equal(j.counts.passedQuizzes,0);
});
test('pending reviews are not achievements; quiz unlock needs all videos',()=>{
 const j=learningJourney(course,{...enrollment,progress:course.lessons.map(l=>({lessonId:l.id,version:l.version,completedAt:new Date()})),submissions:[{labId:'lab',status:'PENDING'}]});
 assert.equal(j.quizUnlocked,true);assert.equal(j.pendingLabs,1);assert.equal(j.percent,50);assert.equal(j.complete,false);assert.equal(j.next,null);
});
test('current version passing attempt and approved labs complete journey',()=>{
 const j=learningJourney(course,{...enrollment,progress:course.lessons.map(l=>({lessonId:l.id,version:l.version,completedAt:new Date()})),submissions:[{labId:'lab',status:'APPROVED'}],attempts:[{quizId:'quiz',version:2,score:70},{quizId:'quiz',version:2,score:20}]});
 assert.equal(j.percent,100);assert.equal(j.complete,true);
});
test('empty content never reports completion or unlocks quizzes',()=>{
 const j=learningJourney({lessons:[],labs:[],quizzes:[]},enrollment);assert.equal(j.percent,0);assert.equal(j.complete,false);assert.equal(j.quizUnlocked,false);
});
