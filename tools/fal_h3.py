#!/usr/bin/env python3
"""fal.ai MiniMax H3 lane. Usage:
  fal_h3.py upload <file>                      -> prints public URL (fal storage)
  fal_h3.py i2v --image URL --prompt-file P.md --duration 15 --resolution 2K [--expansion balanced] --out out.mp4
  fal_h3.py t2v --prompt-file P.md --duration 15 --resolution 2K --aspect 9:16 --out out.mp4
Reads FAL_KEY from ~/.config/keys.env. Never call without an approved prompt (stack-router law 3)."""
import argparse, json, os, sys, time, mimetypes, urllib.request

def env():
    p=os.path.expanduser('~/.config/keys.env')
    for l in open(p):
        if '=' in l and not l.startswith('#'):
            k,v=l.strip().split('=',1); os.environ.setdefault(k,v)
    return os.environ['FAL_KEY']

def req(url, data=None, key=None, method=None, ctype='application/json'):
    h={'Authorization':f'Key {key}'}
    if data is not None and ctype=='application/json': data=json.dumps(data).encode()
    if data is not None: h['Content-Type']=ctype
    r=urllib.request.Request(url,data=data,headers=h,method=method or ('POST' if data is not None else 'GET'))
    with urllib.request.urlopen(r,timeout=120) as resp: return json.loads(resp.read() or b'{}')

def upload(key, path):
    ct=mimetypes.guess_type(path)[0] or 'application/octet-stream'
    init=req('https://rest.alpha.fal.ai/storage/upload/initiate',{'content_type':ct,'file_name':os.path.basename(path)},key)
    with open(path,'rb') as f: body=f.read()
    r=urllib.request.Request(init['upload_url'],data=body,headers={'Content-Type':ct},method='PUT')
    urllib.request.urlopen(r,timeout=300).read()
    return init['file_url']

def run(key, endpoint, payload, out):
    sub=req(f'https://queue.fal.run/{endpoint}',payload,key)
    rid=sub['request_id']; status_url=sub['status_url']; resp_url=sub['response_url']
    print('request_id',rid,file=sys.stderr)
    while True:
        s=req(status_url,key=key)
        st=s.get('status'); print(st, s.get('queue_position',''),file=sys.stderr)
        if st=='COMPLETED': break
        if st in ('FAILED','ERROR'): print(json.dumps(s,indent=1)); sys.exit(1)
        time.sleep(8)
    res=req(resp_url,key=key)
    url=res.get('video',{}).get('url')
    if url and out:
        urllib.request.urlretrieve(url,out); print('saved',out)
    print(json.dumps({k:v for k,v in res.items() if k!='video'} | {'video_url':url},indent=1))

if __name__=='__main__':
    a=argparse.ArgumentParser(); sp=a.add_subparsers(dest='cmd',required=True)
    u=sp.add_parser('upload'); u.add_argument('file')
    for name in ('i2v','t2v'):
        p=sp.add_parser(name); p.add_argument('--prompt-file',required=True); p.add_argument('--duration',type=int,default=5)
        p.add_argument('--resolution',default='2K',choices=['480P','768P','2K','4K']); p.add_argument('--expansion',default='balanced')
        p.add_argument('--out',default='out.mp4'); p.add_argument('--image'); p.add_argument('--end-image'); p.add_argument('--aspect',default='9:16'); p.add_argument('--seed',type=int)
    args=a.parse_args(); key=env()
    if args.cmd=='upload': print(upload(key,args.file)); sys.exit()
    prompt=open(args.prompt_file).read().strip()
    payload={'prompt':prompt,'duration':args.duration,'resolution':args.resolution,'prompt_expansion_mode':args.expansion}
    if args.seed is not None: payload['seed']=args.seed
    if args.cmd=='i2v':
        payload['image_url']=args.image
        if args.end_image: payload['end_image_url']=args.end_image
        run(key,'minimax/h3/image-to-video',payload,args.out)
    else:
        payload['aspect_ratio']=args.aspect
        run(key,'minimax/h3/text-to-video',payload,args.out)
