# Student practical alignment

The assigned-resource SSM environment is the operational reference. Existing video files are unchanged. Every AWS lesson now displays a task, an explicit difference from the video, a success criterion, and a direct guide anchor.

| Lesson | Actual task | Skip |
|---|---|---|
| AWS 01 | Assigned IAM login, Seoul region | Personal billing account |
| AWS 02 | Inspect shared network and draw flow | Create/change VPC or routes |
| AWS 03 | Session Manager with assigned session document | SSH key, MobaXterm, home IP registration |
| AWS 04 | Nginx and all demo-app files on assigned Ubuntu | EC2 creation |
| AWS 05 | Own bucket practice/test.txt upload/download | Bucket creation/public access |
| AWS 06 | MySQL from own server, labdb queries and test table | RDS creation/security changes |
| AWS 07 | Explain permitted actions | IAM policy editing |
| AWS 08 | Submit results, terminate session, AWS quiz | Shared infrastructure deletion |

The lab.py template was reviewed: SSM removes inbound port 22 and SSH keys; read-only EC2 network discovery is permitted; student bucket object writes are restricted to practice/*; private MySQL accepts only the assigned web security group; final deletion is operator-controlled. This is a source review, not a new live AWS pilot.

AWS quiz requires current-version completion of AWS-prefixed lessons only. NHN quiz requires NHN-prefixed lessons. Each lesson still needs validated 95% viewing. Unknown quiz IDs retain whole-course requirements. Both UI and server submission enforce the same helper. Five easy two-option questions per cloud; >=70 score means four of five. Existing quiz attempts remain, but changing question content increments the quiz version, so earlier attempts do not qualify for the revised quiz. Seeding unchanged content does not increment again.

Deployment: rebuild web and tools, run db:seed-assessments once with the rebuilt tools image, then recreate web. No schema migration required. Uploaded video hashes/version records are unchanged.

NHN: do not promise the AWS SSM flow applies. Project/member permissions, assigned compute/storage/DB and connection method must be verified against the actual NHN educational environment before publishing equivalent detailed instructions.
