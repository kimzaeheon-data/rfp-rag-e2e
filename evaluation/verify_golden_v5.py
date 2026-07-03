# -*- coding: utf-8 -*-
"""
V5 골든셋 무결성 검사 (freeze 넘기기 전 게이트).
재청킹/재라벨 때마다 돌려 깨짐 자동 감지.
  python verify_golden_v5.py
경로는 스크립트 위치(중급 프로젝트) 기준.
"""
import json, re, sys, os
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))

GOLD  = os.path.join(HERE, 'v5_gold_labels.json')
CHUNKS= os.path.join(HERE, 'chunks_v1_0622_enriched.json')   # PASS와 index 동일
PIN   = 'chunks_v1_0622_PASS'

SCOPE   = {'requirement','submission','scoring'}
ACTOR   = {'bidder_action','bidder_evaluation_rule','buyer_internal_process','context_or_background'}
ACTOR_IN= {'bidder_action','bidder_evaluation_rule'}
ESCOPE  = {'in_scope','out_of_scope'}
JUDGE   = {'in_scope','out_of_scope','review'}
CRIT    = {'eligibility_gate','mandatory_submission','mandatory_delivery','scored_criterion',
           'optional_or_preferred','unknown','n_a'}
BASIS   = {'explicit','inferred','n_a'}
FIELDS  = ['item','quote','evidence_chunk_id','chunk_version','scope','actor_label',
           'expected_scope','expected_judgment','allowed_actor_labels',
           'criticality','criticality_basis','is_boundary','note']

def norm(s): return re.sub(r'\s+','',s or '')

def main():
    d = json.load(open(GOLD, encoding='utf-8'))
    ch= json.load(open(CHUNKS, encoding='utf-8'))
    TEXT={}; CTYPE={}
    for r in ch:
        m=r['metadata']; k=(m['doc_id'], int(m['chunk_index']))
        TEXT[k]=r['page_content']; CTYPE[k]=m.get('content_type')

    labels=[(doc,i,l) for doc,v in d['docs'].items() for i,l in enumerate(v['labels'])]
    results=[]   # (name, fail_count, [samples])
    def check(name, bad):
        results.append((name, len(bad), bad[:6]))

    # C1 구조
    tot=len(labels)
    check(f'C1 총 item=954 (실제 {tot}), 문서 8 (실제 {len(d["docs"])})',
          [] if (tot==954 and len(d['docs'])==8) else ['MISMATCH'])
    # C2 필드 완비 (note는 빈 문자열 허용, 나머지 truthy)
    bad=[]
    for doc,i,l in labels:
        for f in FIELDS:
            if f not in l: bad.append(f'{doc}[{i}] 필드누락:{f}')
        if not l.get('item'): bad.append(f'{doc}[{i}] item 빈값')
        if not l.get('quote'): bad.append(f'{doc}[{i}] quote 빈값')
        if not l.get('allowed_actor_labels'): bad.append(f'{doc}[{i}] allowed 빈값')
    check('C2 스키마 13필드 완비 + 핵심필드 non-empty', bad)
    # C3 enum 유효성
    bad=[]
    for doc,i,l in labels:
        if l['scope'] not in SCOPE: bad.append(f'{doc}[{i}] scope={l["scope"]}')
        if l['actor_label'] not in ACTOR: bad.append(f'{doc}[{i}] actor={l["actor_label"]}')
        if l['expected_scope'] not in ESCOPE: bad.append(f'{doc}[{i}] escope={l["expected_scope"]}')
        if l['expected_judgment'] not in JUDGE: bad.append(f'{doc}[{i}] judge={l["expected_judgment"]}')
        if l['criticality'] not in CRIT: bad.append(f'{doc}[{i}] crit={l["criticality"]}')
        if l['criticality_basis'] not in BASIS: bad.append(f'{doc}[{i}] basis={l["criticality_basis"]}')
        if not isinstance(l['is_boundary'], bool): bad.append(f'{doc}[{i}] is_boundary 비불리언')
    check('C3 enum 값 유효성 (scope/actor/escope/judge/crit/basis)', bad)
    # C4 chunk_version 핀 정합
    bad=[f'{doc}[{i}]' for doc,i,l in labels if l['chunk_version']!=PIN]
    check(f'C4 chunk_version=={PIN} 정합', bad)
    # C5 evidence 실재 + doc 정합
    bad=[]
    for doc,i,l in labels:
        eid=l['evidence_chunk_id']; dd,ix=eid.split('#')
        if dd!=doc: bad.append(f'{doc}[{i}] eid doc불일치:{eid}')
        if (dd,int(ix)) not in TEXT: bad.append(f'{doc}[{i}] 청크없음:{eid}')
    check('C5 evidence_chunk_id 실재 + doc 정합', bad)
    # C6 actor -> expected_scope 정합
    bad=[f'{doc}[{i}]' for doc,i,l in labels
         if (l['actor_label'] in ACTOR_IN) != (l['expected_scope']=='in_scope')]
    check('C6 actor↔expected_scope 정합 (채점 정본축)', bad)
    # C7 judgment == expected_scope (또는 review)
    bad=[f'{doc}[{i}]' for doc,i,l in labels
         if l['expected_judgment'] not in (l['expected_scope'],'review')]
    check('C7 expected_judgment↔expected_scope 미러링', bad)
    # C8 criticality <-> expected_scope (out ⟺ n_a)
    bad=[]
    for doc,i,l in labels:
        out=(l['expected_scope']=='out_of_scope'); na=(l['criticality']=='n_a')
        if out!=na: bad.append(f'{doc}[{i}] out={out} n_a={na}')
    check('C8 out_of_scope ⟺ criticality=n_a', bad)
    # C9 allowed_actor_labels 포함
    bad=[f'{doc}[{i}]' for doc,i,l in labels if l['actor_label'] not in l['allowed_actor_labels']]
    check('C9 actor_label ∈ allowed_actor_labels', bad)
    # C10 문서내 중복 (item+evidence)
    bad=[]
    for doc,v in d['docs'].items():
        seen=Counter((norm(l['item']),l['evidence_chunk_id']) for l in v['labels'])
        bad+= [f'{doc} 중복:{k[0][:20]}' for k,c in seen.items() if c>1]
    check('C10 문서내 (item+evidence) 중복 없음', bad)
    # C11 quote가 evidence 청크 본문의 부분 (공백무시). DOC_061은 손큐레이션(…생략)이라 예외 허용
    bad=[]
    for doc,i,l in labels:
        if doc=='DOC_061': continue
        dd,ix=l['evidence_chunk_id'].split('#')
        t=norm(TEXT.get((dd,int(ix)),''))
        if norm(l['quote'])[:40] and norm(l['quote'])[:40] not in t:
            bad.append(f'{doc}[{i}] quote≠청크본문')
    check('C11 quote ⊂ evidence 청크 본문 (DOC_061 손큐레이션 제외)', bad)
    # C12 [soft] scope=scoring 은 표(table)가 근거인가
    soft=[f'{doc}[{i}] ctype={CTYPE.get(tuple([l["evidence_chunk_id"].split("#")[0],int(l["evidence_chunk_id"].split("#")[1])]))}'
          for doc,i,l in labels if l['scope']=='scoring'
          and CTYPE.get((l['evidence_chunk_id'].split('#')[0],int(l['evidence_chunk_id'].split('#')[1])))!='table']
    # C13 freeze 지문 재계산 정합
    fp=d.get('freeze',{}).get('fingerprint',{})
    rc_scope=Counter(l['scope'] for _,_,l in labels)
    rc_crit =Counter(l['criticality'] for _,_,l in labels)
    fp_ok = (fp.get('total_items')==tot and dict(rc_scope)==fp.get('scope')
             and dict(rc_crit)==fp.get('criticality'))
    check('C13 freeze fingerprint 재계산 일치', [] if fp_ok else ['MISMATCH'])

    # ---- 리포트 ----
    print('='*66)
    print(f'V5 골든 무결성 검사 — {GOLD}')
    print(f'pin={PIN} | frozen={d.get("freeze",{}).get("frozen")}')
    print('='*66)
    hard_fail=0
    for name,n,samp in results:
        mark='PASS' if n==0 else f'FAIL({n})'
        if n: hard_fail+=1
        print(f'[{mark:8}] {name}')
        for s in samp: print(f'            - {s}')
    print(f'[SOFT    ] C12 scoring 근거가 표(table)가 아님: {len(soft)}건 (참고용)')
    for s in soft[:6]: print(f'            - {s}')
    print('='*66)
    print('결과:', 'ALL PASS — 넘겨도 됨 ✅' if hard_fail==0 else f'{hard_fail}개 검사 FAIL — 수정 필요 ❌')
    return hard_fail

if __name__=='__main__':
    sys.exit(1 if main() else 0)
