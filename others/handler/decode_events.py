"""
Decode Construct 2 obfuscated event AST (data.js) into readable pseudocode.

Strategy:
- Parse cr.getObjectRefTable() from c2runtime.js -> index -> ACE name map.
- Walk the event-sheet JSON (already exported) and pretty-print groups,
  blocks, conditions, actions, parameters using that map.

We focus on the "Map generation" group inside Game_events.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C2 = ROOT / "original_docs" / "c2runtime.js"
EVENTS = ROOT / "文档" / "datajs_export" / "event_sheets" / "Game_events.json"


def parse_ref_table():
    """Extract the ordered list of cr.* references -> friendly names."""
    lines = C2.read_text(encoding="utf-8", errors="replace").splitlines()
    # table body is lines 30951..31405 (1-based inclusive of entries)
    body = lines[30950:31405]  # 0-based slice -> lines 30951..31405
    names = []
    for ln in body:
        ln = ln.strip().rstrip(",")
        if not ln:
            continue
        names.append(ln)
    return names


def shorten(ref):
    """cr.plugins_.Sprite.prototype.cnds.IsOverlapping -> Sprite:cnd.IsOverlapping"""
    if ref is None:
        return "?"
    m = re.match(r"cr\.plugins_\.(\w+)\.prototype\.(cnds|acts|exps)\.(\w+)", ref)
    if m:
        return f"{m.group(1)}:{m.group(2)[:-1]}.{m.group(3)}"
    m = re.match(r"cr\.system_object\.prototype\.(cnds|acts|exps)\.(\w+)", ref)
    if m:
        return f"System:{m.group(1)[:-1]}.{m.group(2)}"
    m = re.match(r"cr\.behaviors\.(\w+)\.prototype\.(cnds|acts|exps)\.(\w+)", ref)
    if m:
        return f"beh.{m.group(1)}:{m.group(2)[:-1]}.{m.group(3)}"
    m = re.match(r"cr\.plugins_\.(\w+)$", ref)
    if m:
        return f"plugin<{m.group(1)}>"
    return ref


REF = None


def fref(i):
    if REF is None or i is None or i < 0 or i >= len(REF):
        return f"ref#{i}"
    return shorten(REF[i])


# ---- expression node decoding (ExpNode opcodes from c2runtime) ----
BINOPS = {4: "+", 5: "-", 6: "*", 7: "/", 8: "%", 9: "^",
          10: "&&", 11: "||", 12: "==", 13: "!=", 14: "<",
          15: "<=", 16: ">", 17: ">="}

# Optional object-type-index -> readable name map (filled from objects/).
TYPE_NAMES = {}


def tname(idx):
    return TYPE_NAMES.get(idx, f"t{idx}")


def decode_exp(node):
    if not isinstance(node, list) or not node:
        return repr(node)
    op = node[0]
    if op in (0, 1):           # int / float literal
        return str(node[1])
    if op == 2:                # string literal
        return json.dumps(node[1], ensure_ascii=False)
    if op == 3:                # unary minus
        return f"-{decode_exp(node[1])}"
    if op in BINOPS:           # binary op: m[1], m[2]
        return f"({decode_exp(node[1])} {BINOPS[op]} {decode_exp(node[2])})"
    if op == 18:               # conditional ternary: m[1]?m[2]:m[3]
        return f"({decode_exp(node[1])} ? {decode_exp(node[2])} : {decode_exp(node[3])})"
    if op == 19:               # system expression: func=m[1], params=m[2]
        name = fref(node[1])
        params = node[2] if len(node) == 3 else []
        args = ", ".join(decode_exp(p) for p in params)
        return f"{name}({args})"
    if op == 20:               # object expression: type=m[1] func=m[2] inst=m[4] params=m[5]
        name = fref(node[2])
        params = node[5] if len(node) == 6 else []
        args = ", ".join(decode_exp(p) for p in params)
        return f"{tname(node[1])}.{name}({args})"
    if op == 21:               # instance variable: type=m[1] inst=m[3] varindex=m[4]
        return f"{tname(node[1])}.iv[{node[4]}]"
    if op == 22:               # behavior expression: type=m[1] beh=m[2] func=m[3] params=m[6]
        params = node[6] if len(node) == 7 else []
        args = ", ".join(decode_exp(p) for p in params)
        return f"{tname(node[1])}.[{node[2]}].{fref(node[3])}({args})"
    if op == 23:               # event variable (global/local) by name
        return f"{node[1]}"
    return f"[op{op}:{node[1:]}]"


CMP = {0: "=", 1: "≠", 2: "<", 3: "≤", 4: ">", 5: "≥"}


def decode_param(p):
    """Parameter model: [ptype, payload...]"""
    if not isinstance(p, list) or not p:
        return repr(p)
    pt = p[0]
    if pt in (0, 1, 5, 7):     # number / string / layer / any -> expression
        return decode_exp(p[1])
    if pt in (3, 8):           # combo / cmp -> selection index
        return CMP.get(p[1], f"combo#{p[1]}") if pt == 8 else f"combo#{p[1]}"
    if pt == 4:                # object reference
        return tname(p[1])
    if pt == 10:               # instance variable index
        return f"iv[{p[1]}]"
    if pt == 11:               # event variable name
        return f"{p[1]}"
    if pt in (2, 12):          # audiofile / fileinfo
        return json.dumps(p[1], ensure_ascii=False)
    if pt == 13:               # variadic
        return ", ".join(decode_param(sp) for sp in p[1:])
    return f"<p{pt}:{p[1:]}>"


def decode_cond(m, indent):
    typ = m[0]
    func = fref(m[1])
    inverted = m[5] if len(m) > 5 else False
    params = m[9] if len(m) == 10 else []
    pstr = ", ".join(decode_param(p) for p in params)
    inv = "NOT " if inverted else ""
    tname = f"t{typ}" if typ != -1 else "System"
    return f"{indent}- IF {inv}{tname}.{func}({pstr})"


def decode_act(m, indent):
    typ = m[0]
    func = fref(m[1])
    params = m[5] if len(m) == 6 else []
    pstr = ", ".join(decode_param(p) for p in params)
    tname = f"t{typ}" if typ != -1 else "System"
    return f"{indent}> {tname}.{func}({pstr})"


def walk(node, depth, out, max_depth=40):
    indent = "  " * depth
    if not isinstance(node, list) or not node:
        return
    kind = node[0]
    if kind == 0:  # event block
        group = node[1]
        if group:
            out.append(f"{indent}### GROUP: {group[1]} (active={bool(group[0])})")
        cm = node[5] if len(node) > 5 else []
        am = node[6] if len(node) > 6 else []
        for c in cm:
            out.append(decode_cond(c, indent))
        for a in am:
            out.append(decode_act(a, indent))
        if len(node) == 8:
            for sub in node[7]:
                walk(sub, depth + 1, out, max_depth)
    elif kind == 1:  # variable
        # m: [1, name, type, value(?), ...]
        out.append(f"{indent}* VAR {node[1]} = {node[2] if len(node)>2 else '?'}")
    elif kind == 2:  # include
        out.append(f"{indent}(include sheet#{node[1] if len(node)>1 else '?'})")


def find_group(events, name):
    """events = top-level list. Find block whose group name matches."""
    for ev in events:
        if isinstance(ev, list) and ev and ev[0] == 0 and ev[1]:
            if ev[1][1].lower() == name.lower():
                return ev
    return None


def main():
    global REF
    REF = parse_ref_table()
    print(f"ref table entries: {len(REF)}")
    data = json.loads(EVENTS.read_text(encoding="utf-8"))
    # data is the sheet_data = [name? , events?] OR directly events list.
    # From export: project[6] items are (name, sheet_data); we saved sheet_data.
    # sheet_data structure used by EventSheet: m[0]=name, m[1]=events.
    events = data[1] if isinstance(data, list) and len(data) == 2 and isinstance(data[1], list) else data
    print(f"top-level events: {len(events)}")
    # list group names at top level
    for ev in events:
        if isinstance(ev, list) and ev and ev[0] == 0 and ev[1]:
            print("  group:", ev[1][1])

    grp = find_group(events, "Map generation")
    if grp:
        out = []
        walk(grp, 0, out)
        text = "\n".join(out)
        dest = ROOT / "文档" / "datajs_export" / "map_generation.decoded.txt"
        dest.write_text(text, encoding="utf-8")
        print(f"\nMap generation decoded -> {dest} ({len(out)} lines)")


if __name__ == "__main__":
    main()