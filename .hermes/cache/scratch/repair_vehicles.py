import re
from pathlib import Path

p = Path("/root/wildcat/src/wildcat/cars/vehicles.py")
t = p.read_text()
count = t.count("<class '")
new = re.sub(r"<class '[^']+\.(\w+)'>", lambda m: m.group(1), t)
p.write_text(new)
print("repaired replacements:", count)
