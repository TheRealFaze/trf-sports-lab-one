from datetime import datetime, timezone
from trf_one.process_model import ProcessXGProxy, ProcessProxyConfig
from trf_one.providers.football_data_uk import ProcessMatchRecord


def sample():
    rows=[]
    for i in range(30):
        rows.append(ProcessMatchRecord(
            datetime(2025,1,1,tzinfo=timezone.utc),
            "A","B",
            2 if i%2==0 else 1, 1,
            14,9,5,2,6,3
        ))
    return rows


def test_process_proxy_fit_and_transform():
    m=ProcessXGProxy(ProcessProxyConfig(max_iter=200)).fit(sample())
    rows=m.transform(sample()[:2])
    assert len(rows)==2
    assert rows[0].home_xg is not None and rows[0].home_xg>0
    assert rows[0].away_xg is not None and rows[0].away_xg>0
    assert rows[0].home_xg > rows[0].away_xg
