from __future__ import annotations

from typing import List, Tuple

from ir_codegen import TACInstr, _renumber


OPT1_NAME = "Устранение временной переменной (copy propagation)"
OPT2_NAME = "Свёртка констант и канонизация объявления"


def optimize_eliminate_temp_copy(instrs: List[TACInstr]) -> List[TACInstr]:
    out: List[TACInstr] = []
    i = 0
    while i < len(instrs):
        if (
            i + 1 < len(instrs)
            and instrs[i].op == "LOAD_CONST"
            and instrs[i + 1].op == "STORE"
            and instrs[i + 1].arg2 == instrs[i].arg1
        ):
            out.append(
                TACInstr(
                    index=0,
                    op="STORE",
                    arg1=instrs[i + 1].arg1,
                    arg2=instrs[i].arg2,
                )
            )
            i += 2
            if i < len(instrs) and instrs[i].op == "SET_TYPE":
                out.append(instrs[i])
                i += 1
            continue
        out.append(instrs[i])
        i += 1
    return _renumber(out)


def optimize_fold_and_canonical(instrs: List[TACInstr]) -> List[TACInstr]:
    out: List[TACInstr] = []
    i = 0
    while i < len(instrs):
        if (
            i + 1 < len(instrs)
            and instrs[i].op == "STORE"
            and instrs[i + 1].op == "SET_TYPE"
        ):
            name = instrs[i].arg1
            value = instrs[i].arg2
            typ = instrs[i + 1].arg2
            out.append(
                TACInstr(
                    index=0,
                    op="CONST_DECL",
                    arg1=name,
                    arg2=typ,
                    arg3=value,
                )
            )
            i += 2
            continue
        if instrs[i].op == "STORE" and instrs[i].arg2.isdigit():
            out.append(
                TACInstr(
                    index=0,
                    op="CONST_DECL",
                    arg1=instrs[i].arg1,
                    arg2="?",
                    arg3=instrs[i].arg2,
                )
            )
            i += 1
            continue
        out.append(instrs[i])
        i += 1
    return _renumber(out)


def apply_optimizations(instrs: List[TACInstr]) -> Tuple[List[TACInstr], List[TACInstr], List[TACInstr]]:
    raw = list(instrs)
    after_opt1 = optimize_eliminate_temp_copy(raw)
    after_opt2 = optimize_fold_and_canonical(after_opt1)
    return raw, after_opt1, after_opt2
