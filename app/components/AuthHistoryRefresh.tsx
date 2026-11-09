'use client';
import {useEffect} from 'react';
import {useRouter} from 'next/navigation';
// A browser history snapshot can predate the session cookie change.
export default function AuthHistoryRefresh(){
 const router=useRouter();
 useEffect(()=>{const restore=(event:PageTransitionEvent)=>{if(event.persisted)router.refresh();};window.addEventListener('pageshow',restore);return()=>window.removeEventListener('pageshow',restore);},[router]);
 return null;
}
