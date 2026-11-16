"use client";
import {useFormStatus} from 'react-dom';
export default function ReviewButtons(){
 const {pending}=useFormStatus();
 return <div className="review" aria-busy={pending}>
  <button type="submit" name="status" value="APPROVED" disabled={pending}>{pending?'저장 중…':'통과'}</button>
  <button type="submit" name="status" value="REVISION" disabled={pending}>보완 요청</button>
  {pending&&<span role="status">검토 결과를 저장하고 있습니다.</span>}
 </div>;
}
