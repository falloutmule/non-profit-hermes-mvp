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


class OperatorBoundaryTests(TestCase):
    def test_exact_route_boundary(self):
        from volunteer_board_operator import allowed_route
        self.assertTrue(allowed_route('GET','/api/admin/events/1/signups'))
        self.assertTrue(allowed_route('POST','/api/admin/messages/send'))
        for route in ('/api/admin/eventsXYZ','/api/admin/events/../messages/send','/api/admin/events?token=x','https://example.com'):
            self.assertFalse(allowed_route('GET',route))
    def test_mutations_require_authorization_and_real_use_review(self):
        from volunteer_board_operator import operate
        c=Fake()
        for action in ('create','update','send','drop'):
            with self.assertRaises(BoardError):operate(action,{},client=c)
        for action in ('send','drop'):
            with self.assertRaises(BoardError):operate(action,{},client=c,authorized=True)
        self.assertEqual(c.writes,0)
    def test_create_and_update_use_api(self):
        from volunteer_board_operator import operate
        c=Fake();event=pantry_occurrences(datetime(2026,9,23,tzinfo=ZoneInfo('America/Denver')))[0]
        operate('create',{'event':event},client=c,authorized=True)
        operate('update',{'eventId':1,'scope':'one','event':{'capacity':7}},client=c,authorized=True)
        self.assertEqual(c.rows[0]['capacity'],7)
        with self.assertRaises(BoardError):operate('update',{'eventId':1,'event':{'status':'published'}},client=c,authorized=True)
    def test_signup_privacy_and_counts(self):
        from volunteer_board_operator import operate
        class SignupClient(Fake):
            def request(self,method,route,payload=None):
                if route.endswith('/signups'):return {'signups':[{'id':1,'volunteerId':2,'status':'standby','standbyPosition':1,'displayName':'PRIVATE','phone':'PRIVATE','smsStatus':'opted_in'}]}
                return {'capacity':6}
        r=operate('signups',{'eventId':1},client=SignupClient())
        self.assertEqual(r['counts']['standby'],1)
        self.assertNotIn('PRIVATE',str(r))
    def test_send_and_drop_use_board_only(self):
        from volunteer_board_operator import operate
        class Sender(Fake):
            config={'real_use_review_complete':True}
            def request(self,method,route,payload=None):
                self.calls.append((method,route,payload));return {'status':'queued','dropped':True}
        c=Sender();c.calls=[]
        r=operate('send',{'volunteerId':2,'body':'Approved content'},client=c,authorized=True)
        self.assertEqual(c.calls[0][1],'/api/admin/messages/send');self.assertNotIn('Approved content',str(r))
        operate('drop',{'signupId':3},client=c,authorized=True)
        self.assertEqual(c.calls[1][1],'/api/admin/signups/3/drop')
