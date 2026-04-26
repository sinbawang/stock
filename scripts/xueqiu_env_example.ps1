$env:XUEQIU_COOKIE = 'xq_a_token=REPLACE_ME; xqat=REPLACE_ME; u=REPLACE_ME'
$env:XUEQIU_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

c:/sinba/stock/venv/Scripts/python.exe scripts/run_hk_60m_chanlun_to_wechat.py `
  --symbol 03690 `
  --name 美团 `
  --start "2026-01-05 09:30" `
  --source xueqiu `
  --contact "888群" `
  --allow-search-switch