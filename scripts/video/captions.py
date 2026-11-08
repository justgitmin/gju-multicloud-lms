"""Display spelling is independent of pronunciation text used by speech synthesis."""
import re
TERMS={
 '에이 더블유 에스':'AWS','에더블유에스':'AWS','엔에이치엔 클라우드':'NHN Cloud','엔에이치엔':'NHN',
 '에스에스에이치':'SSH','에이치티티피에스':'HTTPS','에이치티티피':'HTTP','에이치티엠엘':'HTML',
 '아이피 버전 사':'IPv4','엘라스틱 아이피':'Elastic IP','브이피씨':'VPC','에이피아이':'API',
 '아이엠':'IAM','이씨투':'EC2','에스쓰리':'S3','알디에스':'RDS','티씨피':'TCP','씨피유':'CPU','아이피':'IP','피씨':'PC',
 '마이에스큐엘':'MySQL','엔진엑스':'Nginx','우분투':'Ubuntu','리눅스':'Linux','깃허브':'GitHub','라이트세일':'Lightsail',
 '엠피포':'MP4','웹브이티티':'WebVTT','이태그':'ETag','액세스 디나이드':'Access Denied',
 '십 점 이십 점 영 점 영, 슬래시 십육':'10.20.0.0/16',
 '십 점 이십 점 일 점 영, 슬래시 이십사':'10.20.1.0/24',
 '십 점 이십 점 이 점 영, 슬래시 이십사':'10.20.2.0/24',
 '영 점 영 점 영 점 영, 슬래시 영':'0.0.0.0/0','마이너스 아이':'-i','티씨피 이십이 번':'TCP 22번',
}
def display_caption(text):
 for a,b in sorted(TERMS.items(),key=lambda x:-len(x[0])):text=text.replace(a,b)
 text=re.sub(r'(?<![가-힣])에이(?=는|입니다|,)', 'A',text)
 text=re.sub(r'(?<![가-힣])비(?=는|입니다|,)', 'B',text)
 return text
