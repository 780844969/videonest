import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from notes.transcribe import audio_input

def test_native_audio_download_ignores_stale_merged_video_path(tmp_path):
    payload=b'native audio fixture'
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        row={'protocol':'http','url':f'http://127.0.0.1:{server.server_port}/track',
             'vcodec':'none','acodec':'aac','ext':'m4a','format_id':'audio'}
        result=audio_input({'id':'1','title':'test','extractor':'test','extractor_key':'Generic',
                            'requested_downloads':[{'filepath':'missing.m4a'}],'formats':[row]},tmp_path)
        assert result.read_bytes()==payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
