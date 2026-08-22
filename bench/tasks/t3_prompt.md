Write a Python script that reads nginx combined-format access log lines from stdin and prints one JSON object per line with keys:
ip, ts (the raw timestamp string inside brackets), method, path, status (int), bytes (int, "-" becomes 0), ua.
Malformed lines must be skipped silently. Use only the standard library.
Example line:
127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "http://ref/" "Mozilla/4.08 [en] (Win98; I ;Nav)"
Output ONLY the script in a single ```python block, no explanation.
