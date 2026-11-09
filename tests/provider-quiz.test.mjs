import test from 'node:test';
import assert from 'node:assert/strict';
import {quizProgress} from '../lib/quiz-progress.mjs';
const lessons=[{id:'aws-01',version:2},{id:'nhn-01',version:1}];
const progress=[{lessonId:'aws-01',version:2,completedAt:new Date()}];
test('AWS unlocks before NHN; NHN stays locked',()=>{assert.equal(quizProgress('aws-quiz',lessons,progress).unlocked,true);assert.equal(quizProgress('nhn-quiz',lessons,progress).unlocked,false);});
test('stale versions, incomplete and empty provider never unlock',()=>{assert.equal(quizProgress('aws-quiz',lessons,[{...progress[0],version:1}]).unlocked,false);assert.equal(quizProgress('aws-quiz',lessons,[{...progress[0],completedAt:null}]).unlocked,false);assert.equal(quizProgress('nhn-quiz',[lessons[0]],progress).unlocked,false);});
test('unknown quizzes retain whole-course prerequisite',()=>{assert.equal(quizProgress('custom',lessons,progress).unlocked,false);});
