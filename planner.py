import argparse,hashlib,html,json,re,sys
from pathlib import Path
from datetime import date,datetime,time,timedelta,timezone

def integer(x,name,lo,hi):
 if type(x)!=int or not lo<=x<=hi:raise ValueError(f'{name}: integer {lo}–{hi} required')
 return x
def day(x):
 if not isinstance(x,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',x):raise ValueError('Date must be YYYY-MM-DD')
 return date.fromisoformat(x)
def validate(x):
 if not isinstance(x,dict):raise ValueError('JSON object required')
 start=day(x['start']);days=integer(x['days'],'Days',1,60);minutes=integer(x['minutes_per_day'],'Daily minutes',15,480);session=integer(x.get('session_minutes',40),'Session minutes',10,90);pause=integer(x.get('break_minutes',5),'Break minutes',0,30)
 start_time=x['daily_start_utc']
 if not isinstance(start_time,str) or not re.fullmatch(r'\d{2}:\d{2}',start_time):raise ValueError('daily_start_utc must be HH:MM')
 if int(start_time[:2])>23 or int(start_time[3:])>59:raise ValueError('Clock requires hours 00–23 and minutes 00–59')
 clock=time.fromisoformat(start_time)
 if clock.hour*60+clock.minute+minutes>1440:raise ValueError('Daily window cannot cross midnight UTC')
 weekdays=x.get('weekdays',[0,1,2,3,4]);
 if not isinstance(weekdays,list) or not weekdays or len(set(weekdays))!=len(weekdays) or any(type(w)!=int or w not in range(7) for w in weekdays):raise ValueError('weekdays: distinct integers Monday=0 to Sunday=6')
 tasks=x['tasks']
 if not isinstance(tasks,list) or len(tasks)>100:raise ValueError('Maximum 100 tasks')
 clean=[];ids=set()
 for t in tasks:
  if not isinstance(t,dict):raise ValueError('Each task must be an object')
  i=t['id'];title=t['title']
  if not isinstance(i,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',i) or i in ids:raise ValueError('Task IDs must be unique safe identifiers')
  if not isinstance(title,str) or not title.strip() or len(title)>160 or any(ord(c)<32 for c in title):raise ValueError('Title requires 1–160 printable characters')
  ids.add(i);clean.append(dict(id=i,title=title.strip(),deadline=day(t['deadline']),minutes=integer(t['minutes'],'Task minutes',5,20000),priority=integer(t.get('priority',2),'Priority',1,3)))
 return dict(start=start,days=days,minutes=minutes,session=session,pause=pause,clock=clock,weekdays=weekdays,tasks=clean)

def plan(data):
 cfg=validate(data);tasks=sorted(cfg['tasks'],key=lambda t:(t['deadline'],t['priority'],t['id']));remaining={t['id']:t['minutes'] for t in tasks};sessions=[]
 for n in range(cfg['days']):
  d=cfg['start']+timedelta(days=n)
  if d.weekday() not in cfg['weekdays']:continue
  cursor=datetime.combine(d,cfg['clock'],tzinfo=timezone.utc);left=cfg['minutes']
  for t in tasks:
   while remaining[t['id']] and t['deadline']>=d and left>0:
    duration=min(cfg['session'],remaining[t['id']],left)
    # Tiny end-of-day fragments under 5m aren't useful, but final task fragments are allowed.
    if duration<5:break
    end=cursor+timedelta(minutes=duration);sessions.append(dict(task_id=t['id'],title=t['title'],start=cursor.isoformat(),end=end.isoformat(),minutes=duration));remaining[t['id']]-=duration;left-=duration;cursor=end
    if left and any(remaining[z['id']] and z['deadline']>=d for z in tasks):
     breaktime=min(cfg['pause'],left);cursor+=timedelta(minutes=breaktime);left-=breaktime
 return dict(timezone='UTC',sessions=sessions,tasks=[dict(id=t['id'],title=t['title'],deadline=t['deadline'].isoformat(),estimated_minutes=t['minutes'],scheduled_minutes=t['minutes']-remaining[t['id']],unscheduled_minutes=remaining[t['id']]) for t in tasks],total_scheduled_minutes=sum(s['minutes'] for s in sessions),total_unscheduled_minutes=sum(remaining.values()))

def escape_ics(s):return s.replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\r','').replace('\n','\\n')
def ics(result):
 lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Raj portfolio//Study Sprint//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH']
 for s in result['sessions']:
  key=s['task_id']+s['start']+s['end'];uid=hashlib.sha256(key.encode()).hexdigest()+'@study-sprint.local'
  ts=lambda value:datetime.fromisoformat(value).strftime('%Y%m%dT%H%M%SZ')
  lines+=['BEGIN:VEVENT','UID:'+uid,'DTSTAMP:'+ts(s['start']),'DTSTART:'+ts(s['start']),'DTEND:'+ts(s['end']),'SUMMARY:'+escape_ics(s['title']),'DESCRIPTION:Study block exported from a local demo; times are UTC.','END:VEVENT']
 lines+=['END:VCALENDAR'];folded=[]
 # RFC5545: fold at <=75 octets without splitting UTF-8 codepoints.
 for line in lines:
  chunk=''
  for ch in line:
   if len((chunk+ch).encode())>75:folded.append(chunk);chunk=' '+ch
   else:chunk+=ch
  folded.append(chunk)
 return '\r\n'.join(folded)+'\r\n'
def page(result):
 e=html.escape;groups={}
 for s in result['sessions']:groups.setdefault(s['start'][:10],[]).append(s)
 days=''
 for d,items in groups.items():
  days+=f'<section><h2>{date.fromisoformat(d).strftime("%a, %d %b")}</h2>'
  for s in items:days+=f'<article><time>{e(s["start"][11:16])}–{e(s["end"][11:16])} UTC</time><b>{e(s["title"])}</b><span>{s["minutes"]} min</span></article>'
  days+='</section>'
 rows=''.join(f'<tr><td>{e(t["title"])}</td><td>{e(t["deadline"])}</td><td>{t["scheduled_minutes"]} / {t["estimated_minutes"]} min</td><td class="warning">{t["unscheduled_minutes"] or "—"}</td></tr>' for t in result['tasks'])
 return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Study Sprint — your plan</title><style>
*{box-sizing:border-box}body{margin:0;background:#f1f0e9;color:#25382f;font:15px/1.5 system-ui,sans-serif}main{max-width:1050px;margin:auto;padding:42px 28px}.brand{font:25px Georgia,serif;letter-spacing:-1px}header{margin:40px 0;display:flex;justify-content:space-between;gap:25px}h1{font:49px/1.1 Georgia,serif;margin:15px 0}.muted{color:#758371;font-size:13px}.stats{border-left:2px solid #c2d0b2;padding-left:22px;align-self:center;white-space:nowrap}.stats b{font:40px Georgia,serif}.stats div{margin-bottom:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}section{background:#fffef8;border:1px solid #d1dccc;border-radius:12px;padding:24px}h2{font:24px Georgia,serif;margin:0 0 20px}article{border-top:1px solid #e0e6d8;padding:13px 0;display:grid;grid-template-columns:1fr auto;gap:4px}time{grid-column:1/-1;font-size:11px;color:#77906c}article b{font-weight:500}article span{font-size:12px;color:#7a8972}.summary{margin-top:30px;overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;border-bottom:1px solid #d8e0d1;padding:12px;min-width:90px}th{font-size:10px;letter-spacing:1px;color:#708568}.warning{color:#9c6535}footer{margin-top:35px;color:#7e8d75;font-size:12px}@media(max-width:620px){header{display:block}h1{font-size:38px}.stats{margin:25px 0}.grid{grid-template-columns:1fr}main{padding:25px 18px}section{padding:20px}}@media print{body{background:white}section{break-inside:avoid}main{padding:0}.grid{gap:12px}}
</style><main><div class="brand">s / study sprint</div><header><div><p class="muted">SMALL BLOCKS. REAL PROGRESS.</p><h1>A little structure.<br>A clearer week.</h1><p class="muted">Your estimates, turned into focused study blocks.<br>Times below are explicitly UTC — not your local timezone.</p></div><div class="stats"><div><b>"""+str(result['total_scheduled_minutes'])+"""</b> min planned</div><div><b>"""+str(result['total_unscheduled_minutes'])+"""</b> min won't fit</div></div></header><div class="grid">"""+(days or '<p>No sessions fit the supplied availability.</p>')+"""</div><section class="summary"><h2>The whole picture</h2><table><thead><tr><th>TASK</th><th>DEADLINE</th><th>PLANNED / ESTIMATED</th><th>MINUTES UNPLACED</th></tr></thead><tbody>"""+rows+"""</tbody></table></section><footer>Synthetic coursework demo · Earliest-deadline greedy schedule, not an optimal plan · Export does not create reminders</footer></main></html>"""
def export(result,path):
 p=Path(path)
 if p.exists() and any(p.iterdir()):raise ValueError('Output directory must be empty or new')
 p.mkdir(parents=True,exist_ok=True);(p/'plan.json').write_text(json.dumps(result,indent=2));(p/'plan.html').write_text(page(result));(p/'study.ics').write_bytes(ics(result).encode())
def main(argv=None):
 ap=argparse.ArgumentParser(description='Capacity-aware study blocks, explicit UTC times');ap.add_argument('input');ap.add_argument('--out',required=True);a=ap.parse_args(argv)
 try:
  p=Path(a.input)
  if p.stat().st_size>1000000:raise ValueError('Input exceeds 1 MB')
  result=plan(json.loads(p.read_text()));export(result,a.out);print(json.dumps({'scheduled_minutes':result['total_scheduled_minutes'],'unscheduled_minutes':result['total_unscheduled_minutes'],'output':a.out}));return 0
 except (OSError,ValueError,KeyError,TypeError) as e:print('Error: '+str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
