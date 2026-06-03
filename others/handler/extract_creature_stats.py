# -*- coding: utf-8 -*-
"""
从原始 data.js 提取【生物/敌人】权威默认实例变量，并结合 game_events.decoded.txt 明文，
输出可复用 JSON。

权威来源：
  - 实例变量默认值：Construct2 在 Spawn 时复制该类型“default_instance”（即布局中第一个放置的实例）的
    initial_vars。本脚本扫描 project[5] 全部布局的 world/nonworld 实例，取目标类型第一个实例的 inst[3]，
    每项 = [value, name]，取 value 即默认值。（见 c2runtime.js createInstanceFromInit: inst.instance_vars[i]=initial_vars[i][0]）
  - 伤害/速度/计时等：见 game_events.decoded.txt（明文），本脚本不重复提取，仅在注释中标注。

注意：origin 为符号链接，handler 经符号链接解析后 ROOT 会指向真实路径，故此处显式给出 data.js 路径。
"""
import json, pathlib

DATA = pathlib.Path(r"D:/godot_projects/minidayz/origin/original_docs/data.js")
OUT  = pathlib.Path(r"D:/godot_projects/minidayz/origin/others/文档/datajs_export/parsed/creatures.json")

# 目标类型索引 -> 可读名（依据 sprite 图集名）
TYPES = {
    197: "zed_normal_skin1", 575: "zed_normal_skin2", 576: "zed_normal_skin3",
    579: "zed_normal_skin4", 580: "zed_normal_skin5", 712: "zed_normal_skin(80hp)",
    716: "zed_buried_skin", 212: "zed_army_skin1", 577: "zed_army_skin2", 578: "zed_army_skin3",
    394: "zed_fast_skin1", 581: "zed_fast_skin2", 582: "zed_fast_skin3", 778: "zed_fast_skin(120hp)",
    723: "zed_shooter_skin1(125hp)", 726: "zed_shooter_skin(shotgun_175hp)", 885: "zed_shooter_puncher_skin",
    710: "zed_screamer_skin", 847: "zed_tank_skin",
    469: "wolf_skin", 472: "deer_skin", 609: "rabbit_skin", 687: "crow_skin",
}

def main():
    d = json.loads(DATA.read_text(encoding="utf-8-sig"))
    layouts = d["project"][5]
    want = set(TYPES)
    res = {}
    def scan(inst):
        if not isinstance(inst, list) or len(inst) < 4: return
        t = inst[1]
        if t in want and t not in res:
            ivs = inst[3]
            if isinstance(ivs, list):
                res[t] = [iv[0] if isinstance(iv, list) and iv else iv for iv in ivs]
    for lay in layouts:
        for layer in (lay[6] if len(lay) > 6 and isinstance(lay[6], list) else []):
            if isinstance(layer, list) and len(layer) > 14 and isinstance(layer[14], list):
                for inst in layer[14]:
                    scan(inst)
        for inst in (lay[7] if len(lay) > 7 and isinstance(lay[7], list) else []):
            scan(inst)
    out = {TYPES[t]: {"type_index": t, "instance_vars_default": res[t]} for t in sorted(res)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", OUT, "types:", len(out))
    print("missing:", sorted(want - set(res)))

if __name__ == "__main__":
    main()
