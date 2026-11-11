import json
from pathlib import Path
from yt_dlp import YoutubeDL
from yt_dlp.extractor.tiktok import DouyinIE
from app.engine import options,build_choices
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'.data/douyin-diagnostic/mobile.html').read_text(encoding='utf-8')
with YoutubeDL(options()) as ydl:
    ie=DouyinIE(ydl)
    data=ie._search_json(r'window\._ROUTER_DATA\s*=',html,'router data','7702053444861454587')
    node=data['loaderData']['video_(id)/page']
    print('root keys',list(data))
    print('loaders',list(data.get('loaderData',{})))
    def walk(value,path='root'):
        if isinstance(value,dict):
            for k,v in value.items():
                if any(w in k.lower() for w in ('video','aweme','item_list','play_addr')): print(path+'.'+k, type(v).__name__, list(v)[:8] if isinstance(v,dict) else len(v) if isinstance(v,(str,list)) else v)
                walk(v,path+'.'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value): walk(v,path+'[]')
    walk(data)
    print('page keys',list(node))
    print('videoInfo keys',list(node.get('videoInfoRes',{})))
    items=node.get('videoInfoRes',{}).get('item_list',[])
    print('items',len(items))
    if items:
        print('item keys',list(items[0]))
        print('video keys',list(items[0].get('video',{})))
        parsed=ie._parse_aweme_video_app(items[0])
        info=ydl.process_ie_result(parsed,download=False)
        print(json.dumps({'title':info.get('title'),'duration':info.get('duration'),'choices':build_choices(info)},ensure_ascii=True))
