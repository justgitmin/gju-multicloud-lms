"use client";
import {useActionState} from 'react';
import {reviewLab} from '../../assessment-actions';
type Result={error?:string;status?:string;updatedAt?:string};
export default function ReviewForm(props:{submissionId:string;updatedAt:string;status:string;feedback:string}){
 const [result,action,pending]=useActionState<Result,FormData>(async (_previous,form)=>{
  return await reviewLab(form);
 },{});
 // A newer server version (including a student resubmission) takes precedence.
 const current=result.updatedAt&&Date.parse(result.updatedAt)>=Date.parse(props.updatedAt)?result.status:props.status;
 const version=result.updatedAt&&Date.parse(result.updatedAt)>=Date.parse(props.updatedAt)?result.updatedAt:props.updatedAt;
 return <form action={action} className="assessmentform" aria-busy={pending}>
  <input type="hidden" name="submissionId" value={props.submissionId}/>
  <input type="hidden" name="updatedAt" value={version}/>
  <label>피드백<textarea name="feedback" maxLength={3000} rows={3} defaultValue={props.feedback}/></label>
  <div className="review">
   <button type="submit" name="status" value="APPROVED" disabled={pending||current==='APPROVED'} style={current==='APPROVED'?{background:'#166534',color:'white',opacity:1}:undefined}>{current==='APPROVED'?'✓ 통과 완료':pending?'저장 중…':'통과'}</button>
   <button type="submit" name="status" value="REVISION" disabled={pending}>{current==='REVISION'?'✓ 보완 요청됨':'보완 요청'}</button>
  </div>
  {pending?<p role="status">검토 결과를 저장하고 있습니다.</p>:result.error?<p role="alert" className="error">{result.error}</p>:result.status&&<p role="status">검토 결과가 저장되었습니다: {result.status==='APPROVED'?'통과':'보완 요청'}</p>}
 </form>;
}
