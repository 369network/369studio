#!/usr/bin/env python3
"""PC: python bench_assemble.py <test> [ar 9:16|16:9] [--override id=path ...]  — assembles projects/bench/final/<test>.mp4 from renders/vghigh_<test>_<id>.mp4 (or overrides)."""
import json,subprocess,os,sys,time
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','projects','bench'))
t=sys.argv[1]; ar=sys.argv[2] if len(sys.argv)>2 and ':' in sys.argv[2] else '9:16'
ov={a.split('=')[0]:a.split('=')[1] for a in sys.argv if '=' in a and not a.startswith('--')}
W,H=(1080,1920) if ar=='9:16' else (1920,1080)
S=json.load(open(f'docs/{t}/shots.json',encoding='utf-8'))
subs={}
if os.path.exists(f'docs/{t}/subs.txt'):
    for l in open(f'docs/{t}/subs.txt',encoding='utf-8'):
        if '|' in l: a,b=l.split('|',1); subs[a.strip()]=b.strip()
os.makedirs(f'renders/norm_{t}',exist_ok=True); lst=[]; srt=[]; tt=0; n=1
def ts(x): h=int(x//3600); m=int(x%3600//60); s=x%60; return f"{h:02d}:{m:02d}:{int(s):02d},{int((s%1)*1000):03d}"
for m in S:
    sid=m['id']; short=sid.replace(t+'_','')
    src=ov.get(short) or ov.get(sid) or f"renders/vghigh_{sid.replace('-','_')}.mp4"
    if not os.path.exists(src): src=f"renders/c2_{sid.replace('-','_')}.mp4"
    if not os.path.exists(src): print('MISSING',sid); continue
    out=f'renders/norm_{t}/{sid}.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-i',src,'-vf',f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=25,format=yuv420p','-c:v','libx264','-crf','18','-preset','veryfast','-c:a','aac','-b:a','160k','-ar','48000','-ac','2',out],check=True)
    d=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',out],capture_output=True,text=True).stdout)
    line=subs.get(short) or subs.get(sid) or (m.get('dlg') if isinstance(m.get('dlg'),str) else None)
    if line: srt.append(f"{n}\n{ts(tt+0.2)} --> {ts(tt+d-0.2)}\n{line}\n"); n+=1
    tt+=d; lst.append(os.path.abspath(out))
open(f'renders/norm_{t}/list.txt','w').write(''.join(f"file '{p}'\n" for p in lst))
subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',f'renders/norm_{t}/list.txt','-c','copy',f'renders/{t}_concat.mp4'],check=True)
vf=[]
if srt:
    open(f'docs/{t}/subs.srt','w',encoding='utf-8').write('\n'.join(srt))
    vf=['-vf',f"subtitles=docs/{t}/subs.srt:force_style='FontName=Poppins,FontSize={13 if ar=='9:16' else 11},BorderStyle=4,BackColour=&H80000000,Outline=0,Shadow=0,MarginV=48,WrapStyle=2,Alignment=2'"]
os.makedirs('final',exist_ok=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',f'renders/{t}_concat.mp4']+vf+['-af','loudnorm=I=-16:TP=-1.5:LRA=11','-c:v','libx264','-crf','18','-preset','veryfast','-c:a','aac','-b:a','192k',f'final/{t}.mp4'],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',f'final/{t}.mp4','-vf','scale=720:-2' if ar=='16:9' else 'scale=720:1280','-c:v','libx264','-crf','24','-preset','veryfast','-c:a','aac','-b:a','128k',f'final/{t}_720p.mp4'])
print('DONE',t,round(tt,1),'s')
