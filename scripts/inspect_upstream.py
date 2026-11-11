from pathlib import Path
from yt_dlp.extractor import gen_extractor_classes
import yt_dlp, inspect
from yt_dlp.extractor.tiktok import DouyinIE
from yt_dlp.extractor.bilibili import BiliBiliIE
print('Extractors:', [x.IE_NAME for x in gen_extractor_classes() if any(s in x.IE_NAME.lower() for s in ('kuaishou','douyin','bilibili'))])
for cls in (DouyinIE,BiliBiliIE):
 print(cls.__name__, cls._VALID_URL)
 print('Samples:', [t.get('url') for t in cls._TESTS[:2]])
print(inspect.getsource(DouyinIE._real_extract))
