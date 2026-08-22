set -e
printf '%s\n' '127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "http://ref/" "Mozilla/4.08 [en] (Win98; I ;Nav)"' 'garbage line' '10.0.0.5 - bob [11/Oct/2000:00:00:01 +0000] "POST /api/v1/x?y=1 HTTP/1.1" 404 - "-" "curl/8.0"' | python3 sol.py > out.jsonl
python3 - <<'PY'
import json
L=[json.loads(l) for l in open('out.jsonl')]
assert len(L)==2, L
a,b=L
assert a['ip']=='127.0.0.1' and a['ts']=='10/Oct/2000:13:55:36 -0700' and a['method']=='GET' and a['path']=='/apache_pb.gif' and a['status']==200 and a['bytes']==2326 and a['ua'].startswith('Mozilla/4.08')
assert b['ip']=='10.0.0.5' and b['method']=='POST' and b['path']=='/api/v1/x?y=1' and b['status']==404 and b['bytes']==0 and b['ua']=='curl/8.0'
print("T3 OK")
PY
