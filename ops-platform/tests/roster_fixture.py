import datetime
from cloudops.lms_roster import approve

def snapshot_for(config):
 return {'version':1,'kind':'approved-enrollments','courseId':'gju-multicloud-2026','courseTitle':'Test course','exportedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'students':[{'userId':'user-'+code,'enrollmentId':'enrollment-'+code,'name':'Student '+code,'email':code+'@example.com','studentNumber':code} for code in config['students']]}

def approved_config(config):
 data=snapshot_for(config)
 return approve(config,data,{p['userId']:code for code,p in zip(config['students'],data['students'])},{},{})
