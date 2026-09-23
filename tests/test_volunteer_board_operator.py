import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest import TestCase
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from volunteer_board_operator import pantry_occurrences,prepare_pantry,dispatch,BoardError,BoardClient
class Fake:
    config={'real_use_review_complete':False}
    def __init__(self):self.rows=[];self.writes=0
    def events(self):return self.rows
    def request(self,method,route,payload=None):
        if method=='POST':
            self.writes+=1;r=dict(payload,id=len(self.rows)+1);self.rows.append(r);return r
        if method=='GET':return self.rows[int(route.rsplit('/',1)[1])-1]
        self.writes+=1;self.rows[0].update(payload);return self.rows[0]
class BoardOperatorTests(TestCase):
    def test_dst_and_occurrences(self):
        rows=pantry_occurrences(datetime(2026,9,23,tzinfo=ZoneInfo('America/Denver')))
        self.assertEqual(len(rows),12)
        self.assertEqual(rows[0]['slug'],'PANTRY20260926')
        self.assertEqual(rows[0]['startsAt'],'2026-09-26T21:45:00Z')
        self.assertEqual(rows[6]['startsAt'],'2026-11-07T22:45:00Z')
        for r in rows:
            local=datetime.fromisoformat(r['startsAt'].replace('Z','+00:00')).astimezone(ZoneInfo('America/Denver'))
            self.assertEqual((local.weekday(),local.hour,local.minute),(5,15,45));self.assertEqual(r['capacity'],6);self.assertEqual(r['status'],'draft')
    def test_prepare_idempotency(self):
        c=Fake();now=datetime(2026,9,23,tzinfo=ZoneInfo('America/Denver'))
        self.assertEqual(len(prepare_pantry(c,now)),12);self.assertEqual(prepare_pantry(c,now),[]);self.assertEqual(c.writes,12)
    def test_drift_not_overwritten(self):
        c=Fake();now=datetime(2026,9,23,tzinfo=ZoneInfo('America/Denver'));prepare_pantry(c,now);c.rows[0]['capacity']=9
        with self.assertRaises(BoardError):prepare_pantry(c,now)
        self.assertEqual(c.rows[0]['capacity'],9)
    def test_publication_gate_and_no_sms(self):
        c=Fake();self.assertIn('held',dispatch('publish 1',c));self.assertIn('No SMS',dispatch('send all',c));self.assertEqual(c.writes,0)
    def test_no_secrets_in_failure(self):
        class Broken(Fake):
            def events(self):raise RuntimeError('secret token private phone')
        result=dispatch('list',Broken());self.assertNotIn('secret token',result);self.assertIn('failed',result)
    def test_credential_destination(self):
        with self.assertRaises(BoardError):BoardClient({'base_url':'https://example.com','admin_token':'x'*32})
