BEGIN;
UPDATE "Enrollment" e
SET status='REJECTED'
FROM "User" u, "Course" c
WHERE e."userId"=u.id AND e."courseId"=c.id
 AND e.status='PENDING'
 AND ((u.email='goo9406@naver.com' AND u.name='구종민' AND u."studentNumber"='20201190')
 OR (u.email='t01064898629@gmail.com' AND u.name='고상국' AND u."studentNumber"='20261134')
 OR (u.email='kimsungwon3813@naver.com' AND u.name='김성원' AND u."studentNumber"='20201338'))
 AND c.id='gju-multicloud-2026'
 AND EXISTS (SELECT 1 FROM "Enrollment" dt WHERE dt."userId"=u.id AND dt."courseId"='gju-digital-twin-2026' AND dt.status='APPROVED')
RETURNING u.name,u."studentNumber",c.title,e.status;
COMMIT;
