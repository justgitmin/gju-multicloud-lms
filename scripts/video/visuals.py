"""Precise, code-drawn teaching diagrams; no fabricated console screenshots."""
def lines(d,text,font,width):
 result=[];line=''
 for ch in text:
  if d.textlength(line+ch,font=font)>width and line:result.append(line);line=''
  line+=ch
 if line:result.append(line)
 return result

def box(d,rect,title,subtitle,fonts,active=False):
 d.rounded_rectangle(rect,radius=16,fill='#e1eee7' if active else '#ffffff',outline='#26735b' if active else '#bccfc4',width=4 if active else 2)
 x,y,_,_=rect
 d.text((x+22,y+18),title,font=fonts[30],fill='#173f2f')
 d.text((x+22,y+68),subtitle,font=fonts[22],fill='#64786a')
def arrow(d,points,active=False):
 color='#d18b23' if active else '#a7b8ad';d.line(points,fill=color,width=7 if active else 4)
 x,y=points[-1];px,py=points[-2]
 if x>px:d.polygon([(x,y),(x-16,y-10),(x-16,y+10)],fill=color)
 elif x<px:d.polygon([(x,y),(x+16,y-10),(x+16,y+10)],fill=color)
 elif y>py:d.polygon([(x,y),(x-10,y-16),(x+10,y-16)],fill=color)
 else:d.polygon([(x,y),(x-10,y+16),(x+10,y+16)],fill=color)

def draw_visual(d,scene,fonts,index,total):
 kind=scene['visual'];stage=scene.get('stage',0);step=min(3,index*4//max(1,total))
 # The sentence progress marker and focus card change together with narration.
 d.rounded_rectangle((100,360,650,805),radius=20,fill='#e8eee7')
 bullets=scene['bullets'];highlight=min(len(bullets)-1,index*len(bullets)//max(1,total))
 d.text((130,385),'POINT / '+str(highlight+1),font=fonts[22],fill='#9d661f')
 for i,bullet in enumerate(bullets):
  y=440+i*110;color='#183f2e' if i==highlight else '#788a7d'
  if i==highlight:d.rounded_rectangle((115,y-6,124,y+65),radius=4,fill='#d79835')
  for j,line in enumerate(lines(d,bullet,fonts[30],460)):d.text((145,y+j*42),line,font=fonts[30],fill=color)
 if kind=='quiz':
  d.rounded_rectangle((700,360,1820,805),radius=20,fill='#173c30')
  qlines=lines(d,scene['question'],fonts[34],1010)
  for i,line in enumerate(qlines):d.text((745,395+i*50),line,font=fonts[34],fill='white')
  reveal='정답' in scene.get('_caption','') or scene.get('_revealed',False)
  for i,option in enumerate(scene['options']):
   y=535+i*105;answer=reveal and i==scene['answer']
   d.rounded_rectangle((740,y,1780,y+80),radius=12,fill='#d9ad5c' if answer else '#2d5142')
   d.text((765,y+19),option,font=fonts[30],fill='#153729' if answer else '#fff')
  d.text((745,760),'정답 공개 · 이유를 설명해 보세요' if reveal else 'PAUSE & THINK / 멈추고 먼저 선택',font=fonts[22],fill='#d9b46c')
 elif kind=='route':
  d.rounded_rectangle((700,360,1820,805),radius=20,fill='white',outline='#c8d8ce',width=2)
  d.text((740,390),'ROUTE TABLE / 웹 서브넷에 연결',font=fonts[30],fill='#173c30')
  rows=[('목적지','대상'),('10.20.0.0/16','local'),('0.0.0.0/0','Internet Gateway')]
  for i,(dest,target) in enumerate(rows):
   y=475+i*85
   if i==min(2,step):d.rounded_rectangle((730,y-5,1780,y+70),radius=10,fill='#e5eee5')
   d.text((755,y+8),dest,font=fonts[30],fill='#204530');d.text((1260,y+8),target,font=fonts[30],fill='#204530')
  d.text((750,755),'더 구체적인 목적지 경로가 우선됩니다.',font=fonts[22],fill='#6a7b70')
 elif kind=='mission':
  d.rounded_rectangle((700,360,1820,805),radius=20,fill='#fff',outline='#c8d8ce',width=2)
  d.text((750,400),'03:00 / 직접 그려 보기',font=fonts[54],fill='#1c523c')
  for i,text in enumerate(['① 큰 경계 + 두 구역','② 필요한 통신만 화살표로','③ 인터넷 경로와 접근 조건']):
   d.text((765,510+i*75),text,font=fonts[34],fill='#234c37' if i<=highlight else '#9eaca1')
  d.text((750,755),'영상 정지 후 미션 수행 · 가짜 대기 시간 없음',font=fonts[22],fill='#6a7b70')
 elif kind=='recap':
  for i,(title,subtitle) in enumerate([('주소','계정 / 리전 / IP'),('길','서브넷 / 라우팅 / IGW'),('문','보안 / OS / 서비스')]):
   box(d,(710,370+i*145,1810,495+i*145),title,subtitle,fonts,i==highlight)
 else:
  # VPC contains subnet examples. Internet gateway is explicitly marked at the edge.
  d.rounded_rectangle((1080,370,1815,805),radius=20,outline='#59876d',width=3,fill='#eaf1e9')
  d.text((1100,385),'VPC 10.20.0.0/16',font=fonts[26],fill='#345d42')
  box(d,(720,460,1020,585),'Internet','사용자 / 노트북',fonts,step==0)
  if stage>=1:
   box(d,(1110,450,1450,585),'WEB Subnet','10.20.1.0/24' if stage>=2 else '웹 구역 배치 예정',fonts,step==2)
  if stage>=2:
   box(d,(1110,650,1450,785),'DB Subnet','10.20.2.0/24',fonts,step==3)
  if stage>=3:
   box(d,(1510,450,1785,585),'IGW','VPC 경계 연결',fonts,step==1)
   arrow(d,[(1020,515),(1060,430),(1645,430),(1645,450)],step<=1)
   arrow(d,[(1510,535),(1450,535)],step==2)
  if stage>=5:
   d.text((1490,635),'인터넷 경로 + 공인 IPv4',font=fonts[22],fill='#946321')
   d.text((1490,675),'보안·서비스도 확인',font=fonts[22],fill='#946321')
  if stage>=6:arrow(d,[(1280,585),(1280,650)],step==3)
  if stage==0:
   d.text((1100,490),'? 연결 경로를 찾아보세요',font=fonts[34],fill='#a2691d')

 d.rectangle((100,816,1820,821),fill='#dce5dc')
 d.rectangle((100,816,100+1720*(index+1)/max(1,total),821),fill='#c49139')
