#!/usr/bin/env python3
"""369 Studio — app templates. Every app rides the SAME /api/generate; a template
shapes the final render prompt + sets mode/model/res/dur/ar. `build(user, fields)`
returns the engineered prompt (our seedance2 / Atlas prompt style).

Add a template here and it appears in /api/apps and works end-to-end. No new endpoints.
"""

NEG_V = ("NEGATIVE: blurry, deformed hands, extra limbs, face morphing, removed clothing, "
         "tank top, bare chest, watermark, on-screen text, glitching cuts.")

def _wrap_video(scene, shots, extra=""):
    return (f"One continuous cinematic clip, live-action, Arri Alexa texture, 35mm, natural light, "
            f"fine film grain. {scene}\n{shots}\n{extra}\n"
            f"TECHNICAL: realistic physics, accurate lip-sync if speech; no subtitles, no watermark.\n{NEG_V}")

TEMPLATES = {
  "creator": {
    "name":"Creator Studio","emoji":"🎬","mode":"video","model":"crun_fast","res":"480p","dur":"15s","ar":"9:16",
    "fields":[{"k":"prompt","label":"Describe the shot","type":"textarea"}],
    "build": lambda u,f: u or "cinematic establishing shot",
  },
  "marketing": {
    "name":"Marketing Studio","emoji":"🛍️","mode":"video","model":"crun_fast","res":"720p","dur":"8s","ar":"9:16",
    "fields":[{"k":"product","label":"Product","type":"text"},{"k":"hook","label":"Hook line","type":"text"},{"k":"style","label":"Style","type":"text"}],
    "build": lambda u,f: _wrap_video(
        f"Vertical UGC product ad. A relatable creator holds and demos {f.get('product','the product')} in a real home setting, {f.get('style','bright natural')} look.",
        f"SHOT 1 | 0-3s | selfie close: creator to camera, energetic hook: \"{f.get('hook','You NEED to see this')}\".\n"
        f"SHOT 2 | 3-6s | product demo, hands showing {f.get('product','it')} in use.\n"
        f"SHOT 3 | 6-8s | happy reaction + on-product beauty shot, soft CTA.",
        "AUDIO: upbeat, natural creator voice."),
  },
  "shorts": {
    "name":"Viral Shorts","emoji":"⚡","mode":"video","model":"crun_fast","res":"480p","dur":"15s","ar":"9:16",
    "fields":[{"k":"format","label":"Format","type":"text"},{"k":"prompt","label":"Script / idea","type":"textarea"}],
    "build": lambda u,f: _wrap_video(
        f"Vertical short, {f.get('format','cinematic story')} format.",
        f"BEAT: {u or f.get('prompt','')}", "AUDIO: narration + music bed, captions burned by post."),
  },
  "vtemplate": {
    "name":"Viral Templates","emoji":"🎭","mode":"video","model":"crun_fast","res":"720p","dur":"8s","ar":"9:16",
    "fields":[{"k":"effect","label":"Effect","type":"text"}],
    "build": lambda u,f: _wrap_video(
        f"Transformation effect: {f.get('effect','red carpet arrival')}. The subject is dropped into the scene with dramatic motion.",
        "SHOT: reveal → hero pose, flashing lights / dynamic camera.", "AUDIO: impact whoosh + crowd."),
  },
  "sheets": {
    "name":"Character Sheets","emoji":"🪪","mode":"image","model":"crun_fast","res":"480p","dur":"4s","ar":"9:16",
    "fields":[{"k":"name","label":"Name","type":"text"},{"k":"ident","label":"Identity","type":"textarea"},{"k":"wardrobe","label":"Wardrobe","type":"textarea"}],
    "build": lambda u,f: (
        "A three-panel character reference sheet, one horizontal frame, three equal vertical panels. "
        f"IDENTITY: {f.get('ident','')}. WARDROBE: {f.get('wardrobe','')}. "
        "LEFT: full-body front, no head/neck/hair (invisible-body, hollow neckline). CENTER: full-body rear, head attached. "
        "RIGHT: tight chest-up identity close-up. 18% grey seamless, flat shadowless catalogue light, true skin tone, 50mm. Photographed not generated."),
  },
  "influencer": {
    "name":"AI Influencer","emoji":"🧑‍🎤","mode":"image","model":"crun_fast","res":"480p","dur":"4s","ar":"4:5",
    "fields":[{"k":"name","label":"Name","type":"text"},{"k":"look","label":"Look / vibe","type":"textarea"}],
    "build": lambda u,f: (
        f"Editorial portrait of a virtual influencer named {f.get('name','Nova')}: {f.get('look','supermodel glam, viral energy')}. "
        "Studio softbox light, shallow depth, magazine-cover quality, natural skin texture. Photographed not generated."),
    "save_character": True,
  },
  "music": {
    "name":"Music Studio","emoji":"🎵","mode":"music","model":"crun_fast","res":"480p","dur":"15s","ar":"1:1",
    "fields":[{"k":"style","label":"Style / vibe","type":"text"},{"k":"title","label":"Title","type":"text"},{"k":"lyrics","label":"Lyrics (blank = instrumental)","type":"textarea"}],
    "build": lambda u,f: f.get('style','cinematic') + " — " + f.get('title','Untitled'),
  },
  "author": {
    "name":"Author Studio","emoji":"📖","mode":"text","model":"crun_fast","res":"480p","dur":"4s","ar":"1:1",
    "fields":[{"k":"title","label":"Book title","type":"text"},{"k":"genre","label":"Genre","type":"text"},{"k":"premise","label":"Premise","type":"textarea"}],
    "build": lambda u,f: f"Write chapter 1 of a {f.get('genre','literary')} novel titled '{f.get('title','Untitled')}'. Premise: {f.get('premise','')}. ~700 words, vivid, strong hook.",
  },
  "notes": {
    "name":"Notetaker","emoji":"🎙️","mode":"notes","model":"crun_fast","res":"480p","dur":"4s","ar":"1:1",
    "fields":[{"k":"note","label":"Paste text / (audio upload soon)","type":"textarea"}],
    "build": lambda u,f: f"Summarize into clear minutes with action items:\n{f.get('note','')}",
  },
}

def apply_template(tid, user_prompt, fields):
    t = TEMPLATES.get(tid)
    if not t: return None
    return {"prompt": t["build"](user_prompt, fields or {}),
            "mode": t["mode"], "model": t["model"], "res": t["res"], "dur": t["dur"], "ar": t["ar"]}

def catalog():
    return [{"id":k,"name":v["name"],"emoji":v["emoji"],"mode":v["mode"],"fields":v["fields"]} for k,v in TEMPLATES.items()]
