import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from volunteer_board_operator import operate,BoardError,allowed_route,event_details,summary
from nonprofit_workflow import board

CATEGORIES=[dict(id=i,categoryId=i,key=k,name=n,capacity=cap,active=True,standbyEnabled=True,sortOrder=i,confirmedCount=0,standbyCount=0,reservedCount=0,spotsAvailable=0,unfilledCount=cap,signupEligible=False) for i,k,n,cap in [(1,'PANTRY','Pantry',5),(2,'SUPPLIES','Harm Reduction / First Aid / Hygiene',4),(3,'MEAL','Meal',1)]]
class Client:
    config={'real_use_review_complete':False}
    def __init__(self):self.calls=[]
    def events(self):return [dict(id=1,name='Saturday Feed',slug='PANTRY20260926',seriesId='saturday-pantry',startsAt='2026-09-26T21:45:00Z',endsAt='2026-09-26T23:00:00Z',timezone='America/Denver',location='302 South Ave',status='draft',capacity=10,staffingEnabled=True,standbyEnabled=True,completionReportRequired=False,categories=CATEGORIES)]
    def request(self,method,route,payload=None):
        if method!='GET':self.calls.append((method,route,payload));return {'ok':True}
        return {'signups':[]} if route.endswith('/staffing') else self.events()[0]

def definition():return [{k:c[k] for k in ['key','name','capacity','active','standbyEnabled','sortOrder']} for c in CATEGORIES]
def test_categories_require_explicit_authorization_and_scope():
    c=Client()
    with pytest.raises(BoardError):operate('categories',{'categories':definition()},client=c)
    with pytest.raises(BoardError):operate('categories',{'categories':definition()},client=c,authorized=True)
    assert c.calls==[]

def test_one_and_future_use_narrow_api():
    c=Client()
    operate('categories',{'scope':'one','eventId':1,'categories':definition()},client=c,authorized=True)
    operate('categories',{'scope':'future','seriesId':'saturday-pantry','effectiveFrom':'2026-09-26','categories':definition()},client=c,authorized=True)
    assert c.calls[0][:2]==('PUT','/api/admin/events/1/categories')
    assert c.calls[1][:2]==('PUT','/api/admin/series/saturday-pantry/categories')
    assert not allowed_route('PUT','/api/admin/events/1')
    assert not allowed_route('PUT','/api/admin/events/../categories')

def test_cards_and_staffing_keep_full_category_name_and_draft_boundary():
    c=Client();e=c.events()[0]
    for text in [event_details(e),summary([e]),board('',c),board('show 1',c)]:
        assert 'Harm Reduction / First Aid / Hygiene' in text
        assert 'Pantry' in text and 'Meal' in text
    assert 'Total places: 10' in event_details(e)
    assert 'Not open for signup (draft)' in board('',c)
    assert '5 unfilled' in board('',c)
    assert 'SMS SUPPLIES' in event_details(e)
