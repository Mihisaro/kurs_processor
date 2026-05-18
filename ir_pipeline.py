from __future__ import annotations

from typing import List, Optional

from ir_codegen import format_tac_block, generate_tac
from ir_optimize import OPT1_NAME, OPT2_NAME, apply_optimizations
from semantic_analysis import Program, format_ast_single_tree


def _empty_ir_hint(
    source: str,
    full_ast: Optional[Program],
    syntax_error_count: int,
    semantic_error_count: int,
) -> str:
    lines = [
        "Нет корректных объявлений для генерации IR.",
        "",
        "В верхнем редакторе должен быть ИСХОДНЫЙ КОД, а не TAC.",
        "Пример:",
        "  const MARKS: i32 = 100;",
        "",
        "Цепочка: исходник → лексика → синтаксис → AST → IR → оптимизации.",
    ]
    low = source.lower()
    if "const" not in low and ("= " in source or "type(" in source):
        lines.extend([
            "",
            "Похоже, введён уже промежуточный код (t0 = …, MARKS = t0, type(…) = …).",
            "Такой текст парсер не разбирает — вставьте объявление const … ; и нажмите F5.",
        ])
    if syntax_error_count:
        lines.append(f"Синтаксических ошибок: {syntax_error_count} — см. вкладку «Синтаксический анализ».")
    if semantic_error_count:
        lines.append(f"Семантических ошибок: {semantic_error_count} — см. вкладку «Семантика и AST».")
    if full_ast and full_ast.declarations and semantic_error_count:
        lines.append("AST построен частично, но объявления отмечены как ошибочные.")
    return "\n".join(lines)


def format_ir_pipeline_report(
    valid_ast: Optional[Program],
    *,
    full_ast: Optional[Program] = None,
    source: str = "",
    syntax_error_count: int = 0,
    semantic_error_count: int = 0,
) -> str:
    parts: List[str] = []

    parts.append("=== Абстрактное синтаксическое дерево (AST) ===")
    ast_show = valid_ast if (valid_ast and valid_ast.declarations) else full_ast
    parts.append(format_ast_single_tree(ast_show).rstrip())
    parts.append("")

    if valid_ast is None or not valid_ast.declarations:
        parts.append("=== Промежуточное представление (IR) ===")
        parts.append(_empty_ir_hint(source, full_ast, syntax_error_count, semantic_error_count))
        return "\n".join(parts) + "\n"

    raw, opt1, opt2 = apply_optimizations(generate_tac(valid_ast))

    parts.append(format_tac_block("=== Исходный IR (трёхадресный код, TAC) ===", raw))
    parts.append("")
    parts.append(format_tac_block(f"=== После оптимизации 1: {OPT1_NAME} ===", opt1))
    parts.append("")
    parts.append(format_tac_block(f"=== После оптимизации 2: {OPT2_NAME} ===", opt2))
    parts.append("")
    parts.append("=== Каноническая строка (результат) ===")
    if opt2 and opt2[0].op == "CONST_DECL":
        ins = opt2[0]
        parts.append(f"const {ins.arg1} : {ins.arg2} = {ins.arg3};")
    else:
        parts.append("(не удалось построить)")

    return "\n".join(parts) + "\n"
