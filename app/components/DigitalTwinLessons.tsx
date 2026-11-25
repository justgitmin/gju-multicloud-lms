const lessons=[
 ['01','공정 조건과 결과 비교','3분 42초','가공 시간이 줄었는데 완료 수량이 그대로라면 어느 단계의 어떤 지표를 확인할까요?','검사 앞 대기열과 검사 가동률을 확인합니다. 검사 단계가 흐름을 제한하는지 살펴보고, 포장 중단 같은 다른 원인도 확인합니다.'],
 ['02','공정 데이터의 클라우드 흐름','3분 44초','10분마다 기록한 누적 완료 수량이 8, 17, 30이라면 구간별 완료 수량은 얼마일까요?','시작값이 0이고 초기화가 없다면 8, 9, 13개입니다. 원본 CSV는 보관하고 계산 결과는 별도 파일로 저장합니다.'],
 ['03','교육용 콘솔과 클라우드 연계','4분 14초','로그인했는데 결과표가 안 보인다면 무엇을 어떤 순서로 확인할까요?','먼저 선택한 프로젝트, 다음으로 파일 위치, 마지막으로 해당 위치를 조회할 권한을 확인합니다.']
];
export default function DigitalTwinLessons(){
 return <section aria-labelledby="digital-twin-lessons">
  <h2 id="digital-twin-lessons">디지털트윈 온라인 강의</h2>
  <p>영상을 본 뒤 잠시 멈추고 질문에 답해 보세요. 계산은 종이나 메모장으로 따라 할 수 있습니다.</p>
  <p><a href="/api/digital-twin/guide.html" target="_blank" rel="noreferrer">보충 교안 열기 · 사례와 계산표</a></p>
  {lessons.map(([id,title,duration,question,answer])=><article className="card" key={id}>
   <h3>{Number(id)}강 · {title}</h3><p>{duration}</p>
   <video controls preload="none" playsInline style={{width:'100%',maxWidth:800}} aria-label={title}>
    <source src={`/api/digital-twin/${id}.mp4`} type="video/mp4"/>
   </video>
   <p><strong>생각해 보기</strong> · {question}</p>
   <details><summary>해설 보기</summary><p>{answer}</p></details>
  </article>)}
 </section>;
}
