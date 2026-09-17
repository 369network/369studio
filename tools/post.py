#!/usr/bin/env python3
"""Deterministic post — replaces hub_ffmpeg / merge_videos / hub_subtitle_format / timeline tools.
  post.py concat   --inputs a.mp4 b.mp4 ... --out final.mp4 [--scale 1080x1920]
  post.py mix      --video v.mp4 --bgm bgm.mp3 --out o.mp4 [--gain 0.35] [--fade 1.5] [--keep-native 1]
  post.py subs     --video v.mp4 --srt s.srt --out o.mp4 [--ratio 9:16] [--preset social_safe]
  post.py cuts     --video v.mp4                       # scene-cut timestamps (for text patches / QC)
  post.py tile     --video v.mp4 --out sheet.jpg [--fps 1] [--cols 5]   # keyframe contact sheet for QC (Read it)
  post.py textfix  --video v.mp4 --out o.mp4 --region x,y,w,h --from T0 --to T1 --lines "43-day|remedy|tracker" --x X --y Y [--size 150] [--font PATH]
  post.py transcribe --media m.mp4 --out s.srt        # faster-whisper small int8
  post.py loudnorm --video v.mp4 --out o.mp4
  post.py reframe  --video v.mp4 --out o.mp4 --ratio 16:9   # center crop reframe
"""
import argparse, subprocess, json, os, sys, re
FONT = '/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf'
def run(cmd): print(' '.join(cmd), file=sys.stderr); subprocess.run(cmd, check=True)
def probe(v):
    j = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=width,height,codec_type:format=duration','-of','json',v]))
    vs = next(s for s in j['streams'] if s['codec_type']=='video'); return int(vs['width']), int(vs['height']), float(j['format']['duration'])
LOUD = 'loudnorm=I=-16:TP=-1.5:LRA=11'
def _same_streams(paths):
    sig=lambda f: subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','stream=codec_name,pix_fmt,r_frame_rate,time_base,width,height','-of','csv=p=0',f])
    return len({sig(f) for f in paths})==1
def concat(a):
    if not _same_streams(a.inputs):
        n=len(a.inputs); fc=''.join(f'[{i}:v][{i}:a]' for i in range(n))+f'concat=n={n}:v=1:a=1[v][a]'
        cmd=['ffmpeg','-v','error','-y']+sum([['-i',f] for f in a.inputs],[])+['-filter_complex',fc,'-map','[v]','-map','[a]','-c:v','libx264','-crf','16','-preset','fast','-c:a','aac','-b:a','192k','-movflags','+faststart',a.out]; run(cmd); return
    lst = os.path.abspath(a.out) + '.txt'
    open(lst,'w').write(''.join(f"file '{os.path.abspath(i)}'\n" for i in a.inputs))
    vf = f'scale={a.scale.replace("x",":")}:force_original_aspect_ratio=decrease,pad={a.scale.replace("x",":")}:(ow-iw)/2:(oh-ih)/2' if a.scale else None
    cmd = ['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',lst]
    if vf: cmd += ['-vf', vf, '-c:v','libx264','-crf','18','-preset','medium','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k']
    else: cmd += ['-c','copy']
    run(cmd + ['-movflags','+faststart', a.out]); os.remove(lst)
def mix(a):
    _,_,d = probe(a.video)
    fc = f"[1:a]atrim=0:{d},afade=t=out:st={max(0,d-a.fade)}:d={a.fade},volume={a.gain}[bgm];" + (f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0,{LOUD}[a]" if a.keep_native else f"[bgm]{LOUD}[a]")
    run(['ffmpeg','-v','error','-y','-i',a.video,'-i',a.bgm,'-filter_complex',fc,'-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',a.out])
def subs(a):
    w,h,_ = probe(a.video); ratio = a.ratio or ('9:16' if h>w else '16:9')
    mv = int(h*0.25) if ratio=='9:16' else int(h*0.12)   # safe area bottom 1/4 for vertical
    fs = 18 if ratio=='9:16' else 16
    style = f"FontName=Poppins,FontSize={fs},PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV={mv//20},MarginL={int(w*0.07)//20},MarginR={int(w*0.07)//20}"
    run(['ffmpeg','-v','error','-y','-i',a.video,'-vf',f"subtitles={os.path.abspath(a.srt)}:force_style='{style}'",'-c:v','libx264','-crf','18','-preset','medium','-c:a','copy',a.out])
def cuts(a):
    o = subprocess.run(['ffmpeg','-v','info','-y','-i',a.video,'-vf',f"select='gt(scene,{a.thresh})',showinfo",'-vsync','vfr','-f','null','-'],capture_output=True,text=True).stderr
    print(json.dumps([float(t) for t in re.findall(r'pts_time:([0-9.]+)', o)]))
def tile(a):
    run(['ffmpeg','-v','error','-y','-i',a.video,'-vf',f'fps={a.fps},scale=270:-1,tile={a.cols}x{a.rows}',a.out])
def textfix(a):
    x,y,w,h = a.region.split(','); lines = a.lines.split('|'); en = f"enable='between(t,{a.t0},{a.t1})'"
    alpha = f"alpha='if(lt(t,{a.t0}),0,if(lt(t,{a.t0}+0.5),(t-{a.t0})/0.5,1))'"
    vf = f"delogo=x={x}:y={y}:w={w}:h={h}:{en}"
    for i,l in enumerate(lines): vf += f",drawtext=fontfile={a.font}:text='{l}':fontcolor={a.color}:fontsize={a.size}:x={a.x}:y={a.y+i*int(a.size*1.17)}:{alpha}:{en}"
    run(['ffmpeg','-v','error','-y','-i',a.video,'-vf',vf,'-c:v','libx264','-crf','18','-preset','medium','-pix_fmt','yuv420p','-c:a','copy',a.out])
def transcribe(a):
    from faster_whisper import WhisperModel
    m = WhisperModel('small',device='cpu',compute_type='int8'); segs,_ = m.transcribe(a.media)
    def ts(t): h=int(t//3600); mm=int(t%3600//60); s=t%60; return f"{h:02d}:{mm:02d}:{s:06.3f}".replace('.',',')
    with open(a.out,'w') as f:
        for i,s in enumerate(segs,1): f.write(f"{i}\n{ts(s.start)} --> {ts(s.end)}\n{s.text.strip()}\n\n")
    print(a.out)
def loudnorm(a): run(['ffmpeg','-v','error','-y','-i',a.video,'-af',LOUD,'-c:v','copy','-c:a','aac','-b:a','192k',a.out])
def reframe(a):
    w,h,_ = probe(a.video); rw,rh = map(int,a.ratio.split(':'))
    if w/h > rw/rh: nw=int(h*rw/rh); vf=f'crop={nw}:{h}:(iw-{nw})/2:0'
    else: nh=int(w*rh/rw); vf=f'crop={w}:{nh}:0:(ih-{nh})/2'
    run(['ffmpeg','-v','error','-y','-i',a.video,'-vf',vf,'-c:v','libx264','-crf','18','-c:a','copy',a.out])
if __name__=='__main__':
    p=argparse.ArgumentParser(); sp=p.add_subparsers(dest='cmd',required=True)
    x=sp.add_parser('concat'); x.add_argument('--inputs',nargs='+',required=True); x.add_argument('--out',required=True); x.add_argument('--scale')
    x=sp.add_parser('mix'); x.add_argument('--video',required=True); x.add_argument('--bgm',required=True); x.add_argument('--out',required=True); x.add_argument('--gain',type=float,default=0.35); x.add_argument('--fade',type=float,default=1.5); x.add_argument('--keep-native',type=int,default=1)
    x=sp.add_parser('subs'); x.add_argument('--video',required=True); x.add_argument('--srt',required=True); x.add_argument('--out',required=True); x.add_argument('--ratio'); x.add_argument('--preset',default='social_safe')
    x=sp.add_parser('cuts'); x.add_argument('--video',required=True); x.add_argument('--thresh',type=float,default=0.15)
    x=sp.add_parser('tile'); x.add_argument('--video',required=True); x.add_argument('--out',required=True); x.add_argument('--fps',type=float,default=1); x.add_argument('--cols',type=int,default=5); x.add_argument('--rows',type=int,default=3)
    x=sp.add_parser('textfix'); x.add_argument('--video',required=True); x.add_argument('--out',required=True); x.add_argument('--region',required=True); x.add_argument('--from',dest='t0',type=float,required=True); x.add_argument('--to',dest='t1',type=float,required=True); x.add_argument('--lines',required=True); x.add_argument('--x',type=int,required=True); x.add_argument('--y',type=int,required=True); x.add_argument('--size',type=int,default=150); x.add_argument('--font',default=FONT); x.add_argument('--color',default='white')
    x=sp.add_parser('transcribe'); x.add_argument('--media',required=True); x.add_argument('--out',required=True)
    x=sp.add_parser('loudnorm'); x.add_argument('--video',required=True); x.add_argument('--out',required=True)
    x=sp.add_parser('reframe'); x.add_argument('--video',required=True); x.add_argument('--out',required=True); x.add_argument('--ratio',required=True)
    a=p.parse_args(); globals()[a.cmd](a)
