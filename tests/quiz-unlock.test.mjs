import test from 'node:test';
import assert from 'node:assert/strict';
import {canTakeQuiz} from '../lib/assessment.mjs';
test('quiz requires every course video to be completed',()=>{
 assert.equal(canTakeQuiz({lessons:16,completedLessons:0}),false);
 assert.equal(canTakeQuiz({lessons:16,completedLessons:15}),false);
 assert.equal(canTakeQuiz({lessons:16,completedLessons:16}),true);
 assert.equal(canTakeQuiz({lessons:0,completedLessons:0}),false);
});
