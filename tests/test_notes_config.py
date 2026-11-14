from notes.config import file_key

def test_local_config(tmp_path, monkeypatch):
    monkeypatch.delenv('VN_AI_KEY', raising=False)
    path=tmp_path/'.env'
    assert file_key(path)==''
    path.write_text('# comment\nUNRELATED=test\nVN_AI_KEY="dummy=value"\n', encoding='utf-8-sig')
    assert file_key(path)=='dummy=value'
    import os
    assert 'VN_AI_KEY' not in os.environ
