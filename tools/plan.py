#!/usr/bin/env python3
"""Stage Execution Plan — the hub_plan_* tool family, as a file-backed CLI.
Replaces: hub_plan_write, hub_plan_patch_stage, hub_plan_replan, hub_plan_get_stage_status,
          hub_plan_get_stage_detail, hub_plan_get_work_items, hub_plan_update_stage_state.
Plan lives at projects/<slug>/plan.json. Every write validates and bumps `revision`.

  plan.py init   <proj> --workflow ad-tvc|drama-series|mv|direct [--variant V] --outline "id:name,id:name,..."
  plan.py author <proj> <stage.json>            # append or revise the authored stage (planner)
  plan.py status <proj>                          # summary: current stage, pending, next_action
  plan.py detail <proj> <stage_id>               # executor read: full stage contract + upstream runtime refs
  plan.py items  <proj> <stage_id> [ids...]      # work items with full prompts
  plan.py state  <proj> <stage_id> --status doing|done|blocked|waiting_user --expected S [--reason plan_review|result_review] [--failed id,id] [--results results.json]
  plan.py replan <proj> <ops.json>               # atomic suffix ops: revise_stage / insert_stage / omit_stage / remove_unexecuted_stage
  plan.py validate <proj>
"""
import argparse, json, os, sys, time, shutil

ROOT = os.environ.get('STUDIO_PROJECTS', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'projects'))
MODALITIES = {'image','video','audio.tts','audio.music','postprocess','document','planner_text'}
STATUSES = {'waiting_user','doing','done','blocked','pending'}
WAIT = {'plan_review','result_review'}

def path(proj): return os.path.join(ROOT, proj, 'plan.json')
def load(proj):
    p = path(proj)
    if not os.path.exists(p): die(f'no plan at {p}')
    return json.load(open(p))
def save(proj, plan):
    p = path(proj); bak = p + '.bak'
    if os.path.exists(p): shutil.copy(p, bak)
    plan['revision'] = plan.get('revision', 0) + 1
    plan['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    errs = validate_plan(plan)
    if errs:
        die('validation failed, nothing written:\n  ' + '\n  '.join(errs))
    tmp = p + '.tmp'; json.dump(plan, open(tmp, 'w'), indent=1, ensure_ascii=False); os.replace(tmp, p)
    return plan
def die(msg): print(json.dumps({'error': msg}, ensure_ascii=False)); sys.exit(1)
def out(o): print(json.dumps(o, indent=1, ensure_ascii=False))

# ---------- validation (the contract from _shared/stage-execution-plan.md) ----------
def validate_stage(st, plan):
    e = []
    sid = st.get('stage_id')
    if not sid: e.append('stage_id missing')
    if not st.get('goal'): e.append(f'{sid}: goal missing')
    if not isinstance(st.get('order'), int): e.append(f'{sid}: order must be int')
    for d in st.get('depends_on', []):
        if d not in [s['stage_id'] for s in plan['stages']] and d != sid: e.append(f'{sid}: depends_on unknown stage {d}')
    sf = st.get('stage_fields', {})
    for k in ('status','waiting_reason','approval','blocked_reason','failed_item_ids','runtime_refs','retry_count'):
        if k in sf: e.append(f'{sid}: runtime field {k} inside stage_fields (framework-owned)')
    items = st.get('work_items', [])
    ids = [w.get('id') for w in items]
    if len(ids) != len(set(ids)): e.append(f'{sid}: duplicate work item ids')
    has_visual = any(w.get('modality') in ('image','video') for w in items)
    if has_visual and 'max_generated_clip_duration_s' not in sf: e.append(f'{sid}: max_generated_clip_duration_s required on visual stages')
    cap = sf.get('max_generated_clip_duration_s', 15)
    caps = {c['id'] for c in st.get('ref_capsules', [])} | plan.get('_upstream_capsules', set())
    for w in items:
        wid = w.get('id', '?')
        if w.get('modality') not in MODALITIES: e.append(f'{sid}/{wid}: bad modality {w.get("modality")}')
        if w.get('modality') in ('image','video','audio.tts','audio.music') and not w.get('prompt') and not w.get('text'):
            e.append(f'{sid}/{wid}: prompt/text missing (executor dispatches as-is, never composes)')
        if w.get('modality') == 'video':
            r = w.get('render', {})
            if not r.get('audio_approach'): e.append(f'{sid}/{wid}: render.audio_approach must be stated positively')
            if r.get('duration_target_s', 0) > cap: e.append(f'{sid}/{wid}: duration {r.get("duration_target_s")} > cap {cap} — split into continuation items')
        for ref in w.get('refs', []):
            if ref not in caps and not str(ref).startswith('runtime:'): e.append(f'{sid}/{wid}: ref {ref} not in ref_capsules (or runtime:<stage>/<item>)')
        if w.get('modality') == 'document' and not (w.get('source', {}).get('document_path')): e.append(f'{sid}/{wid}: document item needs source.document_path (real file, written already)')
    for c in st.get('constraints', []):
        if not isinstance(c, dict) or 'rule' not in c: e.append(f'{sid}: constraints must be objects with a rule key')
    return e

def validate_plan(plan):
    e = []
    if not plan.get('workflow', {}).get('path'): e.append('workflow.path missing')
    orders = [s['order'] for s in plan['stages']]
    if orders != sorted(orders): e.append('stages not in order')
    allcaps = set()
    for st in sorted(plan['stages'], key=lambda s: s['order']):
        plan['_upstream_capsules'] = set(allcaps)
        e += validate_stage(st, plan)
        allcaps |= {c['id'] for c in st.get('ref_capsules', [])}
        rt = st.setdefault('runtime', {'status': 'pending'})
        if rt.get('status') not in STATUSES: e.append(f"{st['stage_id']}: bad runtime.status {rt.get('status')}")
        if rt.get('status') == 'waiting_user' and rt.get('waiting_reason') not in WAIT: e.append(f"{st['stage_id']}: waiting_user needs waiting_reason")
    plan.pop('_upstream_capsules', None)
    return e

# ---------- commands ----------
def cmd_init(a):
    os.makedirs(os.path.join(ROOT, a.proj), exist_ok=True)
    if os.path.exists(path(a.proj)) and not a.force: die('plan exists; use --force to overwrite')
    outline = []
    for i, tok in enumerate([t for t in a.outline.split(',') if t.strip()], 1):
        sid, _, name = tok.partition(':'); outline.append({'id': sid.strip(), 'order': i, 'name': (name or sid).strip()})
    plan = {'plan_id': f'{a.proj}-{int(time.time())}', 'project': a.proj, 'workflow': {'path': a.workflow, 'variant': a.variant}, 'sources': [], 'stage_outline': outline, 'stages': [], 'revision': 0}
    save(a.proj, plan); out({'plan_id': plan['plan_id'], 'stage_count': 0, 'pending_stages': outline})

def cmd_author(a):
    plan = load(a.proj); st = json.load(open(a.stage))
    st.setdefault('depends_on', []); st.setdefault('review', {'before_execution': [], 'after_execution': []})
    ex = next((s for s in plan['stages'] if s['stage_id'] == st['stage_id']), None)
    if ex:
        if ex.get('runtime', {}).get('status') == 'done': die('cannot revise a done stage; use replan for later stages')
        st['runtime'] = ex.get('runtime', {'status': 'pending'}); plan['stages'][plan['stages'].index(ex)] = st
    else:
        st['runtime'] = {'status': 'waiting_user', 'waiting_reason': 'plan_review'} if st.get('review', {}).get('before_execution') else {'status': 'doing'}
        if all(w.get('modality') in ('document','planner_text') for w in st.get('work_items', [])) and st.get('work_items'):
            st['runtime'] = {'status': 'waiting_user', 'waiting_reason': 'result_review'} if st['review'].get('after_execution') else {'status': 'done'}
        plan['stages'].append(st)
    save(a.proj, plan); cmd_status(a)

def cmd_status(a):
    plan = load(a.proj)
    authored = {s['stage_id'] for s in plan['stages']}
    pending = [o for o in plan['stage_outline'] if o['id'] not in authored and not o.get('omitted')]
    cur = next((s for s in sorted(plan['stages'], key=lambda s: s['order']) if s['runtime']['status'] != 'done'), None)
    nxt = 'author_next_stage' if (cur is None and pending) else ('dispatch_executor' if cur and cur['runtime']['status'] == 'doing' else ('ask_user' if cur and cur['runtime']['status'] == 'waiting_user' else ('resolve_block' if cur and cur['runtime']['status'] == 'blocked' else 'deliver')))
    out({'plan_id': plan['plan_id'], 'revision': plan['revision'], 'workflow': plan['workflow'], 'stage_count': len(plan['stages']),
         'stages': [{'order': s['order'], 'id': s['stage_id'], 'name': s.get('name', s['stage_id']), 'goal': s['goal'], 'status': s['runtime']['status'], 'waiting_reason': s['runtime'].get('waiting_reason'), 'failed_item_ids': s['runtime'].get('failed_item_ids', [])} for s in plan['stages']],
         'current_stage': cur['stage_id'] if cur else None, 'pending_stages': pending, 'next_action': nxt})

def cmd_detail(a):
    plan = load(a.proj); st = next((s for s in plan['stages'] if s['stage_id'] == a.stage), None) or die('unknown stage')
    up = {}
    for d in st.get('depends_on', []):
        ds = next((s for s in plan['stages'] if s['stage_id'] == d), None)
        if ds: up[d] = {'runtime_refs': ds['runtime'].get('runtime_refs', {}), 'ref_capsules': ds.get('ref_capsules', [])}
    d = dict(st); d['upstream'] = up
    big = [w['id'] for w in st.get('work_items', []) if len(w.get('prompt', '')) > 1500]
    if big and not a.full:
        d['work_items'] = [dict(w, prompt='<omitted, use: plan.py items>') if w['id'] in big else w for w in st['work_items']]
        d['notice'] = f'prompts omitted for {big}; fetch with plan.py items'
    out(d)

def cmd_items(a):
    plan = load(a.proj); st = next((s for s in plan['stages'] if s['stage_id'] == a.stage), None) or die('unknown stage')
    out([w for w in st.get('work_items', []) if not a.ids or w['id'] in a.ids])

def cmd_state(a):
    plan = load(a.proj); st = next((s for s in plan['stages'] if s['stage_id'] == a.stage), None) or die('unknown stage')
    rt = st['runtime']
    if a.expected and rt['status'] != a.expected: die(f"compare-and-set failed: status is {rt['status']}, expected {a.expected}")
    if a.results:
        res = json.load(open(a.results)); refs = rt.setdefault('runtime_refs', {}); sup = rt.setdefault('superseded_runtime_refs', {})
        for r in res.get('results', []):
            if r['id'] in refs: sup.setdefault(r['id'], []).append(refs[r['id']])
            refs[r['id']] = {k: r[k] for k in ('path','url','modality','model','summary') if k in r}
        rt['failed_item_ids'] = [f['id'] for f in res.get('failed', [])]
        rt['failures'] = res.get('failed', [])
    if a.failed: rt['failed_item_ids'] = a.failed.split(',')
    target = a.status
    if target == 'done':
        need = [w['id'] for w in st.get('work_items', []) if w.get('modality') not in ('document','planner_text')]
        missing = [i for i in need if i not in rt.get('runtime_refs', {})]
        if missing: target = 'blocked'; rt['blocked_reason'] = f'missing outputs {missing}'
        elif st.get('review', {}).get('after_execution') and not a.confirm: target = 'waiting_user'; rt['waiting_reason'] = 'result_review'
    if target == 'doing': rt['retry_count'] = rt.get('retry_count', 0) + (1 if rt['status'] in ('blocked','doing') else 0); rt.pop('waiting_reason', None)
    rt['status'] = target
    if target in ('done','doing','blocked'): rt.pop('waiting_reason', None)
    if a.reason: rt['waiting_reason'] = a.reason
    save(a.proj, plan); out({'stage_id': a.stage, 'effective_status': rt['status'], 'waiting_reason': rt.get('waiting_reason'), 'failed_item_ids': rt.get('failed_item_ids', []), 'retry_count': rt.get('retry_count', 0)})

def cmd_replan(a):
    plan = load(a.proj); ops = json.load(open(a.ops))
    if ops.get('expected_revision') is not None and ops['expected_revision'] != plan['revision']: die(f"revision mismatch {plan['revision']}")
    if ops.get('workflow_path') and ops['workflow_path'] != plan['workflow']['path']: die('different workflow path → route again and start a new plan')
    done_ids = [s['stage_id'] for s in plan['stages'] if s['runtime']['status'] == 'done']
    for op in ops['ops']:
        k = op['op']; sid = op.get('stage_id') or op.get('stage', {}).get('stage_id')
        if sid in done_ids: die(f'{k} touches done stage {sid} — prefix is frozen')
        if k == 'revise_stage':
            i = next(i for i, s in enumerate(plan['stages']) if s['stage_id'] == sid); st = op['stage']; st['runtime'] = {'status': 'waiting_user', 'waiting_reason': 'plan_review'} if st.get('review', {}).get('before_execution') else {'status': 'doing'}; plan['stages'][i] = st
        elif k == 'insert_stage':
            st = op['stage']; st['runtime'] = {'status': 'waiting_user', 'waiting_reason': 'plan_review'} if st.get('review', {}).get('before_execution') else {'status': 'doing'}
            plan['stages'].append(st); plan['stage_outline'].append({'id': st['stage_id'], 'order': st['order'], 'name': st.get('name', st['stage_id'])})
        elif k == 'insert_stage_outline':
            plan['stage_outline'].append(op['entry'])
        elif k == 'omit_stage':
            for o in plan['stage_outline']:
                if o['id'] == sid: o['omitted'] = True
        elif k == 'remove_unexecuted_stage':
            plan['stages'] = [s for s in plan['stages'] if s['stage_id'] != sid]; plan['stage_outline'] = [o for o in plan['stage_outline'] if o['id'] != sid]
        else: die(f'unknown op {k}')
    for s in plan['stages']: s['order'] = next(o['order'] for o in plan['stage_outline'] if o['id'] == s['stage_id']) if any(o['id'] == s['stage_id'] for o in plan['stage_outline']) else s['order']
    plan['stages'].sort(key=lambda s: s['order']); plan['stage_outline'].sort(key=lambda o: o['order'])
    save(a.proj, plan); out({'revision': plan['revision'], 'impact': [op['op'] + ':' + str(op.get('stage_id') or op.get('stage', {}).get('stage_id')) for op in ops['ops']]}); cmd_status(a)

def cmd_validate(a):
    plan = load(a.proj); e = validate_plan(plan); out({'ok': not e, 'errors': e})

if __name__ == '__main__':
    p = argparse.ArgumentParser(); sp = p.add_subparsers(dest='cmd', required=True)
    x = sp.add_parser('init'); x.add_argument('proj'); x.add_argument('--workflow', required=True); x.add_argument('--variant'); x.add_argument('--outline', required=True); x.add_argument('--force', action='store_true')
    x = sp.add_parser('author'); x.add_argument('proj'); x.add_argument('stage')
    x = sp.add_parser('status'); x.add_argument('proj')
    x = sp.add_parser('detail'); x.add_argument('proj'); x.add_argument('stage'); x.add_argument('--full', action='store_true')
    x = sp.add_parser('items'); x.add_argument('proj'); x.add_argument('stage'); x.add_argument('ids', nargs='*')
    x = sp.add_parser('state'); x.add_argument('proj'); x.add_argument('stage'); x.add_argument('--status', required=True); x.add_argument('--expected'); x.add_argument('--reason'); x.add_argument('--failed'); x.add_argument('--results'); x.add_argument('--confirm', action='store_true')
    x = sp.add_parser('replan'); x.add_argument('proj'); x.add_argument('ops')
    x = sp.add_parser('validate'); x.add_argument('proj')
    a = p.parse_args(); globals()['cmd_' + a.cmd](a)
