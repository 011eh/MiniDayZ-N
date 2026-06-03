# -*- coding: utf-8 -*-
"""
从已解码的 Game_events 中提取【明文】物品数值，输出可复用 JSON。
依赖：先由 decode 流程生成 ../文档/datajs_export/game_events.decoded.txt
权威可提取项：
  - 消耗品效果 (item_activate / item_activate2): iv[13]饱食 iv[14]水分 iv[15]生命 iv[16]体温 + 特殊标志
  - 武器散布 (set_wpn_dispersion_f 步枪 / _p 手枪): 按武器内部索引
注意：武器伤害/弹匣、衣物护甲/保暖 存于【混淆的实例变量默认值】中，无法由此脚本明文提取。
"""
import re, json, pathlib

BASE = pathlib.Path(__file__).resolve().parent
DEC  = BASE / ".." / "文档" / "datajs_export" / "game_events.decoded.txt"
XML  = pathlib.Path(r"D:/godot_projects/minidayz/origin/original_docs/l_eng_items.xml")
OUT  = BASE / ".." / "文档" / "datajs_export" / "parsed"
OUT.mkdir(parents=True, exist_ok=True)

LINES = DEC.read_text(encoding="utf-8").split("\n")

def extract_fn(fn):
    start=base=None; res=[]
    for l in LINES:
        if start is None:
            if re.search(r'OnFunction\("%s"\)'%re.escape(fn), l):
                start=True; base=len(l)-len(l.lstrip()); res.append(l)
            continue
        ind=len(l)-len(l.lstrip())
        if l.strip().startswith("- IF") and 'OnFunction(' in l and ind<=base: break
        if l.strip().startswith("### GROUP") and ind<=base: break
        res.append(l)
    return "\n".join(res)

def item_names():
    xml = XML.read_text(encoding="utf-8")
    return {int(i):n for i,n in re.findall(r'<id>(\d+)</id>\s*<name>([^<]*)</name>', xml)}

IV = {'13':'hunger','14':'water','15':'health','16':'warmth'}
# 标志位语义：iv[22]出血 iv[34]感染 iv[32]维生素/免疫 iv[49]回血冷却
# 注意 iv[17] 是消音器/扼流圈等配件属性，并非消耗品效果，忽略。

def parse_consumables(fn):
    body = extract_fn(fn)
    blocks = re.split(r'(?m)^\s*- IF t180\.Function:cnd\.CompareParam\(0, =, (\d+)\)\s*$', body)
    rows={}
    for k in range(1,len(blocks),2):
        pid=int(blocks[k]); c=blocks[k+1]
        eff={}
        def addflag(f):
            eff.setdefault('flags',[])
            if f not in eff['flags']: eff['flags'].append(f)
        for verb,iv,val in re.findall(r'(Add|Sub|Set)InstanceVar\(iv\[(\d+)\], ([\d.]+)\)', c):
            fv=float(val)
            if iv in IV and verb in ('Add','Sub'):
                v=-fv if verb=='Sub' else fv
                eff[IV[iv]] = eff.get(IV[iv],0)+v
            elif iv=='22': addflag('stop_bleed')
            elif iv=='34': addflag('cure_infection' if fv==0 else 'infection_risk')
            elif iv=='32': addflag('vitamins')
            elif iv=='49' and verb=='Sub': addflag('health_regen_cd')
        # 数值取整展示
        for kk in list(eff):
            if kk!='flags' and float(eff[kk]).is_integer(): eff[kk]=int(eff[kk])
        rows[pid]=eff
    return rows

def parse_dispersion(fn, ivkey):
    body = extract_fn(fn)
    blocks = re.split(r'(?m)^\s*- IF t172\.Sprite:cnd\.CompareInstanceVar\(iv\[%s\], =, (\d+)\)\s*$'%ivkey, body)
    rows={}
    keys={'dispersion_angle_max':'max_spread','dispersion_default':'base_spread',
          'dispersion_cooldown_step':'cooldown_step','dispersion_pershot':'spread_per_shot',
          'dispersion_run_penalty':'run_penalty'}
    for k in range(1,len(blocks),2):
        idx=int(blocks[k]); c=blocks[k+1]
        d={}
        for var,val in re.findall(r'SetVar\((dispersion_\w+), ([\d.]+)\)', c):
            if var in keys:
                d[keys[var]] = float(val) if '.' in val else int(val)
        if d: rows[idx]=d
    return rows

def main():
    names = item_names()
    consum = {}
    for fn in ("item_activate","item_activate2"):
        for pid,eff in parse_consumables(fn).items():
            if eff:
                consum.setdefault(pid,{}).update(eff)
    consum_named = {pid:{"name":names.get(pid,"?"),**eff} for pid,eff in sorted(consum.items())}
    (OUT/"consumables.json").write_text(json.dumps(consum_named,ensure_ascii=False,indent=1),encoding="utf-8")

    disp = {
        "firearm_by_index_iv1": parse_dispersion("set_wpn_dispersion_f","1"),
        "pistol_by_index_iv43": parse_dispersion("set_wpn_dispersion_p","43"),
    }
    (OUT/"weapon_dispersion.json").write_text(json.dumps(disp,ensure_ascii=False,indent=1),encoding="utf-8")

    (OUT/"item_names.json").write_text(json.dumps({str(k):v for k,v in sorted(names.items())},ensure_ascii=False,indent=1),encoding="utf-8")
    print("consumables:",len(consum_named),"| firearm disp idx:",len(disp["firearm_by_index_iv1"]),"| pistol disp idx:",len(disp["pistol_by_index_iv43"]),"| names:",len(names))
    print("written ->",OUT)

if __name__=="__main__":
    main()
