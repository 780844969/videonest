"""Install an immutable revision of the public multilingual base model locally."""
import hashlib
import os
from pathlib import Path
import httpx

def prepare():
    dest=Path(__file__).resolve().parents[1]/'.data'/'notes-models'/'base-local'
    dest.mkdir(exist_ok=True,parents=True)
    host='https://huggingface.co'
    repo='Systran/faster-whisper-base'
    with httpx.Client(follow_redirects=True,timeout=90) as client:
        meta=client.get(f'{host}/api/models/{repo}',params={'blobs':'true'})
        meta.raise_for_status()
        data=meta.json()
        for item in data['siblings']:
            name=item['rfilename']
            if name not in ('config.json','model.bin','tokenizer.json','vocabulary.txt','vocabulary.json','preprocessor_config.json'): continue
            target=dest/name
            temp=target.with_suffix(target.suffix+'.part')
            digest=hashlib.sha256()
            with client.stream('GET',f"{host}/{repo}/resolve/{data['sha']}/{name}") as response:
                if response.status_code!=200: raise RuntimeError(f'{name}: HTTP {response.status_code}')
                with temp.open('wb') as file:
                    for part in response.iter_bytes():
                        file.write(part)
                        digest.update(part)
            if item.get('size') and temp.stat().st_size!=item['size']: raise RuntimeError('Size mismatch')
            sha=(item.get('lfs') or {}).get('sha256')
            if sha and sha!=digest.hexdigest(): raise RuntimeError('Checksum mismatch')
            os.replace(temp,target)
            print('Prepared',name,flush=True)
        (dest/'revision.txt').write_text(data['sha'],encoding='ascii')

if __name__=='__main__': prepare()
