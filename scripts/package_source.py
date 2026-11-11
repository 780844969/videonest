from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
out=ROOT.parent/'VideoNest-source.zip'
allowed={'app','tests','scripts','docs'}
top={'README.md','LICENSE','THIRD_PARTY.md','requirements.txt','requirements-dev.txt','requirements-lock.txt','start.cmd','.gitignore','pytest.ini'}
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(ROOT.rglob('*')):
        if not file.is_file():continue
        rel=file.relative_to(ROOT)
        if '__pycache__' in rel.parts or file.suffix=='.pyc':continue
        if (len(rel.parts)==1 and file.name in top) or (rel.parts[0] in allowed):
            archive.write(file,'videonest/'+str(rel))
print(out)
print(f'{out.stat().st_size} bytes')
