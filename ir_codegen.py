from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from semantic_analysis import ConstDeclNode, Program


@dataclass
class TACInstr:
    index: int
    op: str
    arg1: str = ""
    arg2: str = ""
    arg3: str = ""

    def format_line(self) -> str:
        if self.op == "LOAD_CONST":
            return f"{self.index:3d}  {self.arg1} = {self.arg2}"
        if self.op == "STORE":
            return f"{self.index:3d}  {self.arg1} = {self.arg2}"
        if self.op == "SET_TYPE":
            return f"{self.index:3d}  type({self.arg1}) = {self.arg2}"
        if self.op == "CONST_DECL":
            return f"{self.index:3d}  CONST {self.arg1} : {self.arg2} = {self.arg3}"
        return f"{self.index:3d}  {self.op} {self.arg1} {self.arg2} {self.arg3}".strip()


def _renumber(instrs: List[TACInstr]) -> List[TACInstr]:
    out: List[TACInstr] = []
    for i, ins in enumerate(instrs, start=1):
        out.append(
            TACInstr(index=i, op=ins.op, arg1=ins.arg1, arg2=ins.arg2, arg3=ins.arg3)
        )
    return out


def generate_tac(program: Optional[Program]) -> List[TACInstr]:
    if program is None or not program.declarations:
        return []

    instrs: List[TACInstr] = []
    temp_id = 0
    for decl in program.declarations:
        if decl.value is None or decl.name is None:
            continue
        tname = f"t{temp_id}"
        temp_id += 1
        instrs.append(
            TACInstr(
                index=len(instrs) + 1,
                op="LOAD_CONST",
                arg1=tname,
                arg2=str(decl.value.value),
            )
        )
        instrs.append(
            TACInstr(
                index=len(instrs) + 1,
                op="STORE",
                arg1=decl.name,
                arg2=tname,
            )
        )
        if decl.type_node is not None:
            instrs.append(
                TACInstr(
                    index=len(instrs) + 1,
                    op="SET_TYPE",
                    arg1=decl.name,
                    arg2=decl.type_node.name,
                )
            )
    return instrs


def format_tac_block(title: str, instrs: List[TACInstr]) -> str:
    lines = [title, "-" * len(title)]
    if not instrs:
        lines.append("(пусто)")
    else:
        for ins in instrs:
            lines.append(ins.format_line())
    return "\n".join(lines) + "\n"
