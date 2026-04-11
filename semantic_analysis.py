from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from lexical_analyzer import LexicalAnalyzer, Token, TokenType
from parser import Parser, ParserError, SyntaxTreeNode


@dataclass
class IntegerLiteralNode:
    value: int


@dataclass
class TypeNode:
    name: str


@dataclass
class ConstDeclNode:
    name: Optional[str] = None
    modifiers: List[str] = field(default_factory=list)
    type_node: Optional[TypeNode] = None
    value: Optional[IntegerLiteralNode] = None
    line: Optional[int] = None
    column: Optional[int] = None


@dataclass
class Program:
    declarations: List[ConstDeclNode] = field(default_factory=list)


@dataclass
class SemanticError:
    message: str
    line: int
    column: int
    fragment: str = ""

    def format_line(self) -> str:
        return f"{self.message} | строка {self.line}, символ {self.column}"


TYPE_RANGE: Dict[str, Tuple[int, int]] = {
    "i8": (-(2**7), 2**7 - 1),
    "i16": (-(2**15), 2**15 - 1),
    "i32": (-(2**31), 2**31 - 1),
    "i64": (-(2**63), 2**63 - 1),
    "i128": (-(2**127), 2**127 - 1),
    "u8": (0, 2**8 - 1),
    "u16": (0, 2**16 - 1),
    "u32": (0, 2**32 - 1),
    "u64": (0, 2**64 - 1),
    "u128": (0, 2**128 - 1),
}


def _syntax_child(decl: SyntaxTreeNode, kind: str) -> Optional[SyntaxTreeNode]:
    for c in decl.children:
        if c.node_type == kind:
            return c
    return None


def _literal_int(val_node: Optional[SyntaxTreeNode]) -> Optional[int]:
    if val_node is None or val_node.value is None:
        return None
    try:
        return int(val_node.value, 10)
    except ValueError:
        return None


def _int_literal_from_syntax(val: Optional[SyntaxTreeNode]) -> Optional[IntegerLiteralNode]:
    if val is None or val.value is None:
        return None
    try:
        return IntegerLiteralNode(value=int(val.value, 10))
    except ValueError:
        return None


def _syntax_decl_to_ast(node: SyntaxTreeNode) -> ConstDeclNode:
    kw = _syntax_child(node, "keyword")
    ident = _syntax_child(node, "identifier")
    typ = _syntax_child(node, "type")
    val = _syntax_child(node, "value")
    modifiers: List[str] = []
    if kw is not None and kw.value:
        modifiers.append(kw.value)
    type_node = TypeNode(name=typ.value) if typ and typ.value else None
    line = None
    col = None
    for part in (ident, typ, val, kw):
        if part is not None:
            line = part.line
            col = part.position
            break
    return ConstDeclNode(
        name=ident.value if ident else None,
        modifiers=modifiers,
        type_node=type_node,
        value=_int_literal_from_syntax(val),
        line=line,
        column=col,
    )


def build_ast_from_syntax_tree(root: Optional[SyntaxTreeNode]) -> Optional[Program]:
    if root is None:
        return None
    if root.node_type != "program":
        return Program(declarations=[_syntax_decl_to_ast(root)])
    decls = [
        _syntax_decl_to_ast(c)
        for c in root.children
        if c.node_type == "const_declaration"
    ]
    return Program(declarations=decls)


def _significant(tokens: List[Token]) -> List[Token]:
    out: List[Token] = []
    for t in tokens:
        if t.type in (TokenType.SPACE, TokenType.TAB, TokenType.NEWLINE):
            continue
        if t.is_error:
            continue
        out.append(t)
    return out


def _split_by_semicolon(sig: List[Token]) -> List[List[Token]]:
    chunks: List[List[Token]] = []
    cur: List[Token] = []
    for t in sig:
        if t.type == TokenType.SEMICOLON:
            if cur:
                chunks.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        chunks.append(cur)
    return chunks


def _refs_after_assign(chunk: List[Token]) -> List[Token]:
    refs: List[Token] = []
    eq_idx = None
    for i, t in enumerate(chunk):
        if t.type == TokenType.ASSIGN:
            eq_idx = i
            break
    if eq_idx is None:
        return refs
    i = eq_idx + 1
    while i < len(chunk):
        t = chunk[i]
        if t.type == TokenType.IDENTIFIER:
            refs.append(t)
        i += 1
    return refs


def _syntax_declarations(root: Optional[SyntaxTreeNode]) -> List[SyntaxTreeNode]:
    if root is None:
        return []
    if root.node_type != "program":
        if root.node_type == "const_declaration":
            return [root]
        return []
    return [c for c in root.children if c.node_type == "const_declaration"]


def format_ast_single_tree(program: Optional[Program]) -> str:
    if program is None:
        return "(нет дерева разбора)\n"
    if not program.declarations:
        return "Program\n└── (нет объявлений)\n"
    out: List[str] = ["Program"]
    nd = len(program.declarations)
    for di, decl in enumerate(program.declarations):
        last_decl = di == nd - 1
        p = "└── " if last_decl else "├── "
        out.append(p + "ConstDeclNode")
        bar = "    " if last_decl else "│   "
        out.append(bar + "├── " + (f'name: "{decl.name}"' if decl.name else "name: null"))
        out.append(bar + "├── " + f"modifiers: {decl.modifiers!r}")
        if decl.type_node is not None:
            out.append(bar + "├── " + "type: TypeNode")
            out.append(bar + "│   " + "└── " + f'name: "{decl.type_node.name}"')
        else:
            out.append(bar + "├── " + "type: null")
        if decl.value is not None:
            out.append(bar + "└── " + "value: IntegerLiteralNode")
            out.append(bar + "    " + "└── " + f"value: {decl.value.value}")
        else:
            out.append(bar + "└── " + "value: null")
    return "\n".join(out) + "\n"


def analyze_semantics_from_parse(
    tokens: List[Token],
    syntax_tree: Optional[SyntaxTreeNode],
    syntax_errors: List[ParserError],
) -> Tuple[Optional[Program], Optional[Program], List[SemanticError], List[ParserError]]:
    full_ast = build_ast_from_syntax_tree(syntax_tree)

    sem_errors: List[SemanticError] = []
    decl_faulty: set = set()

    sig = _significant(tokens)
    chunks = _split_by_semicolon(sig)
    decl_nodes = _syntax_declarations(syntax_tree)

    symbols: Dict[str, Tuple[int, int]] = {}

    n = max(len(chunks), len(decl_nodes))
    for idx in range(n):
        chunk = chunks[idx] if idx < len(chunks) else None
        syn = decl_nodes[idx] if idx < len(decl_nodes) else None

        ident_n = _syntax_child(syn, "identifier") if syn else None
        type_n = _syntax_child(syn, "type") if syn else None
        val_n = _syntax_child(syn, "value") if syn else None

        name = ident_n.value if ident_n and ident_n.value else None
        typ = type_n.value if type_n and type_n.value else None
        ival = _literal_int(val_n)

        name_line = ident_n.line if ident_n else 0
        name_col = ident_n.position if ident_n else 0

        if name and name in symbols:
            prev_line = symbols[name][0]
            sem_errors.append(
                SemanticError(
                    f'Ошибка: идентификатор "{name}" уже объявлен ранее (строка {prev_line})',
                    name_line,
                    name_col,
                    fragment=name,
                )
            )
            decl_faulty.add(idx)
            continue

        if typ and ival is not None and typ in TYPE_RANGE:
            lo, hi = TYPE_RANGE[typ]
            if not (lo <= ival <= hi):
                vc = val_n.position if val_n else name_col
                vl = val_n.line if val_n else name_line
                frag = val_n.value if val_n and val_n.value else str(ival)
                sem_errors.append(
                    SemanticError(
                        f"Ошибка: значение {ival} вне допустимого диапазона для типа {typ} "
                        f"([{lo}, {hi}]); несовместимость типа инициализатора",
                        vl,
                        vc,
                        fragment=frag,
                    )
                )
                decl_faulty.add(idx)
        elif typ and ival is not None and typ not in TYPE_RANGE:
            sem_errors.append(
                SemanticError(
                    f"Ошибка: неизвестный тип {typ} для проверки диапазона",
                    type_n.line if type_n else name_line,
                    type_n.position if type_n else name_col,
                    fragment=typ,
                )
            )
            decl_faulty.add(idx)

        if chunk:
            for ref in _refs_after_assign(chunk):
                if ref.value not in symbols:
                    sem_errors.append(
                        SemanticError(
                            f'Ошибка: идентификатор "{ref.value}" используется без предшествующего объявления',
                            ref.line,
                            ref.start_pos,
                            fragment=ref.value,
                        )
                    )
                    decl_faulty.add(idx)

        if name and idx not in decl_faulty:
            symbols[name] = (name_line, name_col)

    valid_decls: List[ConstDeclNode] = []
    if full_ast:
        for i, d in enumerate(full_ast.declarations):
            if i not in decl_faulty:
                valid_decls.append(d)

    valid_ast: Optional[Program] = None
    if full_ast is not None:
        valid_ast = Program(declarations=valid_decls)

    return full_ast, valid_ast, sem_errors, syntax_errors


def analyze_semantics(
    source: str,
) -> Tuple[Optional[Program], Optional[Program], List[SemanticError], List[ParserError]]:
    tokens = LexicalAnalyzer().analyze(source)
    syntax_tree, syntax_errors = Parser().parse(tokens)
    return analyze_semantics_from_parse(tokens, syntax_tree, syntax_errors)


def format_analysis_report(
    full_ast: Optional[Program],
    valid_ast: Optional[Program],
    sem_errs: List[SemanticError],
    syn_errs: List[ParserError],
) -> str:
    parts: List[str] = []
    parts.append("=== AST ===")
    parts.append(format_ast_single_tree(full_ast))
    parts.append("")
    parts.append("=== Семантические ошибки ===")
    if not sem_errs:
        parts.append("(нет)")
    else:
        for e in sem_errs:
            parts.append(e.format_line())
    parts.append(f"Количество семантических ошибок: {len(sem_errs)}")
    parts.append("")
    parts.append("=== Синтаксические ошибки ===")
    if not syn_errs:
        parts.append("(нет)")
    else:
        for e in syn_errs:
            parts.append(f"{e.description} | строка {e.line}, символ {e.position}")
    parts.append(f"Количество синтаксических ошибок: {len(syn_errs)}")
    return "\n".join(parts)


def run_analysis(source: str) -> str:
    t = analyze_semantics(source)
    return format_analysis_report(t[0], t[1], t[2], t[3])


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sample = (
        "const MARKS: i32 = 100;\n"
        "const OTHER: u8 = 300;\n"
        "const MARKS: i32 = 20;\n"
        "const X: i32 = Y;\n"
        "const Y: i32 = 1;\n"
    )
    print(run_analysis(sample))
