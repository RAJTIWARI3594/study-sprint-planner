import copy,tempfile,unittest
from pathlib import Path
from datetime import datetime
from planner import plan,ics,page,export,validate
class PlannerTests(unittest.TestCase):
 def setUp(self):self.x={'start':'2026-10-26','days':2,'weekdays':[0,1],'daily_start_utc':'12:00','minutes_per_day':60,'session_minutes':30,'break_minutes':5,'tasks':[{'id':'a','title':'Synthetic task','deadline':'2026-10-27','minutes':90}]}
 def test_capacity(self):r=plan(self.x);self.assertEqual(r['total_scheduled_minutes'],90)
 def test_breaks(self):r=plan(self.x);self.assertEqual(r['sessions'][1]['start'][11:16],'12:35')
 def test_fragments(self):r=plan(self.x);self.assertEqual(r['sessions'][1]['minutes'],25)
 def test_overflow(self):self.x['tasks'][0]['minutes']=300;r=plan(self.x);self.assertEqual(r['total_unscheduled_minutes'],190)
 def test_deadline(self):self.x['tasks'][0]['deadline']='2026-10-25';self.assertEqual(plan(self.x)['sessions'],[])
 def test_priority(self):self.x['tasks']=[{'id':'b','title':'Low','deadline':'2026-10-27','minutes':30,'priority':3},{'id':'a','title':'High','deadline':'2026-10-27','minutes':30,'priority':1}];self.assertEqual(plan(self.x)['sessions'][0]['task_id'],'a')
 def test_empty(self):self.x['tasks']=[];self.assertEqual(plan(self.x)['total_scheduled_minutes'],0)
 def test_duplicate(self):
  self.x['tasks']*=2
  with self.assertRaises(ValueError):plan(self.x)
 def test_bad_time(self):
  self.x['daily_start_utc']='24:00'
  with self.assertRaises(ValueError):plan(self.x)
 def test_midnight(self):
  self.x['daily_start_utc']='23:30'
  with self.assertRaises(ValueError):plan(self.x)
 def test_bool(self):
  self.x['days']=True
  with self.assertRaises(ValueError):plan(self.x)
 def test_bad_weekdays(self):
  self.x['weekdays']=[7]
  with self.assertRaises(ValueError):plan(self.x)
 def test_immutable(self):before=copy.deepcopy(self.x);plan(self.x);self.assertEqual(self.x,before)
 def test_html_escape(self):self.x['tasks'][0]['title']='<script>alert(1)</script>';s=page(plan(self.x));self.assertNotIn('<script>',s);self.assertIn('&lt;script&gt;',s)
 def test_ics(self):s=ics(plan(self.x));self.assertIn('DTSTART:20261026T120000Z',s);self.assertEqual(s.count('BEGIN:VEVENT'),len(plan(self.x)['sessions']))
 def test_ics_folding(self):self.x['tasks'][0]['title']='é'*160;self.assertTrue(all(len(l.encode())<=75 for l in ics(plan(self.x)).split('\r\n')))
 def test_ics_escape(self):self.x['tasks'][0]['title']='Read, code; repeat';self.assertIn('Read\\, code\\; repeat',ics(plan(self.x)))
 def test_repeatable(self):self.assertEqual(ics(plan(self.x)),ics(plan(self.x)))
 def test_export(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'out';export(plan(self.x),p);self.assertEqual(len(list(p.iterdir())),3)
   with self.assertRaises(ValueError):export(plan(self.x),p)
 def test_conservation(self):r=plan(self.x);self.assertEqual(r['total_scheduled_minutes']+r['total_unscheduled_minutes'],90)
 def test_no_overlap(self):
  r=plan(self.x)
  for a,b in zip(r['sessions'],r['sessions'][1:]):self.assertLessEqual(datetime.fromisoformat(a['end']),datetime.fromisoformat(b['start']))
if __name__=='__main__':unittest.main()
