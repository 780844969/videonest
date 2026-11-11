import httpx, zipfile, io
from pathlib import Path
u='https://codeload.github.com/JoeanAmier/KS-Downloader/zip/refs/heads/master'
r=httpx.get(u,timeout=60,trust_env=False,follow_redirects=True)
r.raise_for_status()
root=Path(__file__).resolve().parents[1]/'vendor'
with zipfile.ZipFile(io.BytesIO(r.content)) as z:
 for n in z.namelist():
  p=(root/n).resolve()
  if not p.is_relative_to(root.resolve()): raise ValueError('unsafe archive')
 z.extractall(root)
print('Downloaded upstream source')
