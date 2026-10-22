"""Download pinned public source archives without credentials or a global install."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile,datetime,concurrent.futures

ROOT=Path(__file__).resolve().parent.parent
SPECS={
 'fprime':('nasa/fprime','558b7ef48edd5d25f3bdddcbbe7afddb9cc22d09'),
 'hermes':('nasa/hermes','7145a1adbf1eb10a5b48bdd7e242a9156c896e4c'),
 'fprime-gds':('nasa/fprime-gds','ae809def30800445bda42f10b5a7fd2d7cee79f4'),
}
EXPECTED={
 'fprime':'91be3aa21af304874fa073afe206796a8a6f26f3ddc90a79de80edc77a3e60a0',
 'hermes':'14ee7d7541813a88717cb60022c8d8f0c1800e0310cd563607ffdcf779631eff',
 'fprime-gds':'b91c33eecbe95b499c634af5afc3a30f16ac457defd24fcb647abac093b2abea',
}
for name in ['downloads','vendor','outputs']:(ROOT/name).mkdir(exist_ok=True)
def acquire(item):
    name,(repo,ref)=item
    url=f'https://codeload.github.com/{repo}/zip/{ref}'
    archive=ROOT/'downloads'/(name+'-'+ref+'.zip')
    record=dict(name=name,repo=repo,ref=ref,url=url,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        if archive.exists():
            data=archive.read_bytes();record['acquisition']='existing pinned archive'
        else:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Public F Prime implementation source acquisition'}),timeout=45) as response:
                data=response.read();record['status']=response.status
            archive.write_bytes(data);record['acquisition']='public anonymous HTTPS'
        record.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        if record['sha256'] != EXPECTED[name]:raise ValueError('Pinned archive checksum mismatch')
        target=ROOT/'vendor'/name
        if target.exists():
            record['extraction']='existing target preserved'
        else:
            target.mkdir()
            with zipfile.ZipFile(archive) as z:
                top=z.namelist()[0].split('/')[0]+'/'
                for info in z.infolist():
                    relative=info.filename.removeprefix(top)
                    if not relative:continue
                    path=(target/relative).resolve()
                    if not path.is_relative_to(target.resolve()):raise ValueError('Unsafe archive member')
                    if info.is_dir():path.mkdir(parents=True,exist_ok=True)
                    else:
                        path.parent.mkdir(parents=True,exist_ok=True)
                        path.write_bytes(z.read(info))
            record['extraction']='complete pinned source tree'
        record['target']=str(target)
    except Exception as e:record['error']=f'{type(e).__name__}: {e}'
    return record
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:records=list(pool.map(acquire,SPECS.items()))
(ROOT/'outputs/source-acquisition.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print(json.dumps(records,indent=2))
if any('error' in r for r in records):raise SystemExit(1)
