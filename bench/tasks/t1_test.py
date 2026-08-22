from lru_ttl import LRUTTL
t=[0.0]; clk=lambda: t[0]
c=LRUTTL(2, 10, clock=clk)
c.put('a',1); c.put('b',2); assert c.get('a')==1
c.put('c',3); assert c.get('b') is None and c.get('a')==1 and c.get('c')==3
t[0]=5; c.put('a',11); t[0]=12; assert c.get('c') is None and c.get('a')==11 and len(c)==1
t[0]=16; assert c.get('a') is None and len(c)==0
print("T1 OK")
