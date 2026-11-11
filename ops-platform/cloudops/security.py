import base64,hashlib,hmac,json,secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def password_hash(password):
 if not 12<=len(password)<=128:raise ValueError('비밀번호는 12~128자입니다.')
 salt=secrets.token_bytes(16);key=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1)
 return salt.hex()+':'+key.hex()

def verify_password(password,encoded):
 try:
  if len(password)>128:return False
  salt,key=encoded.split(':');actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1)
  return hmac.compare_digest(actual.hex(),key)
 except (ValueError,TypeError):return False

def digest(value):return hashlib.sha256(value.encode()).hexdigest()

class Vault:
 def __init__(self,key):
  try:self.key=base64.b64decode(key,validate=True)
  except Exception:raise ValueError('OPS_MASTER_KEY must be base64 of 32 random bytes') from None
  if len(self.key)!=32:raise ValueError('OPS_MASTER_KEY must be 32 bytes')
 def seal(self,value,context):
  nonce=secrets.token_bytes(12)
  return base64.b64encode(nonce+AESGCM(self.key).encrypt(nonce,json.dumps(value).encode(),context.encode())).decode()
 def open(self,value,context):
  raw=base64.b64decode(value)
  return json.loads(AESGCM(self.key).decrypt(raw[:12],raw[12:],context.encode()))
