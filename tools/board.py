#!/usr/bin/env python3
"""Production Board — renders projects/<slug>/plan.json (+ renders/ thumbnails) into one self-contained HTML.
  board.py <proj> [--out projects/<proj>/board.html]
Publish the HTML as an Artifact for plan_review / result_review; the user reads prompts + cost there."""
import json, os, sys, base64, subprocess, html, glob
ROOT = os.environ.get('STUDIO_PROJECTS', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'projects'))
COL = {'done':'#0E6B60','doing':'#B86E08','waiting_user':'#7C4DFF','blocked':'#A93A2E','pending':'#7A8781'}
def thumb(p):
    try:
        if p.lower().endswith(('.mp4','.mov','.webm')):
            out = p + '.thumb.jpg'
            if not os.path.exists(out): subprocess.run(['ffmpeg','-v','error','-y','-ss','1','-i',p,'-frames:v','1','-vf','scale=240:-1',out],check=True)
            p = out
        elif p.lower().endswith(('.mp3','.wav','.m4a')): return '<div class="aud">audio</div>'
        elif p.lower().endswith(('.png','.jpg','.jpeg','.webp')) and os.path.getsize(p) > 200_000:
            out = p + '.thumb.jpg'
            if not os.path.exists(out): subprocess.run(['ffmpeg','-v','error','-y','-i',p,'-vf','scale=240:-1',out],check=True)
            p = out
        return f'<img src="data:image/jpeg;base64,{base64.b64encode(open(p,"rb").read()).decode()}">'
    except Exception as e: return f'<div class="aud">{html.escape(str(e))[:40]}</div>'
def main(proj, out):
    plan = json.load(open(os.path.join(ROOT, proj, 'plan.json'))); pdir = os.path.join(ROOT, proj)
    brief = open(os.path.join(pdir,'brief.md')).read() if os.path.exists(os.path.join(pdir,'brief.md')) else ''
    h = [f"""<title>{html.escape(proj)} · Production Board</title><style>
body{{margin:0;background:#F6F8F5;color:#15211C;font:14px/1.5 'IBM Plex Sans',system-ui,sans-serif;padding:24px clamp(16px,4vw,48px)}}
h1{{font-size:26px;margin:0 0 4px}} .meta{{font-family:ui-monospace,monospace;font-size:12px;color:#7A8781}}
.stage{{border:1px solid #D5DDD7;background:#fff;margin:14px 0;padding:14px 16px;border-left:5px solid #ccc}}
.st{{display:inline-block;font-family:ui-monospace,monospace;font-size:11px;color:#fff;padding:2px 8px;border-radius:2px;margin-left:8px}}
.wi{{border-top:1px dashed #D5DDD7;padding:8px 0;display:grid;grid-template-columns:120px 1fr;gap:12px}}
.wi img{{width:120px;border-radius:3px}} .aud{{width:120px;height:60px;background:#EDF1EC;display:grid;place-items:center;font-size:11px;color:#7A8781}}
pre{{white-space:pre-wrap;font-size:12px;background:#EDF1EC;padding:8px;border-radius:3px;max-height:220px;overflow:auto}}
.rev{{background:#FBEBD2;padding:8px 12px;border-left:4px solid #B86E08;margin:8px 0;font-size:13px}}
.brief{{background:#fff;border:1px solid #D5DDD7;padding:12px 16px;white-space:pre-wrap;font-size:13px;max-height:260px;overflow:auto}}
</style><h1>{html.escape(proj)} — Production Board</h1><div class="meta">plan {plan['plan_id']} · rev {plan.get('revision')} · workflow {plan['workflow']['path']} · {plan.get('updated_at','')}</div>"""]
    if brief: h.append(f'<h3>Brief</h3><div class="brief">{html.escape(brief)}</div>')
    authored = {s['stage_id'] for s in plan['stages']}
    for o in plan['stage_outline']:
        s = next((x for x in plan['stages'] if x['stage_id']==o['id']), None)
        if not s:
            h.append(f'<div class="stage" style="border-left-color:#7A8781;opacity:.6"><b>{o["order"]}. {html.escape(o["name"])}</b><span class="st" style="background:#7A8781">{"omitted" if o.get("omitted") else "pending"}</span></div>'); continue
        rt = s['runtime']; st = rt['status']
        h.append(f'<div class="stage" style="border-left-color:{COL.get(st,"#ccc")}"><b>{s["order"]}. {html.escape(s.get("name",s["stage_id"]))}</b><span class="st" style="background:{COL.get(st,"#ccc")}">{st}{(" · "+rt["waiting_reason"]) if rt.get("waiting_reason") else ""}</span><div>{html.escape(s["goal"])}</div>')
        rv = s.get('review',{})
        if st=='waiting_user' and rt.get('waiting_reason')=='plan_review' and rv.get('before_execution'): h.append('<div class="rev"><b>Confirm before generation:</b> '+'; '.join(map(html.escape,rv['before_execution']))+'</div>')
        if st=='waiting_user' and rt.get('waiting_reason')=='result_review' and rv.get('after_execution'): h.append('<div class="rev"><b>Review outputs:</b> '+'; '.join(map(html.escape,rv['after_execution']))+'</div>')
        if rt.get('blocked_reason'): h.append(f'<div class="rev" style="border-color:#A93A2E;background:#F7DEDA">{html.escape(str(rt["blocked_reason"]))}</div>')
        locks = s.get('execution_locks',[]);
        if locks: h.append('<div class="meta">locks: '+html.escape(json.dumps(locks))+'</div>')
        for w in s.get('work_items',[]):
            ref = rt.get('runtime_refs',{}).get(w['id']); tb = thumb(os.path.join(pdir, ref['path'])) if ref and ref.get('path') and os.path.exists(os.path.join(pdir, ref['path'])) else '<div class="aud">not rendered</div>'
            failed = ' style="color:#A93A2E"' if w['id'] in rt.get('failed_item_ids',[]) else ''
            h.append(f'<div class="wi">{tb}<div><b{failed}>{html.escape(w.get("name",w["id"]))}</b> <span class="meta">{w["id"]} · {w.get("modality")} · {html.escape(json.dumps(w.get("render",{})))} · refs {html.escape(",".join(map(str,w.get("refs",[]))))}</span>'
                     + (f'<pre>{html.escape(w.get("prompt") or w.get("text") or "")}</pre>' if (w.get('prompt') or w.get('text')) else '') + (f'<div class="meta">{html.escape(ref.get("summary",""))} · {html.escape(ref.get("path",""))}</div>' if ref else '') + '</div></div>')
        h.append('</div>')
    open(out,'w').write('\n'.join(h)); print(out)
if __name__=='__main__':
    proj = sys.argv[1]; out = sys.argv[sys.argv.index('--out')+1] if '--out' in sys.argv else os.path.join(ROOT, proj, 'board.html'); main(proj, out)
