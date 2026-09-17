#!/usr/bin/env python3
"""sunoapi.org lane (Suno). Usage:
  suno.py credits
  suno.py gen --style "warm tabla lo-fi, chimes" --title "Red Book" --duration 15 [--instrumental] [--prompt LYRICS] [--model V6] --out bgm.mp3
Reads SUNOAPI_KEY from ~/.config/keys.env. callBackUrl is required by the API; we pass a dummy and poll record-info instead."""
import argparse, json, os, sys, time, urllib.request
BASE='https://api.sunoapi.org/api/v1'
def env():
    for l in open(os.path.expanduser('~/.config/keys.env')):
        if '=' in l: k,v=l.strip().split('=',1); os.environ.setdefault(k,v)
    return os.environ['SUNOAPI_KEY']
def req(url,key,data=None):
    h={'Authorization':f'Bearer {key}','Content-Type':'application/json','User-Agent':'curl/8.0','Accept':'*/*'}
    r=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,headers=h)
    with urllib.request.urlopen(r,timeout=120) as resp: return json.loads(resp.read())
if __name__=='__main__':
    a=argparse.ArgumentParser(); sp=a.add_subparsers(dest='cmd',required=True)
    sp.add_parser('credits')
    pl=sp.add_parser('poll'); pl.add_argument('task'); pl.add_argument('--out',default='bgm.mp3')
    g=sp.add_parser('gen'); g.add_argument('--style',required=True); g.add_argument('--title',required=True); g.add_argument('--duration',type=int)
    g.add_argument('--instrumental',action='store_true'); g.add_argument('--prompt',default=''); g.add_argument('--model',default='V6'); g.add_argument('--negative',default=''); g.add_argument('--out',default='bgm.mp3')
    args=a.parse_args(); key=env()
    if args.cmd=='credits': print(req(f'{BASE}/generate/credit',key)); sys.exit()
    if args.cmd=='poll': tid=args.task
    else:
      body={'customMode':True,'instrumental':args.instrumental,'model':args.model,'style':args.style,'title':args.title,'callBackUrl':'https://example.com/suno-callback'}
      if not args.instrumental: body['prompt']=args.prompt
      if args.duration: body['duration']=args.duration
      if args.negative: body['negativeTags']=args.negative
      r=req(f'{BASE}/generate',key,body); print(r,file=sys.stderr); tid=r['data']['taskId']
    while True:
        s=req(f'{BASE}/generate/record-info?taskId={tid}',key); d=s.get('data') or {}
        st=d.get('status'); print(st,file=sys.stderr)
        if st in ('SUCCESS','FIRST_SUCCESS','TEXT_SUCCESS') and (d.get('response') or {}).get('sunoData'):
            tracks=d['response']['sunoData']
            if st=='SUCCESS' or all(t.get('audioUrl') for t in tracks):
                for i,t in enumerate(tracks):
                    out=args.out if i==0 else args.out.replace('.mp3',f'_{i}.mp3')
                    urllib.request.urlretrieve(t['audioUrl'],out); print('saved',out,t.get('duration'))
                break
        if st and 'FAIL' in st: print(json.dumps(s,indent=1)); sys.exit(1)
        time.sleep(10)
