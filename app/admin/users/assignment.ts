'use server';
import {redirect} from 'next/navigation';
import {revalidatePath} from 'next/cache';
import {requireAdmin} from '../../../lib/auth';
import {db} from '../../../lib/db';

export async function assignCourses(form:FormData){
 await requireAdmin();
 const userId=String(form.get('userId')??'');
 const courseIds=[...new Set(form.getAll('courseId').map(String))];
 const query=new URLSearchParams({q:String(form.get('q')??'').slice(0,100)});
 const [student,courses]=await Promise.all([
  db.user.findFirst({where:{id:userId,role:'STUDENT'},select:{id:true}}),
  db.course.findMany({where:{id:{in:courseIds},published:true},select:{id:true}})
 ]);
 if(!student||!courseIds.length||courses.length!==courseIds.length){
  query.set('assignment','invalid');
  redirect('/admin/users?'+query);
 }
 await db.$transaction(courses.map(({id:courseId})=>db.enrollment.upsert({
  where:{userId_courseId:{userId,courseId}},
  create:{userId,courseId,status:'APPROVED'},
  update:{status:'APPROVED'}
 })));
 revalidatePath('/admin/users');
 revalidatePath('/admin');
 revalidatePath('/classroom');
 query.set('assignment','saved');
 redirect('/admin/users?'+query);
}
