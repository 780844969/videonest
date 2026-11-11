import json
import pytest
from app.douyin import extract_detail
from app.security import UserError

def html(items):
    return '<script>window._ROUTER_DATA = ' + json.dumps({
        'loaderData': {'video_layout': None, 'video_(id)/page': {
            'videoInfoRes': {'item_list': items}}}}) + ';</script>'

def test_douyin_matches_requested_video_with_nested_json():
    wanted={'aweme_id':'123','desc':'quoted " and }','video':{'bit_rate':None,'play_addr':{'url_list':['https://example.com/v.mp4']}}}
    assert extract_detail(html([{'aweme_id':'999','video':{}},wanted]),'123')==wanted

@pytest.mark.parametrize('page',[
    '<html>login</html>',
    'window._ROUTER_DATA = {broken',
    html([{'aweme_id':'999','video':{'play_addr':{}}}]),
])
def test_douyin_rejects_missing_or_different_video(page):
    with pytest.raises(UserError): extract_detail(page,'123')


def test_kuaishou_mobile_matches_target_and_real_formats():
    from app.kuaishou import extract_mobile_html
    photo={'share_info':'userId=user&photoId=3target','caption':'视频','duration':8400,
           'manifest':{'adaptationSet':[{'representation':[{'url':'https://cdn.example/a.mp4','width':720,'height':1280,'fileSize':123,'videoCodec':'avc'}]}]}}
    page='window.INIT_STATE = '+json.dumps({'entry':{'photo':photo}})
    info=extract_mobile_html(page,'3target')
    assert info['duration']==8.4 and info['formats'][0]['height']==1280
    with pytest.raises(UserError): extract_mobile_html(page,'3other')
