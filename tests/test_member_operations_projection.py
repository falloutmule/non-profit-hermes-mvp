import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
p=Path(__file__).resolve().parents[1]/'scripts/member_operations_projection.py'
spec=importlib.util.spec_from_file_location('projection',p); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def snapshot():
 return {'events':[{'id':1,'name':'Pantry','status':'draft','capacity':6,'startsAt':'2026-09-26T21:45:00Z','endsAt':'2026-09-26T23:00:00Z','location':'Venue','description':'PRIVATE TEXT','confirmedCount':1,'standbyCount':1,'reservedCount':1,'spotsAvailable':4}], 'staffing':[{'id':4,'eventId':1,'volunteerId':7,'status':'confirmed','phone':'PRIVATE PHONE'}], 'activity':[{'id':1,'createdAt':'now','source':'sms','action':'signup.created','target':'signup:4','result':'success','body':'PRIVATE SMS'}],'generatedAt':'now'}

class Tests(unittest.TestCase):
 def category_snapshot(self):
  s=snapshot();e=s['events'][0];e.update(name='Saturday Feed',capacity=10,confirmedCount=0,standbyCount=0,reservedCount=0,unfilled=10,spotsAvailable=0,signupAvailable=0,timezone='America/Denver',seriesId='saturday-pantry',recurrenceRule=json.dumps({'frequency':'weekly','weekday':5}),occurrenceDate='2026-09-26')
  e['categories']=[{'id':21,'categoryId':1,'key':'PANTRY','name':'Pantry','capacity':5,'active':True,'sortOrder':0,'confirmedCount':0,'standbyCount':0,'reservedCount':0,'unfilled':5,'spotsAvailable':0,'signupAvailable':0},{'id':22,'categoryId':2,'key':'SUPPLIES','name':'Harm Reduction / First Aid / Hygiene','capacity':4,'active':True,'sortOrder':1,'confirmedCount':0,'standbyCount':0,'reservedCount':0,'unfilled':4,'spotsAvailable':0,'signupAvailable':0},{'id':23,'categoryId':3,'key':'MEAL','name':'Meal','capacity':1,'active':True,'sortOrder':2,'confirmedCount':0,'standbyCount':0,'reservedCount':0,'unfilled':1,'spotsAvailable':0,'signupAvailable':0}]
  s['staffing']=[];return s
 def test_zero_signup_category_summary_and_draft_unfilled(self):
  rows=m.member_rows(self.category_snapshot(),{},'now')
  cats=[dict(zip(rows['Staffing Categories'][0],r)) for r in rows['Staffing Categories'][1:]]
  self.assertEqual([r['Category key'] for r in cats],['PANTRY','SUPPLIES','MEAL'])
  self.assertEqual(cats[0]['Occurrence category ID'],'21');self.assertEqual(cats[0]['Definition category ID'],'1');self.assertEqual(cats[0]['Occurrence date'],'2026-09-26');self.assertIn('03:45 PM MDT',cats[0]['Start (Denver)']);self.assertIn('05:00 PM MDT',cats[0]['End (Denver)']);self.assertEqual(cats[0]['Snapshot UTC'],'now')
  self.assertEqual([r['Unfilled places'] for r in cats],['5','4','1']);self.assertEqual([r['Signup available'] for r in cats],['0','0','0'])
  e=dict(zip(rows['Events'][0],rows['Events'][1]));self.assertEqual(e['Capacity'],'10');self.assertEqual(e['Status'],'draft');self.assertEqual(e['Series ID'],'saturday-pantry');self.assertEqual(e['Recurrence'],'Every Saturday');self.assertEqual(e['Occurrence date'],'2026-09-26');self.assertIn('03:45 PM MDT',e['Start (Denver)']);self.assertEqual(len(rows['Staffing']),1)
 def test_category_staffing_and_audit_no_historical_guess(self):
  s=self.category_snapshot();s['staffing']=[{'id':4,'eventId':1,'volunteerId':7,'status':'confirmed','categoryId':1,'occurrenceCategoryId':21,'categoryKey':'PANTRY','categoryName':'Pantry','phone':'SECRET'}]
  s['activity'].append({'id':2,'createdAt':'now','source':'sms','action':'signup.created','target':'signup:4','result':'success','categoryId':1,'occurrenceCategoryId':21,'categoryKey':'PANTRY','categoryName':'Pantry','rawBody':'SECRET'})
  rows=m.member_rows(s,{},'now');self.assertEqual(rows['Staffing'][1][-4:],['1','PANTRY','Pantry','21']);self.assertEqual(rows['Activity'][1][-4:],['','','','']);self.assertEqual(rows['Activity'][2][-4:],['1','PANTRY','Pantry','21']);self.assertNotIn('SECRET',json.dumps(rows))
 def test_category_signup_availability_comes_from_board(self):
  s=self.category_snapshot();e=s['events'][0];e['status']='published';e['categories'][0].update(confirmedCount=2,reservedCount=1,unfilled=2,signupAvailable=2,spotsAvailable=2)
  rows=m.member_rows(s,{},'now');r=dict(zip(rows['Staffing Categories'][0],rows['Staffing Categories'][1]));self.assertEqual(r['Reserved offers'],'1');self.assertEqual(r['Unfilled places'],'2');self.assertEqual(r['Signup available'],'2')
  e['categories'][0]['signupAvailable']=0
  rows=m.member_rows(s,{},'now');self.assertEqual(rows['Staffing Categories'][1][9],'0')
 def test_one_calendar_operation_per_occurrence_not_category(self):
  with tempfile.TemporaryDirectory() as d:
   b=Mock();b.call.side_effect=lambda route,payload=None:{'pending':[{'id':3}]} if route=='pending' else self.category_snapshot()
   g=Mock();g.sources.return_value={}
   m.run_once(b,g,{'workbook_id':'test'},Path(d)/'state.json')
   self.assertEqual(g.calendar_upsert.call_count,1)
  g=object.__new__(m.Google);g.calendar=Mock();g.calendar_target='test'
  g.calendar_upsert(self.category_snapshot()['events'][0],{});g.calendar.events.assert_not_called()
 def test_projection_allowlist(self):
  rows=m.member_rows(snapshot(),{},'now'); text=json.dumps(rows)
  self.assertNotIn('PRIVATE',text);self.assertIn('Volunteer #7',text);self.assertIn('MDT',text)
 def test_privacy_gate_and_no_donor(self):
  sources={'Donations':[{'DonationID':'D1','DonorContact':'SECRET','DonorName':'SECRET','PrivacyLevel':'public-safe','PublicListingAllowed':'yes','DonationType':'food'},{'DonationID':'D2','PrivacyLevel':'private','PublicListingAllowed':'yes'}], 'Reports':[{'ReportID':'R','PrivacyLevel':'public-safe','PublicSummaryAllowed':'yes','Summary':'SECRET','SensitiveDetails':'SECRET','PublicSummaryDraft':'Approved summary'}], 'Tasks':[{'TaskID':'T','TaskTitle':'SECRET'}]}
  rows=m.member_rows(snapshot(),sources,'now')
  self.assertEqual(len(rows['Donations Summary']),2);self.assertEqual(len(rows['Tasks']),1);self.assertNotIn('SECRET',json.dumps(rows));self.assertIn('Approved summary',json.dumps(rows))
 def test_public_need_gate(self):
  rows=m.member_rows(snapshot(),{'Requests':[{'RequestID':'1','PrivacyLevel':'public-safe','ConsentToShare':'no'},{'RequestID':'2','PrivacyLevel':'public-safe','ConsentToShare':'yes'}],'Inventory':[{'ItemID':'3','PublicNeedAllowed':'yes','Notes':'SECRET'}]},'now')
  self.assertEqual(len(rows['Needs']),3); self.assertEqual(len(rows['Inventory']),2);self.assertNotIn('SECRET',json.dumps(rows))
 def test_member_authorization_not_public_publication(self):
  sources={'Tasks':[{'TaskID':'T','TaskTitle':'Reviewed title'},{'TaskID':'P','TaskTitle':'SECRET','PrivacyLevel':'private-review'}], 'Inventory':[{'ItemID':'I','ItemName':'Socks','PublicNeedAllowed':'no'},{'ItemID':'P','ItemName':'SECRET','PrivacyLevel':'private'}]}
  rows=m.member_rows(snapshot(),sources,'now',{'Tasks':['T','P']})
  self.assertIn('Reviewed title',json.dumps(rows));self.assertIn('Socks',json.dumps(rows));self.assertNotIn('SECRET',json.dumps(rows))
 def test_legacy_audit_prefixed_private_and_ambiguous_targets(self):
  sources={'Requests':[{'RequestID':'R1','PrivacyLevel':'board-visible'},{'RequestID':'PRIVATE','PrivacyLevel':'private-review'},{'RequestID':'SHARED','PrivacyLevel':'board-visible'}], 'Inventory':[{'ItemID':'I1','ItemName':'Socks'}], 'Tasks':[{'TaskID':'SHARED','TaskTitle':'PRIVATE'}]}
  refs=['Requests/R1','Inventory/I1','R1','Requests/PRIVATE','PRIVATE','SHARED','Tasks/SHARED','Requests/SHARED']
  sources['AuditLog']=[{'AuditID':str(i),'Timestamp':'now','Action':'create','TargetItem':ref,'Before':'SECRET','After':'SECRET','Actor':'SECRET'} for i,ref in enumerate(refs)]
  rows=m.member_rows(snapshot(),sources,'now')['Activity'][1:]
  projected=[r[4] for r in rows if str(r[0]).startswith('google:')]
  self.assertEqual(projected,['Requests/R1','Inventory/I1','R1','Requests/SHARED'])
  self.assertNotIn('SECRET',json.dumps(rows))
 def test_duplicate_source_id_does_not_expose_ambiguous_audit(self):
  sources={'Requests':[{'RequestID':'R','PrivacyLevel':'board-visible'},{'RequestID':'R','PrivacyLevel':'private-review'}], 'AuditLog':[{'AuditID':'A','TargetItem':'Requests/R','Action':'update'}]}
  rows=m.member_rows(snapshot(),sources,'now')['Activity']
  self.assertFalse(any(str(r[0]).startswith('google:') for r in rows))
 def test_completion(self):
  s=snapshot();s['events'][0]['completion']={'volunteerId':7,'completedAt':'now','statement':'Socks picked up'}
  text=json.dumps(m.member_rows(s,{},'now'));self.assertIn('Socks picked up',text);self.assertIn('Volunteer #7',text)
 def test_google_failure_does_not_ack(self):
  with tempfile.TemporaryDirectory() as d:
   b=Mock();b.call.side_effect=lambda route,payload=None:{'pending':[{'id':3}]} if route=='pending' else snapshot()
   g=Mock();g.sources.return_value={};g.write_views.side_effect=ValueError('SECRET')
   c={'workbook_id':'test'};path=Path(d)/'state.json'
   with self.assertRaisesRegex(RuntimeError,'retry pending'):m.run_once(b,g,c,path)
   self.assertFalse(any(x.args[0]=='ack' for x in b.call.call_args_list));self.assertNotIn('SECRET',path.read_text());self.assertEqual(c['status'],'sync pending')
 def test_success_ack_after_views_and_repeat(self):
  with tempfile.TemporaryDirectory() as d:
   calls=[];b=Mock();b.call.side_effect=lambda route,payload=None:(calls.append(route) or ({'pending':[{'id':3}]} if route=='pending' else snapshot()))
   g=Mock();g.sources.return_value={};g.write_views.side_effect=lambda *a:calls.append('views')
   c={'workbook_id':'test'}
   for _ in range(2):self.assertEqual(m.run_once(b,g,c,Path(d)/'state.json'),'current')
   self.assertLess(calls.index('views'),calls.index('ack'));self.assertEqual(g.write_views.call_args_list[0].args[1]['Events'],g.write_views.call_args_list[1].args[1]['Events'])
 def test_idle_reconcile_and_backoff(self):
  with tempfile.TemporaryDirectory() as d:
   b=Mock();b.call.return_value={'pending':[]};g=Mock();c={'workbook_id':'test','last_reconciliation_epoch':m.time.time()}
   self.assertEqual(m.run_once(b,g,c,Path(d)/'s'),'idle');g.sources.assert_not_called()
   c['backoff_until']=m.time.time()+100
   self.assertEqual(m.run_once(b,g,c,Path(d)/'s'),'backoff')
 def test_calendar_draft_and_stable_id(self):
  g=object.__new__(m.Google);g.calendar=Mock();g.calendar_target='test'
  g.calendar_upsert(snapshot()['events'][0],{});g.calendar.events.assert_not_called()
  self.assertEqual(m.calendar_id(1),m.calendar_id(1));self.assertNotEqual(m.calendar_id(1),m.calendar_id(2))
 def test_sheet_replace_atomic_and_no_formula(self):
  g=object.__new__(m.Google);g.sheets=Mock()
  g.sheets.spreadsheets().get().execute.return_value={'sheets':[{'properties':{'title':'Events','sheetId':100,'gridProperties':{'rowCount':1000}}}]}
  g.write_views('book',{'Events':[['=IMPORTXML(secret)']]})
  body=g.sheets.spreadsheets().batchUpdate.call_args.kwargs['body']
  self.assertEqual(body['requests'][0]['updateCells']['range'],{'sheetId':100})
  self.assertEqual(body['requests'][0]['updateCells']['rows'][0]['values'][0]['userEnteredValue'],{'stringValue':'=IMPORTXML(secret)'})
 def test_calendar_retry_uses_same_identity_and_no_attendees(self):
  g=object.__new__(m.Google);g.calendar=Mock();g.calendar_target='target'
  e=snapshot()['events'][0];e['status']='published';e['timezone']='America/New_York'
  class Missing(Exception):resp=type('Response',(),{'status':404})()
  g.calendar.events().get().execute.side_effect=Missing()
  for i in range(2):g.calendar_upsert(e,{})
  calls=g.calendar.events().insert.call_args_list
  self.assertEqual(calls[0].kwargs['body']['id'],calls[1].kwargs['body']['id'])
  self.assertEqual(calls[0].kwargs['body']['start']['timeZone'],'America/New_York')
  self.assertEqual(calls[0].kwargs['sendUpdates'],'none');self.assertNotIn('attendees',calls[0].kwargs['body'])
 def test_cancel_missing_calendar_never_creates(self):
  g=object.__new__(m.Google);g.calendar=Mock();g.calendar_target='target'
  e=snapshot()['events'][0];e['status']='cancelled'
  class Missing(Exception):resp=type('Response',(),{'status':404})()
  g.calendar.events().get().execute.side_effect=Missing()
  g.calendar_upsert(e,{});g.calendar.events().insert.assert_not_called()
 def test_status_no_secrets(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c';m.save(p,{'workbook_id':'abc','token':'SECRET','last_success':'now','status':'current'})
   self.assertNotIn('SECRET',json.dumps(m.inspection_status(p)))
 def test_concurrent_lock(self):
  with tempfile.TemporaryDirectory() as d:
   with m.exclusive(Path(d)/'lock'):
    with self.assertRaises(OSError):
     with m.exclusive(Path(d)/'lock'):pass
if __name__=='__main__':unittest.main()
