#!/usr/bin/env python3
"""Executor's generation dispatcher — one entry point per modality, keyed by capabilities.json lanes.
  gen.py video --proj P --item sg_01 --prompt-file docs/x.txt --duration 15 --ratio 9:16 [--image assets/card.jpg] [--end-image ...] [--resolution 2K] [--lane fal_h3]
  gen.py music --proj P --item bgm --style "..." --title "..." --duration 15 [--lyrics-file f] [--lane suno]
  gen.py image --proj P --item card --prompt-file docs/card.txt --ratio 9:16 [--lane higgsfield_web|fal_nano_banana_pro|pollo]
  gen.py speech --proj P --item vo_01 --text-file t.txt --voice "Arjun (en)" [--lane fal_speech]
Writes outputs to projects/<P>/renders/<item>.<ext> and appends a results.json entry (plan.py state --results).
Reads keys from ~/.config/keys.env (FAL_KEY, SUNOAPI_KEY, REPLICATE_API_TOKEN, PROTOFACE_API_KEY, VGENV_API_KEY).
  video lanes: fal_h3 | fal_h3_turbo | protoface_h3 (multi-ref, --refs ≤9, 3000 cr/mo plan) | vgenv_h3 (--tier fast|quality, --refs ≤9 XOR first/last frame)"""
import argparse, json, os, sys, subprocess, time, urllib.request, mimetypes
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.environ.get('STUDIO_PROJECTS', os.path.join(os.path.dirname(HERE),'projects'))
CAP = json.load(open(os.path.join(HERE,'capabilities.json')))
def env():
    p=os.path.expanduser('~/.config/keys.env')
    if os.path.exists(p):
        for l in open(p):
            if '=' in l and not l.startswith('#'): k,v=l.strip().split('=',1); os.environ.setdefault(k,v)
def curl_json(url, key_header, data=None, method=None):
    # SECURITY: the auth header used to sit in argv, readable via `ps` by any local process.
    # curl -K reads it from a 0600 file that is removed when this process exits.
    import tempfile, atexit
    global _KCFG
    try: _KCFG
    except NameError: _KCFG = {}
    if key_header not in _KCFG:
        fd, cfg = tempfile.mkstemp(prefix='.gen-', suffix='.conf'); os.close(fd); os.chmod(cfg, 0o600)
        with open(cfg, 'w') as f:
            f.write(f'header = "{key_header}"\nheader = "Content-Type: application/json"\n')
        atexit.register(lambda c=cfg: os.path.exists(c) and os.remove(c))
        _KCFG[key_header] = cfg
    cmd=['curl','-s','-m','120',url,'-K',_KCFG[key_header]]
    tmp=None
    if data is not None:
        body=json.dumps(data)
        if len(body)>60000:  # data-URI refs — keep off the argv
            import tempfile; tmp=tempfile.NamedTemporaryFile('w',suffix='.json',delete=False); tmp.write(body); tmp.close(); cmd += ['-X', method or 'POST','--data-binary',f'@{tmp.name}']
        else: cmd += ['-X', method or 'POST','-d',body]
    try:
        for attempt in range(4):
            r=subprocess.run(cmd,capture_output=True)
            if r.returncode==0 and r.stdout.strip():
                try: return json.loads(r.stdout)
                except json.JSONDecodeError: pass
            time.sleep(3*(attempt+1))
        raise SystemExit(f'curl to {url.split("?")[0]} failed after 4 attempts (exit {r.returncode}); key not shown')
    finally:
        if tmp: os.unlink(tmp.name)
def record(proj, item, path, modality, model, summary):
    rp=os.path.join(ROOT,proj,'renders','results.json'); res=json.load(open(rp)) if os.path.exists(rp) else {'results':[],'failed':[]}
    res['results']=[r for r in res['results'] if r['id']!=item]+[{'id':item,'path':os.path.relpath(path,os.path.join(ROOT,proj)),'modality':modality,'model':model,'summary':summary}]
    json.dump(res,open(rp,'w'),indent=1); print(json.dumps(res['results'][-1]))
def fal_upload(path):
    key=os.environ['FAL_KEY']; ct=mimetypes.guess_type(path)[0] or 'application/octet-stream'
    init=curl_json('https://rest.alpha.fal.ai/storage/upload/initiate',f'Authorization: Key {key}',{'content_type':ct,'file_name':os.path.basename(path)})
    subprocess.run(['curl','-s','-m','300','-X','PUT',init['upload_url'],'-H',f'Content-Type: {ct}','--data-binary',f'@{path}'],check=True); return init['file_url']
def fal_run(endpoint, payload, out, key_field='video'):
    key=os.environ['FAL_KEY']; sub=curl_json(f'https://queue.fal.run/{endpoint}',f'Authorization: Key {key}',payload)
    if 'request_id' not in sub: raise SystemExit(json.dumps(sub))
    json.dump(sub,open(out+'.req.json','w'),indent=1)  # request_id/status_url/response_url — recoverable if download fails
    while True:
        s=curl_json(sub['status_url'],f'Authorization: Key {key}'); st=s.get('status'); print(st,s.get('queue_position',''),file=sys.stderr)
        if st=='COMPLETED': break
        if st in ('FAILED','ERROR'): raise SystemExit(json.dumps(s))
        time.sleep(8)
    res=curl_json(sub['response_url'],f'Authorization: Key {key}'); obj=res.get(key_field) or res.get('images') or res.get('audio') or {}
    if isinstance(obj,list): obj=obj[0] if obj else {}
    url=obj.get('url')
    if not url: json.dump(res,open(out+'.resp.json','w'),indent=1); raise SystemExit('no url in response; saved '+out+'.resp.json')
    subprocess.run(['curl','-s','-L','-m','600','-o',out,url],check=True)
    if not os.path.exists(out) or os.path.getsize(out)==0: raise SystemExit('download failed: '+out)
    return res
def assert_lane(modality, lane):
    """Nothing used to check this. capabilities.json still listed disabled vendors as the default,
    so a call without an explicit --lane routed straight at a banned paid lane."""
    e = (CAP['lanes'].get(modality) or {}).get(lane)
    if not isinstance(e, dict):
        raise SystemExit(f'unknown {modality} lane {lane!r} — see tools/capabilities.json')
    if e.get('enabled') is False or e.get('disabled') is True or e.get('status') == 'FORBIDDEN':
        raise SystemExit(f'lane {lane!r} is DISABLED ({e.get("note") or e.get("role") or "see capabilities.json"}). '
                         f'Live {modality} default is {CAP["lanes"][modality].get("default")!r}.')
    return e

def video(a):
    lane=a.lane or CAP['lanes']['video']['default']; assert_lane('video',lane); prompt=open(a.prompt_file).read().strip(); out=os.path.join(ROOT,a.proj,'renders',f'{a.item}.mp4'); os.makedirs(os.path.dirname(out),exist_ok=True)
    if lane in ('fal_h3','fal_h3_turbo'):
        L=CAP['lanes']['video'][lane]; res=a.resolution or ('768P' if lane=='fal_h3_turbo' else '2K')
        if res not in L['resolutions']: raise SystemExit(f'{lane} supports {L["resolutions"]}, not {res}')
        payload={'prompt':prompt,'duration':int(a.duration),'resolution':res,'prompt_expansion_mode':a.expansion}
        if a.image: payload['image_url']=fal_upload(os.path.join(ROOT,a.proj,a.image)) if not a.image.startswith('http') else a.image; ep=L['endpoints']['i2v']
        else: payload['aspect_ratio']=a.ratio; ep=L['endpoints']['t2v']
        a.resolution=res
        if a.end_image: payload['end_image_url']=fal_upload(os.path.join(ROOT,a.proj,a.end_image))
        res=fal_run(ep,payload,out); json.dump(res,open(out+'.json','w'),indent=1)
        record(a.proj,a.item,out,'video',f'fal/{ep}',f'{a.duration}s {a.resolution} {a.ratio}')
    elif lane=='protoface_h3':
        L=CAP['lanes']['video'][lane]; q=(a.resolution or '768p').lower().replace('1440p','2k'); assert q in L['qualities'], f'protoface quality must be one of {list(L["qualities"])}'
        key=os.environ['PROTOFACE_API_KEY']; H=f'Authorization: Bearer {key}'
        payload={'operation':'video.general','prompt':prompt,'quality':q,'duration_seconds':int(a.duration),'aspect_ratio':a.ratio,'generate_audio':True,'enhance_prompt':False}
        refs=[data_uri(os.path.join(ROOT,a.proj,r)) for r in (a.refs or [])]
        if refs: payload['reference']=refs
        if a.image: payload['first_frame']=data_uri(os.path.join(ROOT,a.proj,a.image))
        if a.end_image: payload['last_frame']=data_uri(os.path.join(ROOT,a.proj,a.end_image))
        est=L['qualities'][q]['credits_per_s']*int(a.duration)+max(0,len(refs)-L['qualities'][q]['refs_included'])*L['qualities'][q]['ref_extra_credits']
        print(f'protoface estimate ≈ {est:.1f} credits (≈ ${est/100:.2f}; included in Studio Unlimited 3000/mo)',file=sys.stderr)
        if os.path.exists(out+'.req.json') and not os.path.exists(out):
            sub=json.load(open(out+'.req.json')); print('resuming run',sub.get('id'),file=sys.stderr)
        else:
            sub=None
            for attempt in range(3):
                sub=curl_json(f'https://api.protoface.com/v1/run/{L["model"]}',H,payload)
                if 'id' in sub: break
                print('submit error, retrying:',json.dumps(sub)[:200],file=sys.stderr); time.sleep(10*(attempt+1))
            if 'id' not in sub: raise SystemExit(json.dumps(sub))
            json.dump({k:v for k,v in sub.items()},open(out+'.req.json','w'),indent=1)
        while True:
            s=curl_json(f'https://api.protoface.com/v1/runs/{sub["id"]}',H); st=s.get('status'); print(st,s.get('progress',''),file=sys.stderr)
            if st=='completed': break
            if st in ('failed','cancelled'): raise SystemExit(json.dumps(s)[:2000])
            time.sleep(8)
        url=(s.get('video') or {}).get('url')
        if not url: json.dump(s,open(out+'.resp.json','w'),indent=1); raise SystemExit('no video url; saved '+out+'.resp.json')
        subprocess.run(['curl','-s','-L','-m','600','-o',out,url],check=True); json.dump(s,open(out+'.json','w'),indent=1)
        record(a.proj,a.item,out,'video',f'protoface/{L["model"]}',f'{a.duration}s {q} {a.ratio} refs={len(refs)} credits={s.get("credits",{}).get("charged")}')
    elif lane=='vgenv_h3':
        L=CAP['lanes']['video'][lane]; res=(a.resolution or '768p').lower(); tier=a.tier or 'fast'; assert res in L['resolutions'] and tier in L['tiers']
        key=os.environ['VGENV_API_KEY']; H=f'Authorization: Bearer {key}'
        payload={'model':'minimax/h3','tier':tier,'prompt':prompt,'duration':int(a.duration),'resolution':res,'aspect_ratio':a.ratio,'prompt_optimization':{'mode':'raw'}}
        refs=[{'type':'image_url','image_url':{'url':data_uri(os.path.join(ROOT,a.proj,r))}} for r in (a.refs or [])]
        if refs and (a.image or a.end_image): raise SystemExit('vgenv: reference_images cannot be combined with frame_images — choose refs OR first/last frame')
        if refs: payload['reference_images']=refs
        fr=[]
        if a.image: fr.append({'type':'image_url','image_url':{'url':data_uri(os.path.join(ROOT,a.proj,a.image))},'frame_type':'first_frame'})
        if a.end_image: fr.append({'type':'image_url','image_url':{'url':data_uri(os.path.join(ROOT,a.proj,a.end_image))},'frame_type':'last_frame'})
        if fr: payload['frame_images']=fr
        print(f'vgenv estimate ≈ ${L["price_usd_per_s"][tier][res]*int(a.duration):.3f}',file=sys.stderr)
        sub=curl_json('https://api.vgenv.com/v1/videos',H,payload)
        if 'id' not in sub: raise SystemExit(json.dumps(sub))
        json.dump(sub,open(out+'.req.json','w'),indent=1)
        while True:
            s=curl_json(f'https://api.vgenv.com/v1/videos/{sub["id"]}',H); st=s.get('status'); print(st,s.get('progress',''),s.get('queue_position',''),file=sys.stderr)
            if st=='succeeded': break
            if st in ('failed','cancelled'): raise SystemExit(json.dumps(s)[:2000])
            time.sleep(10)
        url=(s.get('output') or {}).get('url')
        if not url: json.dump(s,open(out+'.resp.json','w'),indent=1); raise SystemExit('no output url; saved '+out+'.resp.json')
        subprocess.run(['curl','-s','-L','-m','600','-o',out,url],check=True); json.dump(s,open(out+'.json','w'),indent=1)
        pr=s.get('price') or {}; record(a.proj,a.item,out,'video','vgenv/minimax-h3',f'{a.duration}s {res} {tier} {a.ratio} refs={len(refs)} price={pr.get("currency")} {pr.get("amount_micros",0)/1e6}')
    else: raise SystemExit(f'lane {lane} not implemented in gen.py — see capabilities.json notes')
def data_uri(path):
    import base64; ct=mimetypes.guess_type(path)[0] or 'image/jpeg'
    if os.path.getsize(path)>5*1024*1024: raise SystemExit(f'{path} > 5 MiB — downscale first (post.py) ')
    return f'data:{ct};base64,'+base64.b64encode(open(path,'rb').read()).decode()
def music(a):
    lane=a.lane or CAP['lanes']['music']['default']; out=os.path.join(ROOT,a.proj,'renders',f'{a.item}.mp3'); os.makedirs(os.path.dirname(out),exist_ok=True)
    key=os.environ['SUNOAPI_KEY']; body={'customMode':True,'instrumental':not a.lyrics_file,'model':'V6','style':a.style,'title':a.title,'callBackUrl':'https://example.com/cb'}
    if a.lyrics_file: body['prompt']=open(a.lyrics_file).read()
    if a.duration: body['duration']=int(a.duration)
    r=curl_json('https://api.sunoapi.org/api/v1/generate',f'Authorization: Bearer {key}',body); tid=r['data']['taskId']
    while True:
        s=curl_json(f'https://api.sunoapi.org/api/v1/generate/record-info?taskId={tid}',f'Authorization: Bearer {key}'); d=s.get('data') or {}; st=d.get('status'); print(st,file=sys.stderr)
        if st=='SUCCESS':
            tr=d['response']['sunoData']; subprocess.run(['curl','-s','-L','-o',out,tr[0]['audioUrl']],check=True)
            if len(tr)>1: subprocess.run(['curl','-s','-L','-o',out.replace('.mp3','_alt.mp3'),tr[1]['audioUrl']],check=True)
            record(a.proj,a.item,out,'audio.music','sunoapi/V6',f'{tr[0].get("duration")}s {a.style[:40]}'); break
        if st and 'FAIL' in st: raise SystemExit(json.dumps(s))
        time.sleep(10)
def image(a):
    lane=a.lane or CAP['lanes']['image']['default']
    # This used to be one line: `if <forbidden>: raise ...; prompt=...; out=...; makedirs(...)`.
    # Python put ALL of it in the if-body, so on the allowed path prompt/out were never bound and
    # the next line raised NameError. gen.py image was dead for every lane.
    if lane.startswith(('fal','pollo')):
        raise SystemExit(f'lane {lane} is not an image lane here — fal/pollo are video-only.')
    assert_lane('image', lane)
    prompt=open(a.prompt_file).read().strip()
    out=os.path.join(ROOT,a.proj,'renders',f'{a.item}.png')
    os.makedirs(os.path.dirname(out),exist_ok=True)
    if lane=='higgsfield_web':
        print(json.dumps({'action':'higgsfield_web','url':'https://higgsfield.ai/ai/image?model=seedream_v5_lite','prompt':prompt,'ratio':a.ratio,'steps':['open URL in Chrome extension','replace prompt','set ratio','ensure Unlimited toggle ON','Generate','open tile → Download','stage from Downloads → save as '+out]})); return
    if lane=='fal_nano_banana_pro':
        if a.refs:
            urls=[fal_upload(os.path.join(ROOT,a.proj,r)) if not r.startswith('http') else r for r in a.refs]
            res=fal_run('fal-ai/nano-banana-pro/edit',{'prompt':prompt,'image_urls':urls,'aspect_ratio':a.ratio,'resolution':a.resolution or '2K','output_format':'png'},out,key_field='images'); record(a.proj,a.item,out,'image','fal/nano-banana-pro/edit',f'{a.ratio} refs={len(urls)}'); return
        res=fal_run('fal-ai/nano-banana-pro',{'prompt':prompt,'aspect_ratio':a.ratio,'resolution':a.resolution or '2K'},out,key_field='images'); record(a.proj,a.item,out,'image','fal/nano-banana-pro',a.ratio); return
    raise SystemExit(f'lane {lane} not implemented')
def speech(a):
    text=open(a.text_file).read().strip(); out=os.path.join(ROOT,a.proj,'renders',f'{a.item}.mp3'); os.makedirs(os.path.dirname(out),exist_ok=True)
    res=fal_run('fal-ai/minimax/speech-2.8-hd',{'text':text,'voice_setting':{'voice_id':a.voice}},out,key_field='audio'); record(a.proj,a.item,out,'audio.tts','fal/minimax-speech-2.8-hd',a.voice)
if __name__=='__main__':
    env(); p=argparse.ArgumentParser(); sp=p.add_subparsers(dest='cmd',required=True)
    for c in ('video','music','image','speech'):
        x=sp.add_parser(c); x.add_argument('--proj',required=True); x.add_argument('--item',required=True); x.add_argument('--lane')
        if c=='video': x.add_argument('--prompt-file',required=True); x.add_argument('--duration',default=5); x.add_argument('--ratio',default='9:16'); x.add_argument('--image'); x.add_argument('--end-image'); x.add_argument('--resolution'); x.add_argument('--expansion',default='balanced'); x.add_argument('--refs',nargs='*',default=[],help='identity refs (character sheets) — protoface_h3 ≤9 / vgenv_h3 ≤9 / topview ≤9'); x.add_argument('--tier',help='vgenv: fast|standard|quality')
        if c=='music': x.add_argument('--style',required=True); x.add_argument('--title',required=True); x.add_argument('--duration'); x.add_argument('--lyrics-file')
        if c=='image': x.add_argument('--prompt-file',required=True); x.add_argument('--ratio',default='9:16'); x.add_argument('--refs',nargs='*',default=[]); x.add_argument('--resolution')
        if c=='speech': x.add_argument('--text-file',required=True); x.add_argument('--voice',default='Wise_Woman')
    a=p.parse_args(); globals()[a.cmd](a)
