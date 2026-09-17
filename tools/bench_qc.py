#!/usr/bin/env python3
"""PC: python bench_qc.py <test>  — 1 fps tiles for every vghigh_<test>_* clip + contact sheet renders/qc/<test>_sheet.jpg"""
import subprocess,os,sys,glob
from PIL import Image, ImageDraw
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','projects','bench'))
t=sys.argv[1]; os.makedirs('renders/qc',exist_ok=True); rows=[]
for f in sorted(set(glob.glob(f'renders/vg*_{t}_*.mp4')+glob.glob(f'renders/c2_{t}_*.mp4'))):
    if os.path.exists(f'renders/qc/{os.path.basename(f)}.jpg'): 
        rows.append((f,f'renders/qc/{os.path.basename(f)}.jpg')); continue
    subprocess.run(['ffmpeg','-v','error','-y','-i',f,'-vf','fps=1,scale=220:-1,tile=8x1','-frames:v','1',f'renders/qc/{os.path.basename(f)}.jpg'])
    rows.append((f,f'renders/qc/{os.path.basename(f)}.jpg'))
ims=[]
for f,p in rows:
    if not os.path.exists(p): continue
    i=Image.open(p).convert('RGB'); ImageDraw.Draw(i).text((6,6),os.path.basename(f),fill='yellow'); ims.append(i)
if ims:
    s=Image.new('RGB',(max(i.width for i in ims),sum(i.height+6 for i in ims)),'white'); y=0
    for i in ims: s.paste(i,(0,y)); y+=i.height+6
    s.save(f'renders/qc/{t}_sheet.jpg',quality=70); print('sheet',s.size)
