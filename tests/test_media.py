"""Real yt-dlp + FFmpeg checks using self-generated local media, no external platform."""
import functools
import http.server
import json
import subprocess
import threading
from pathlib import Path
import pytest
from app.engine import ffmpeg_path, build_choices, download

@pytest.fixture(scope='module')
def media_server(tmp_path_factory):
    root=tmp_path_factory.mktemp('media')
    binary=ffmpeg_path()
    def ff(*args):
        subprocess.run([binary,'-hide_banner','-loglevel','error','-y',*args],check=True,timeout=30)
    ff('-f','lavfi','-i','color=c=teal:s=320x180:d=1','-an','-c:v','libx264',str(root/'video.mp4'))
    ff('-f','lavfi','-i','sine=frequency=440:duration=1','-c:a','aac',str(root/'audio.m4a'))
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(root)))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    yield 'http://127.0.0.1:'+str(server.server_port),binary
    server.shutdown()
    server.server_close()

@pytest.mark.parametrize('choice,extension',[('video-0','.mp4'),('audio-mp3','.mp3')])
def test_real_download_merge_and_audio(tmp_path,media_server,choice,extension):
    base,binary=media_server
    info={'id':'self-generated','title':'自制测试素材','extractor':'test','extractor_key':'Generic',
          'formats':[
          {'format_id':'v','url':base+'/video.mp4','protocol':'http','ext':'mp4','height':180,'width':320,'vcodec':'avc1','acodec':'none'},
          {'format_id':'a','url':base+'/audio.m4a','protocol':'http','ext':'m4a','vcodec':'none','acodec':'aac'}]}
    (tmp_path/'source.json').write_text(json.dumps(info),encoding='utf-8')
    (tmp_path/'choices.json').write_text(json.dumps(build_choices(info)),encoding='utf-8')
    events=[]
    result=download(tmp_path,choice,events.append)
    output=tmp_path/result['filename']
    assert output.suffix==extension and output.stat().st_size>100
    decoded=subprocess.run([binary,'-v','error','-i',str(output),'-f','null','-'],capture_output=True,timeout=20)
    assert decoded.returncode==0,decoded.stderr
    assert any(e['state']=='downloading' for e in events)
    assert any(e['state']=='processing' for e in events)
