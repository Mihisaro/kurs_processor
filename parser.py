import re
from typing import List, Optional

from lexical_analyzer import (
    DATA_TYPE_NAMES,
    Token,
    TokenType,
    _is_float_error_lexeme,
)

SYNC_TOKENS = {TokenType.SEMICOLON, TokenType.CONST}


class ParserError:
    def __init__(self, fragment, line, position, description, *, cursor_only=False):
        self.fragment = fragment
        self.line = line
        self.position = position
        self.description = description
        self.cursor_only = cursor_only

    def __str__(self):
        return (f"[строка {self.line}, позиция {self.position}] "
                f"{self.description}: '{self.fragment}'")


class SyntaxTreeNode:
    def __init__(self, node_type, value=None, line=None, position=None):
        self.node_type = node_type
        self.value = value
        self.line = line
        self.position = position
        self.children = []

    def add_child(self, child):
        if child:
            self.children.append(child)

    def __str__(self, level=0):
        indent = "  " * level
        result = f"{indent}{self.node_type}"
        if self.value:
            result += f": {self.value}"
        if self.line:
            result += f" (строка {self.line})"
        result += "\n"
        for child in self.children:
            result += child.__str__(level + 1)
        return result


def _lexical_error_message(token: Token) -> str:
    if _is_float_error_lexeme(token.value):
        return (
            f"Дробное число '{token.value}' недопустимо: используйте целое число"
        )
    msg = f"Лексическая ошибка: недопустимый символ '{token.value}'"
    if token.value == "#":
        msg += " (лишний знак внутри слова или числа)"
    return msg


def _tokens_adjacent(a: Token, b: Token) -> bool:
    """Смежные значимые лексемы: на одной строке без пробела/разрыва между ними."""
    return a.line == b.line and (a.end_pos + 1) == b.start_pos


def _token_kind_ru(t: Optional[Token]) -> str:
    if t is None:
        return "конец ввода"
    if t.is_error:
        return f"лексическая ошибка '{t.value}'"
    names = {
        TokenType.CONST: "ключевое слово 'const'",
        TokenType.IDENTIFIER: "идентификатор",
        TokenType.COLON: "символ ':'",
        TokenType.TYPE: "тип данных",
        TokenType.ASSIGN: "символ '='",
        TokenType.NUMBER: "числовой литерал",
        TokenType.SEMICOLON: "символ ';'",
    }
    return names.get(t.type, t.type.name)


def _expected_ru(state: int) -> str:
    return {
        0: "ключевое слово 'const'",
        1: "идентификатор",
        2: "символ ':'",
        3: "тип данных",
        4: "символ '='",
        5: "числовой литерал",
        6: "символ ';'",
    }[state]


def _levenshtein(a: str, b: str) -> int:
    a, b = a.lower(), b.lower()
    la, lb = len(a), len(b)
    row = list(range(lb + 1))
    for i in range(1, la + 1):
        prev = row[0]
        row[0] = i
        for j in range(1, lb + 1):
            cur = row[j]
            cost = 0 if a[i - 1] == b[j - 1] else 1
            row[j] = min(row[j] + 1, row[j - 1] + 1, prev + cost)
            prev = cur
    return row[lb]


def _is_likely_const_typo(word: str) -> bool:
    if not word or word.lower() == "const":
        return False
    if len(word) < 3 or len(word) > 6:
        return False
    return _levenshtein(word, "const") <= 1


def _is_valid_data_type_name(name: str) -> bool:
    return name.lower() in DATA_TYPE_NAMES


def _alnum_data_type_spelling(raw: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", raw or "").lower()


def _alnum_ident_error_run(sig: List[Token], start: int):
    """Подряд идентификаторов и лексических ошибок до первого «разделителя»."""
    j = start
    toks: List[Token] = []
    while j < len(sig):
        tt = sig[j].type
        if tt in (TokenType.IDENTIFIER, TokenType.ERROR):
            toks.append(sig[j])
            j += 1
            continue
        break
    if not toks:
        return "", j, []
    raw = "".join(x.value for x in toks)
    return raw, j, toks


def _merge_identifier_with_embedded_errors(sig: List[Token], start: int):
    """
    Имя с вкраплениями (MAR#KS), без склейки двух соседних идентификаторов (MARKS и i2).
    """
    if start >= len(sig) or sig[start].type != TokenType.IDENTIFIER:
        return None
    parts: List[Token] = [sig[start]]
    j = start + 1

    def _adj(a: Token, b: Token) -> bool:
        return a.line == b.line and (a.end_pos + 1) == b.start_pos

    while j < len(sig):
        if sig[j].type == TokenType.ERROR:
            # Любой недопустимый символ "внутри слова" (без пробелов) склеиваем,
            # а самостоятельные (с пробелами/разделителями) — нет.
            if not _adj(parts[-1], sig[j]):
                break
            parts.append(sig[j])
            j += 1
            continue
        if sig[j].type in (TokenType.SEMICOLON, TokenType.COLON, TokenType.ASSIGN):
            # Склеиваем подряд идущие разделители внутри "слова" (MA::RKS, MA==RKS, MA;;RKS ...),
            # но только когда далее действительно идёт ':' объявления (MA::RKS: ...).
            k = j
            while (
                k < len(sig)
                and sig[k].type in (TokenType.SEMICOLON, TokenType.COLON, TokenType.ASSIGN)
                and _adj(parts[-1] if k == j else sig[k - 1], sig[k])
            ):
                k += 1
            if (
                k < len(sig)
                and sig[k].type == TokenType.IDENTIFIER
                and _adj(sig[k - 1], sig[k])
                and (k + 1) < len(sig)
                and sig[k + 1].type == TokenType.COLON
            ):
                nxt_id = sig[k]
                # «MARKS:i…» — одна буква после «:» чаще всего начало типа (i32), не часть имени.
                if len(nxt_id.value) < 2:
                    break
                if re.search(r"\d", nxt_id.value):
                    break
                parts.extend(sig[j:k])
                parts.append(nxt_id)
                j = k + 1
                continue
        if (
            sig[j].type == TokenType.IDENTIFIER
            and parts[-1].type == TokenType.ERROR
        ):
            if re.search(r"\d", sig[j].value):
                break
            parts.append(sig[j])
            j += 1
            continue
        break
    if len(parts) == 1:
        return None
    if parts[-1].type == TokenType.ERROR:
        return None
    raw = "".join(x.value for x in parts)
    return raw, j, parts


def _letters_only_az(s: str) -> str:
    return re.sub(r"[^A-Za-z]", "", s).lower()


class Parser:
    def __init__(self):
        self.significant_tokens: List[Token] = []
        self.position = 0
        self.current_token: Optional[Token] = None
        self.errors: List[ParserError] = []
        self.syntax_tree: Optional[SyntaxTreeNode] = None

    def _suppress_embedded_lex_errors(self, toks: List[Token]) -> None:
        """
        Удаляет из списка ошибок те лексические ошибки, которые находятся *внутри* «склеенного»
        токена (например, con#st, MAR#KS, i3'2, 10!0).

        Важно: одиночные/самостоятельные лексические ошибки (между токенами, разделённые
        пробелами и т.п.) не подавляются — только те, что попали в кластер `toks`.
        """
        drop = {(t.line, t.start_pos) for t in toks if t.is_error}
        if not drop:
            return
        self.errors = [
            e for e in self.errors
            if not (
                (e.line, e.position) in drop
                and e.description.startswith("Лексическая ошибка")
            )
        ]

    def parse(self, tokens):
        self.errors = []
        self.position = 0

        lex_errors: List[ParserError] = []
        for token in tokens:
            if token.is_error:
                lex_errors.append(ParserError(
                    token.value,
                    token.line,
                    token.start_pos,
                    _lexical_error_message(token),
                ))

        self.significant_tokens = [
            t for t in tokens
            if t.type not in (TokenType.SPACE, TokenType.TAB, TokenType.NEWLINE)
        ]

        self.errors.extend(lex_errors)

        if not self.significant_tokens:
            self.errors.sort(key=lambda e: (e.line, e.position))
            return None, self.errors

        self._update()
        root = SyntaxTreeNode("program")

        while self.current_token:
            pos_before = self.position
            decl = self._parse_one_declaration_fsm()
            if decl is not None:
                root.add_child(decl)
                self._flush_trailing_until_next_const()
            if self.position == pos_before:
                self._advance()

        self.syntax_tree = root
        self.errors.sort(key=lambda e: (e.line, e.position))
        return root, self.errors

    def _flush_trailing_until_next_const(self) -> None:
        """После успешного «... ;» всё до следующего const — недопустимый хвост (не новое объявление)."""
        if not self.current_token or self.current_token.type == TokenType.CONST:
            return
        start = self.current_token
        parts: List[str] = []
        spanned_lex: List[Token] = []
        while self.current_token and self.current_token.type != TokenType.CONST:
            t = self.current_token
            if t.is_error:
                parts.append(t.value)
                spanned_lex.append(t)
                self._advance()
                continue
            if t.type == TokenType.SEMICOLON:
                parts.append(";")
                self._advance()
                continue
            parts.append(t.value)
            self._advance()
        combined = " ".join(parts) if parts else start.value
        # Если мы показываем общий синтаксический фрагмент, лексические ошибки внутри этого хвоста
        # в синтаксической таблице не дублируем.
        self._suppress_embedded_lex_errors(spanned_lex)
        self.errors.append(ParserError(
            combined,
            start.line,
            start.start_pos,
            "После «;» объявление константы уже завершено. Недопустимый фрагмент "
            f"«{combined}» (далее — только новое объявление с «const» или конец ввода).",
        ))

    def _misplaced_semicolon(self, t: Token) -> None:
        # Объединяем подряд идущие ';' в одну ошибку.
        first = t
        count = 0
        while self._cur_is(TokenType.SEMICOLON):
            count += 1
            self._advance()
        frag = ";" * max(1, count)
        self.errors.append(ParserError(
            frag,
            first.line,
            first.start_pos,
            "Символ ';' допустим только в конце объявления константы "
            "(сразу после числового литерала, без лишнего кода после него)",
        ))

    def _peek_token(self, offset: int) -> Optional[Token]:
        idx = self.position + offset
        if idx < len(self.significant_tokens):
            return self.significant_tokens[idx]
        return None

    def _peek_is(self, offset: int, token_type) -> bool:
        tok = self._peek_token(offset)
        return tok is not None and tok.type == token_type

    def _gap(self, a: Token, b: Token) -> bool:
        """Есть пробел(ы) между значимыми лексемами на одной строке."""
        return a is not None and b is not None and a.line == b.line and b.start_pos > (a.end_pos + 1)

    def _try_recover_split_const_keyword(self, children: List[SyntaxTreeNode]) -> bool:
        """con#st → буквы «const»: синтаксическая ошибка на фрагмент (лексика по # уже есть)."""
        sig = self.significant_tokens
        idx = self.position
        if idx >= len(sig):
            return False
        toks: List[Token] = []
        j = idx

        def _adj(a: Token, b: Token) -> bool:
            return a.line == b.line and (a.end_pos + 1) == b.start_pos

        def _gap(a: Token, b: Token) -> bool:
            return a.line == b.line and b.start_pos > (a.end_pos + 1)

        while j < len(sig):
            t = sig[j]
            # Как только уже набрали «const» по буквам — дальше ничего не поглощаем.
            # Иначе можно «съесть» следующий мусорный символ/следующее слово (например, con#st ) MAR...).
            if toks and _letters_only_az("".join(x.value for x in toks)) == "const":
                break
            if t.type == TokenType.ERROR:
                # Любой недопустимый символ "внутри слова" (без пробелов) считаем частью испорченного const.
                # А если он отделён пробелом — не поглощаем.
                if toks and not _adj(toks[-1], t):
                    break
                toks.append(t)
                j += 1
                continue
            if t.type == TokenType.SEMICOLON:
                toks.append(t)
                j += 1
                continue
            if t.type == TokenType.COLON:
                toks.append(t)
                j += 1
                continue
            if t.type == TokenType.ASSIGN:
                toks.append(t)
                j += 1
                continue
            if t.type == TokenType.IDENTIFIER:
                if toks and toks[-1].type == TokenType.IDENTIFIER:
                    # Разрешаем «con st» (лишний пробел внутри const), но не склеиваем прочие пары слов.
                    if (
                        len(toks) == 1
                        and _gap(toks[-1], t)
                        and (_letters_only_az(toks[-1].value + t.value) == "const")
                    ):
                        toks.append(t)
                        j += 1
                        continue
                    break
                toks.append(t)
                j += 1
                continue
            break
        if not toks:
            return False
        # «con st» (лишний пробел внутри ключевого слова) — отдельная, более понятная ошибка.
        if (
            len(toks) == 2
            and toks[0].type == TokenType.IDENTIFIER
            and toks[1].type == TokenType.IDENTIFIER
            and self._gap(toks[0], toks[1])
            and (_letters_only_az(toks[0].value + toks[1].value) == "const")
        ):
            raw_spaced = f"{toks[0].value} {toks[1].value}"
            self.errors.append(ParserError(
                raw_spaced,
                toks[0].line,
                toks[0].start_pos,
                "Лишний пробел внутри ключевого слова «const» (напишите «const» одним словом)",
            ))
            self.position = idx + 2
            self._update()
            children.append(SyntaxTreeNode(
                "keyword", "const", toks[0].line, toks[0].start_pos))
            return True
        raw = "".join(x.value for x in toks)
        letters = _letters_only_az(raw)
        if letters != "const" and _levenshtein(letters, "const") > 1:
            return False
        if len(toks) == 1 and toks[0].type == TokenType.IDENTIFIER and _is_likely_const_typo(raw):
            return False
        if raw.lower() == "const" and not any(
            t.is_error
            or t.type in (TokenType.SEMICOLON, TokenType.COLON, TokenType.ASSIGN)
            for t in toks
        ):
            return False
        # Лексические ошибки внутри «con#st» и т.п. не показываем в синтаксическом анализе.
        self._suppress_embedded_lex_errors(toks)
        self.errors.append(ParserError(
            raw,
            toks[0].line,
            toks[0].start_pos,
            f"Ожидалось ключевое слово «const», получено «{raw}» "
            "(напишите const одним словом без «=», «:», «;» и посторонних символов между буквами).",
        ))
        self.position = j
        self._update()
        children.append(SyntaxTreeNode(
            "keyword", "const", toks[0].line, toks[0].start_pos))
        return True

    def _gather_mangled_type_token_cluster(
        self, idx: int
    ) -> Optional[tuple]:
        """
        «i3'2» / «i3;2» / «i!3"2» / … перед «=»: неверный префикс типа + «мусор» (ERROR/цифры/;/:),
        затем ASSIGN значения.
        Как con'st для const — одна синтаксическая ошибка на весь фрагмент.
        """
        sig = self.significant_tokens
        if idx >= len(sig):
            return None
        t0 = sig[idx]
        if t0.type != TokenType.IDENTIFIER or _is_valid_data_type_name(t0.value):
            return None
        toks: List[Token] = [t0]
        j = idx + 1

        def _adj(a: Token, b: Token) -> bool:
            return a.line == b.line and (a.end_pos + 1) == b.start_pos

        used_equals_glue = False
        had_semicolon_or_colon_glue = False
        if j >= len(sig):
            return None
        if sig[j].type in (TokenType.SEMICOLON, TokenType.COLON):
            # Разрешаем несколько подряд идущих ':'/';' внутри типа: i:::32, i;;;32 ...
            while j < len(sig) and sig[j].type in (TokenType.SEMICOLON, TokenType.COLON):
                if toks and not _adj(toks[-1], sig[j]):
                    break
                toks.append(sig[j])
                j += 1
            had_semicolon_or_colon_glue = True
        elif sig[j].type == TokenType.ASSIGN:
            toks.append(sig[j])
            j += 1
            if j >= len(sig) or sig[j].type != TokenType.NUMBER:
                return None
            toks.append(sig[j])
            j += 1
            used_equals_glue = True
        while j < len(sig) and sig[j].type in (
            TokenType.ERROR,
            TokenType.NUMBER,
            TokenType.COLON,
            TokenType.SEMICOLON,
            TokenType.ASSIGN,
        ):
            if toks and not _adj(toks[-1], sig[j]):
                break
            if sig[j].type == TokenType.ASSIGN:
                used_equals_glue = True
            toks.append(sig[j])
            j += 1
        if j >= len(sig) or sig[j].type != TokenType.ASSIGN:
            return None
        if not (
            used_equals_glue
            or had_semicolon_or_colon_glue
            or any(t.is_error for t in toks[1:])
        ):
            return None
        raw = "".join(x.value for x in toks)
        alnum = _alnum_data_type_spelling(raw)
        ast_name = alnum if alnum in DATA_TYPE_NAMES else t0.value
        return raw, j, ast_name, toks

    def _gather_mangled_int_literal_cluster(self, idx: int) -> Optional[tuple]:
        """
        «10!0;» — между цифрами лексические ERROR; одна синтаксическая ошибка на весь литерал,
        без каскада «лишний фрагмент 0» после пропуска «!».
        """
        sig = self.significant_tokens
        if idx >= len(sig) or sig[idx].type != TokenType.NUMBER:
            return None
        parts: List[Token] = [sig[idx]]
        j = idx + 1
        had_error = False
        had_following_digits = False

        def _adj(a: Token, b: Token) -> bool:
            return a.line == b.line and (a.end_pos + 1) == b.start_pos

        while j < len(sig):
            if sig[j].is_error:
                if parts and not _adj(parts[-1], sig[j]):
                    break
                had_error = True
                parts.append(sig[j])
                j += 1
                continue
            if sig[j].type == TokenType.COLON:
                # ':' внутри числа допускаем только когда дальше слитно идут цифры (например, 1:::00).
                # Хвостовой ':' оставляем как отдельную ошибку (ожидалась ';', найдено ':').
                if parts and not _adj(parts[-1], sig[j]):
                    break
                nxt = sig[j + 1] if (j + 1) < len(sig) else None
                if nxt is None or nxt.type != TokenType.NUMBER or not _adj(sig[j], nxt):
                    break
                had_error = True
                parts.append(sig[j])
                j += 1
                continue
            if sig[j].type == TokenType.ASSIGN:
                if parts and not _adj(parts[-1], sig[j]):
                    break
                had_error = True
                parts.append(sig[j])
                j += 1
                continue
            if sig[j].type == TokenType.NUMBER:
                if parts and not _adj(parts[-1], sig[j]):
                    break
                had_following_digits = True
                parts.append(sig[j])
                j += 1
                continue
            break
        # Считаем испорченным числом только случаи «цифры + ERROR + цифры» (например, 10#0),
        # но не хвостовой мусор после числа (например, 100").
        if not (had_error and had_following_digits):
            return None
        # Допускаем как «...;», так и EOF/CONST/':' после литерала: тогда завершающий символ
        # будет обработан отдельно (например, ошибка «ожидалась ;, найдено :»).
        if j < len(sig) and sig[j].type not in (TokenType.SEMICOLON, TokenType.CONST, TokenType.COLON):
            return None
        raw = "".join(x.value for x in parts)
        digits = re.sub(r"\D", "", raw) or "0"
        return raw, j, digits, parts, parts[0].line, parts[0].start_pos, parts[-1].end_pos

    def _parse_one_declaration_fsm(self) -> Optional[SyntaxTreeNode]:
        state = 0
        decl = SyntaxTreeNode("const_declaration")
        children: List[SyntaxTreeNode] = []
        ident_tok: Optional[Token] = None
        type_tok: Optional[Token] = None
        value_tok: Optional[Token] = None
        missing_const_reported = False

        while state <= 6:
            t = self.current_token
            if t is None:
                if state == 6:
                    anchor = (
                        value_tok
                        or type_tok
                        or ident_tok
                        or (
                            self.significant_tokens[self.position - 1]
                            if self.position > 0 else None
                        )
                    )
                    if anchor:
                        self.errors.append(ParserError(
                            ";",
                            anchor.line,
                            anchor.end_pos + 1,
                            "Пропущена ';' в конце объявления: после значения константы "
                            "должна стоять точка с запятой",
                            cursor_only=True,
                        ))
                    else:
                        self._add_error_eof(state)
                    return None
                self._add_error_eof(state)
                return None

            if t.is_error:
                # Если после значения константы в конце стоит недопустимый символ,
                # показываем одну синтаксическую ошибку «ожидалась ;, найдено ...»
                if state == 6 and value_tok is not None:
                    self._suppress_embedded_lex_errors([t])
                    self.errors.append(ParserError(
                        t.value,
                        value_tok.line,
                        value_tok.end_pos + 1,
                        "Пропущена «;» в конце объявления после числового литерала; "
                        f"вместо «;» указан лишний фрагмент «{t.value}».",
                        cursor_only=True,
                    ))
                    self._advance()
                    while (
                        self.current_token
                        and self.current_token.type not in (
                            TokenType.SEMICOLON,
                            TokenType.CONST,
                        )
                    ):
                        self._advance()
                    if self._cur_is(TokenType.SEMICOLON):
                        self._consume_repeated_semicolon()
                        for c in children:
                            decl.add_child(c)
                        return decl
                    return None
                # Дробный литерал: только лексическая ошибка, без лишних синтаксических;
                # если после него нет «;» (часто EOF) — отдельно сообщаем о пропущенной «;».
                if state == 5 and _is_float_error_lexeme(t.value):
                    self._advance()
                    if not self._cur_is(TokenType.SEMICOLON):
                        self.errors.append(ParserError(
                            ";",
                            t.line,
                            t.end_pos + 1,
                            "Пропущена «;» в конце объявления: после значения константы "
                            "должна стоять точка с запятой",
                            cursor_only=True,
                        ))
                    self._irons_sync_after_error()
                    return None
                # «i32 ! 100», «i32 !=! 100» — мусор вместо «=» до литерала: одна синтаксическая ошибка.
                if state == 4 and type_tok is not None:
                    got = self._mangled_assign_cluster_before_number(
                        self.significant_tokens, self.position)
                    if got is not None:
                        raw, k, err_toks = got
                        self._suppress_embedded_lex_errors(err_toks)
                        first_t = self.significant_tokens[self.position]
                        self.errors.append(ParserError(
                            raw,
                            first_t.line,
                            first_t.start_pos,
                            f"Ожидался символ «=», найдено «{raw}»",
                        ))
                        self.position = k
                        self._update()
                        state = 5
                        continue
                # Иначе: сообщение о лексеме ERROR уже в parse(); пропускаем и продолжаем FSM.
                self._advance()
                continue

            # «... = ;» — пропущен числовой литерал, но ';' на месте.
            if state == 5 and t.type == TokenType.SEMICOLON:
                anchor = (
                    type_tok
                    or ident_tok
                    or (
                        self.significant_tokens[self.position - 1]
                        if self.position > 0 else None
                    )
                )
                if anchor:
                    self.errors.append(ParserError(
                        "<число>",
                        anchor.line,
                        anchor.end_pos + 1,
                        "Пропущен числовой литерал инициализатора после «=»",
                        cursor_only=True,
                    ))
                else:
                    self.errors.append(ParserError(
                        "<число>",
                        0,
                        0,
                        "Пропущен числовой литерал инициализатора после «=»",
                        cursor_only=True,
                    ))
                self._consume_repeated_semicolon()
                for c in children:
                    decl.add_child(c)
                return decl

            if t.type == TokenType.SEMICOLON and state != 6:
                self._misplaced_semicolon(t)
                continue

            if state == 0:
                if t.type == TokenType.CONST:
                    first = self._consume()
                    extra = 0
                    while self._cur_is(TokenType.CONST):
                        extra += 1
                        self._consume()
                    if extra:
                        self.errors.append(ParserError(
                            "const",
                            first.line,
                            first.start_pos,
                            f"Лишние ключевые слова 'const' подряд ({extra + 1} раз): "
                            f"перед именем допускается только одно 'const'",
                        ))
                    children.append(SyntaxTreeNode(
                        "keyword", first.value, first.line, first.start_pos))
                    state = 1
                    continue
                if self._try_recover_split_const_keyword(children):
                    state = 1
                    continue
                if t.type == TokenType.IDENTIFIER and _is_likely_const_typo(t.value):
                    self.errors.append(ParserError(
                        t.value,
                        t.line,
                        t.start_pos,
                        f"В ключевом слове опечатка: «{t.value}» вместо «const» "
                        f"(имя константы задаётся отдельным идентификатором после «const»)",
                    ))
                    children.append(SyntaxTreeNode(
                        "keyword", "const", t.line, t.start_pos))
                    self._consume()
                    state = 1
                    continue
                if t.type == TokenType.TYPE:
                    nxt = self._peek_token(1)
                    # Лишняя лексема перед «const»: «i32 const ...»
                    if nxt is not None and nxt.type == TokenType.CONST:
                        self.errors.append(ParserError(
                            t.value,
                            t.line,
                            t.start_pos,
                            f"Лишняя лексема перед «const»: тип данных «{t.value}»",
                        ))
                        self._consume()
                        continue
                    self.errors.append(ParserError(
                        t.value,
                        t.line,
                        t.start_pos,
                        f"Ожидался ключевое слово 'const', найден тип данных «{t.value}»",
                    ))
                    missing_const_reported = True
                    if nxt is not None and nxt.type == TokenType.COLON:
                        self.errors.append(ParserError(
                            t.value,
                            t.line,
                            t.end_pos + 1,
                            "Пропущен идентификатор имени константы: перед «:» должно быть "
                            "имя константы, а не тип данных",
                            cursor_only=True,
                        ))
                        children.append(SyntaxTreeNode(
                            "keyword", "const", t.line, max(1, t.start_pos - 1)))
                        self._consume()
                        state = 2
                        continue
                    if nxt is not None and nxt.type == TokenType.IDENTIFIER:
                        self._consume()
                        continue
                    self._add_error_mismatch(0, t)
                    self._irons_sync_after_error()
                    return None
                if t.type == TokenType.IDENTIFIER:
                    # Без «const» тоже умеем склеивать испорченный идентификатор вида «MA!RKS»
                    # в одну синтаксическую ошибку (а лексические внутри — подавлять).
                    merged0 = _merge_identifier_with_embedded_errors(
                        self.significant_tokens, self.position)
                    if merged0 is not None:
                        raw0, end_idx0, toks0 = merged0
                        embedded0 = (
                            any(x.is_error for x in toks0)
                            or bool(re.search(r"[^0-9A-Za-z_]", raw0))
                        )
                        if embedded0:
                            if not missing_const_reported:
                                self.errors.append(ParserError(
                                    t.value,
                                    t.line,
                                    max(1, t.start_pos - 1),
                                    "Пропущено ключевое слово 'const' в начале объявления",
                                    cursor_only=True,
                                ))
                                missing_const_reported = True
                            children.append(SyntaxTreeNode(
                                "keyword", "const", t.line, max(1, t.start_pos - 1)))

                            clean0 = re.sub(r"[^0-9A-Za-z_]", "", raw0)
                            name0 = (
                                clean0
                                if clean0 and (clean0[0].isalpha() or clean0[0] == "_")
                                else (raw0 if raw0 else "?")
                            )
                            # Лексические ошибки внутри «MA!RKS» не дублируем в синтаксисе.
                            self._suppress_embedded_lex_errors(toks0)
                            self.errors.append(ParserError(
                                raw0,
                                toks0[0].line,
                                toks0[0].start_pos,
                                "Идентификатор имени константы содержит недопустимые символы "
                                f"(фрагмент «{raw0}»). Допустимы только буквы, цифры и «_».",
                            ))
                            ident_tok = Token(
                                TokenType.IDENTIFIER,
                                name0,
                                toks0[0].line,
                                toks0[0].start_pos,
                                toks0[-1].end_pos,
                            )
                            children.append(SyntaxTreeNode(
                                "identifier", ident_tok.value,
                                ident_tok.line, ident_tok.start_pos))
                            self.position = end_idx0
                            self._update()
                            state = 2
                            continue
                    t2 = self._peek_token(1)
                    if (
                        t2 is not None
                        and t2.type == TokenType.IDENTIFIER
                        and self._peek_is(2, TokenType.COLON)
                    ):
                        # «X Y:» без const: первое — не ключевое слово, второе — имя константы.
                        self.errors.append(ParserError(
                            t.value,
                            t.line,
                            t.start_pos,
                            f"Ожидалось ключевое слово «const»; в начале вместо него указано «{t.value}».",
                        ))
                        missing_const_reported = True
                        children.append(SyntaxTreeNode(
                            "keyword", "const", t.line, max(1, t.start_pos - 1)))
                        ident_tok = t2
                        children.append(SyntaxTreeNode(
                            "identifier", ident_tok.value,
                            ident_tok.line, ident_tok.start_pos))
                        self._consume()
                        self._consume()
                        state = 2
                        continue
                    if not missing_const_reported:
                        self.errors.append(ParserError(
                            t.value,
                            t.line,
                            max(1, t.start_pos - 1),
                            "Пропущено ключевое слово 'const' в начале объявления",
                            cursor_only=True,
                        ))
                    children.append(SyntaxTreeNode(
                        "keyword", "const", t.line, max(1, t.start_pos - 1)))
                    ident_tok = self._consume()
                    children.append(SyntaxTreeNode(
                        "identifier", ident_tok.value,
                        ident_tok.line, ident_tok.start_pos))
                    state = 2
                    continue
                self._add_error_mismatch(state, t)
                self._irons_sync_after_error()
                return None

            if state == 1:
                t0 = self.current_token
                if t0 is None:
                    self._add_error_eof(1)
                    return None
                # «const MA RKS: ...» — лишний пробел в идентификаторе (склеиваем).
                if (
                    t0.type == TokenType.IDENTIFIER
                    and self._peek_is(1, TokenType.IDENTIFIER)
                    and self._peek_is(2, TokenType.COLON)
                    and self._gap(t0, self._peek_token(1))
                ):
                    t1 = self._peek_token(1)
                    assert t1 is not None
                    raw_spaced = f"{t0.value} {t1.value}"
                    merged = t0.value + t1.value
                    self.errors.append(ParserError(
                        raw_spaced,
                        t0.line,
                        t0.start_pos,
                        "Лишний пробел внутри идентификатора имени константы (напишите имя одним словом)",
                    ))
                    ident_tok = Token(
                        TokenType.IDENTIFIER,
                        merged,
                        t0.line,
                        t0.start_pos,
                        t1.end_pos,
                    )
                    children.append(SyntaxTreeNode(
                        "identifier", ident_tok.value,
                        ident_tok.line, ident_tok.start_pos))
                    self._consume()
                    self._consume()
                    state = 2
                    continue
                # «const 100: ...» — число вместо имени константы. Сообщаем и восстанавливаемся,
                # продолжая разбор как будто это идентификатор.
                if (
                    t0.type == TokenType.NUMBER
                    and self._peek_is(1, TokenType.COLON)
                ):
                    self.errors.append(ParserError(
                        t0.value,
                        t0.line,
                        t0.start_pos,
                        "Ожидался идентификатор, найден числовой литерал",
                    ))
                    ident_tok = Token(
                        TokenType.IDENTIFIER,
                        t0.value,
                        t0.line,
                        t0.start_pos,
                        t0.end_pos,
                    )
                    children.append(SyntaxTreeNode(
                        "identifier", ident_tok.value,
                        ident_tok.line, ident_tok.start_pos))
                    self._consume()  # number as name
                    state = 2
                    continue
                # Лишние '=' после «const»: «const == NAME ...»
                if t0.type == TokenType.ASSIGN:
                    first, count = self._consume_repeated_assign_run() or (t0, 1)
                    frag = "=" * max(1, count)
                    self.errors.append(ParserError(
                        frag,
                        first.line,
                        first.start_pos,
                        "Лишние символы '=' после «const» (здесь должно быть имя константы)",
                    ))
                    continue
                # Лишнее двоеточие сразу после «const»: «const : NAME: ...»
                if t0.type == TokenType.COLON:
                    first, count = self._consume_repeated_colon() or (t0, 1)
                    # «const : = 100;» — нет имени и типа, но дальше можно разобрать инициализатор.
                    if (
                        self.current_token
                        and self.current_token.type == TokenType.ASSIGN
                        and self._peek_is(1, TokenType.NUMBER)
                    ):
                        self.errors.append(ParserError(
                            "<идентификатор>",
                            first.line,
                            first.start_pos,
                            "Пропущен идентификатор имени константы после «const»",
                            cursor_only=True,
                        ))
                        self.errors.append(ParserError(
                            "<тип>",
                            first.line,
                            first.start_pos,
                            "Пропущен тип данных между ':' и '='",
                            cursor_only=True,
                        ))
                        ident_tok = Token(
                            TokenType.IDENTIFIER,
                            "?",
                            first.line,
                            first.start_pos,
                            first.start_pos,
                        )
                        children.append(SyntaxTreeNode(
                            "identifier", ident_tok.value,
                            ident_tok.line, ident_tok.start_pos))
                        type_tok = Token(
                            TokenType.TYPE,
                            "",
                            first.line,
                            first.start_pos,
                            first.start_pos,
                        )
                        children.append(SyntaxTreeNode(
                            "type", type_tok.value,
                            type_tok.line, type_tok.start_pos))
                        self._consume_repeated_assign()
                        state = 5
                        continue
                    # Если после ':' сразу идёт тип, то двоеточие "на месте", а ошибка — в пропущенном имени:
                    # «const : i32 = 100;»
                    if self.current_token and self.current_token.type == TokenType.TYPE:
                        self.errors.append(ParserError(
                            ":",
                            first.line,
                            first.start_pos,
                            "Пропущен идентификатор имени константы после «const»",
                            cursor_only=True,
                        ))
                        ident_tok = Token(
                            TokenType.IDENTIFIER,
                            "?",
                            first.line,
                            first.start_pos,
                            first.start_pos,
                        )
                        children.append(SyntaxTreeNode(
                            "identifier", ident_tok.value,
                            ident_tok.line, ident_tok.start_pos))
                        state = 3
                        continue
                    # «const : i3!!2 = ...» — после ':' идёт "сломаный" тип (лексика/цифры внутри),
                    # двоеточие на месте, а ошибка — в пропущенном имени.
                    if (
                        self.current_token
                        and self.current_token.type == TokenType.IDENTIFIER
                        and not self._peek_is(1, TokenType.COLON)
                    ):
                        self.errors.append(ParserError(
                            ":",
                            first.line,
                            first.start_pos,
                            "Пропущен идентификатор имени константы после «const»",
                            cursor_only=True,
                        ))
                        ident_tok = Token(
                            TokenType.IDENTIFIER,
                            "?",
                            first.line,
                            first.start_pos,
                            first.start_pos,
                        )
                        children.append(SyntaxTreeNode(
                            "identifier", ident_tok.value,
                            ident_tok.line, ident_tok.start_pos))
                        state = 3
                        continue
                    frag = ":" * max(1, count)
                    self.errors.append(ParserError(
                        frag,
                        first.line,
                        first.start_pos,
                        "Лишние двоеточия после «const» (здесь должно быть имя константы)",
                    ))
                    continue
                # «const i32 = 100» — пропущены имя и «:», тип стоит на месте имени.
                if (
                    t0.type == TokenType.TYPE
                    and _is_valid_data_type_name(t0.value)
                    and not self._peek_is(1, TokenType.COLON)
                ):
                    self.errors.append(ParserError(
                        t0.value,
                        t0.line,
                        t0.start_pos,
                        "Пропущен идентификатор имени константы после «const»; "
                        f"найден тип данных «{t0.value}».",
                    ))
                    self.errors.append(ParserError(
                        ":",
                        t0.line,
                        max(1, t0.start_pos - 1),
                        "Пропущено ':' между именем константы и типом данных",
                        cursor_only=True,
                    ))
                    # Восстановление: имя неизвестно, но тип известен — продолжаем разбор с '='.
                    ident_tok = Token(
                        TokenType.IDENTIFIER,
                        "?",
                        t0.line,
                        max(1, t0.start_pos - 1),
                        max(1, t0.start_pos - 1),
                    )
                    children.append(SyntaxTreeNode(
                        "identifier", ident_tok.value,
                        ident_tok.line, ident_tok.start_pos))
                    type_tok = t0
                    children.append(SyntaxTreeNode(
                        "type", type_tok.value,
                        type_tok.line, type_tok.start_pos))
                    self._consume()
                    state = 4
                    continue
                # «const i32: i32 = 100» — имя пропущено, но «: тип = число» на месте.
                # Первый i32 (TYPE) трактуем как имя с ошибкой (ожидался идентификатор),
                # чтобы продолжить разбор и увидеть ошибку про ';' в конце.
                if (
                    t0.type == TokenType.TYPE
                    and _is_valid_data_type_name(t0.value)
                    and self._peek_is(1, TokenType.COLON)
                    and not self._peek_is(2, TokenType.IDENTIFIER)
                ):
                    self.errors.append(ParserError(
                        t0.value,
                        t0.line,
                        t0.start_pos,
                        f"Ожидался идентификатор; вместо него указан тип данных «{t0.value}».",
                    ))
                    ident_tok = Token(
                        TokenType.IDENTIFIER,
                        t0.value,
                        t0.line,
                        t0.start_pos,
                        t0.end_pos,
                    )
                    children.append(SyntaxTreeNode(
                        "identifier", ident_tok.value,
                        ident_tok.line, ident_tok.start_pos))
                    self._consume()
                    state = 2
                    continue
                # «const i32: MARKS = …» — тип и имя перепутаны (норма: const MARKS: i32 = …).
                if (
                    t0.type == TokenType.TYPE
                    and _is_valid_data_type_name(t0.value)
                    and self._peek_is(1, TokenType.COLON)
                ):
                    t_name = self._peek_token(2)
                    if t_name is not None and t_name.type == TokenType.IDENTIFIER:
                        self.errors.append(ParserError(
                            t0.value,
                            t0.line,
                            t0.start_pos,
                            f"Ожидался идентификатор; вместо него указан тип данных «{t0.value}».",
                        ))
                        self.errors.append(ParserError(
                            t_name.value,
                            t_name.line,
                            t_name.start_pos,
                            f"Ожидался тип данных; вместо него указан идентификатор «{t_name.value}».",
                        ))
                        type_tok = t0
                        ident_tok = t_name
                        children.append(SyntaxTreeNode(
                            "identifier", ident_tok.value,
                            ident_tok.line, ident_tok.start_pos))
                        children.append(SyntaxTreeNode(
                            "type", type_tok.value,
                            type_tok.line, type_tok.start_pos))
                        self._consume()
                        self._consume()
                        self._consume()
                        self._update()
                        state = 4
                        continue
                if t0.type not in (TokenType.IDENTIFIER, TokenType.ERROR):
                    self._add_error_mismatch(state, t0)
                    self._irons_sync_after_error()
                    return None
                merged = _merge_identifier_with_embedded_errors(
                    self.significant_tokens, self.position)
                if merged is None:
                    if t0.type == TokenType.ERROR:
                        self._add_error_mismatch(state, t0)
                        self._irons_sync_after_error()
                        return None
                    ident_tok = self._consume()
                    children.append(SyntaxTreeNode(
                        "identifier", ident_tok.value,
                        ident_tok.line, ident_tok.start_pos))
                    state = 2
                    continue
                raw, end_idx, toks = merged
                embedded = (
                    any(x.is_error for x in toks)
                    or bool(re.search(r"[^0-9A-Za-z_]", raw))
                )
                clean = re.sub(r"[^0-9A-Za-z_]", "", raw)
                if embedded:
                    # Лексические ошибки внутри «MAR#KS», «MA;RKS», ... не дублируем в синтаксисе.
                    self._suppress_embedded_lex_errors(toks)
                    self.errors.append(ParserError(
                        raw,
                        toks[0].line,
                        toks[0].start_pos,
                        "Идентификатор имени константы содержит недопустимые символы "
                        f"(фрагмент «{raw}»). Допустимы только буквы, цифры и «_».",
                    ))
                name = (
                    clean
                    if clean and (clean[0].isalpha() or clean[0] == "_")
                    else (raw if raw else "?")
                )
                ident_tok = Token(
                    TokenType.IDENTIFIER,
                    name,
                    toks[0].line,
                    toks[0].start_pos,
                    toks[-1].end_pos,
                )
                self.position = end_idx
                self._update()
                children.append(SyntaxTreeNode(
                    "identifier", ident_tok.value,
                    ident_tok.line, ident_tok.start_pos))
                state = 2
                continue

            if state == 2:
                if (
                    ident_tok is not None
                    and t.type == TokenType.IDENTIFIER
                    and self._peek_is(1, TokenType.COLON)
                ):
                    # «const X Y:» — после имени допускается только «:», не второй идентификатор.
                    self.errors.append(ParserError(
                        t.value,
                        t.line,
                        t.start_pos,
                        "После имени константы должно следовать «:» с указанием типа; "
                        f"лишний идентификатор «{t.value}» перед «:».",
                    ))
                    self._consume()
                    continue
                if t.type == TokenType.COLON:
                    self._consume()
                    state = 3
                    continue
                if t.type == TokenType.TYPE and ident_tok is not None:
                    self.errors.append(ParserError(
                        ":",
                        ident_tok.line,
                        ident_tok.end_pos + 1,
                        "Пропущено ':' между именем константы и типом данных",
                        cursor_only=True,
                    ))
                    state = 3
                    continue
                if (
                    t.type == TokenType.IDENTIFIER
                    and ident_tok is not None
                ):
                    self.errors.append(ParserError(
                        ":",
                        ident_tok.line,
                        ident_tok.end_pos + 1,
                        "Пропущено ':' между именем константы и типом данных",
                        cursor_only=True,
                    ))
                    if not _is_valid_data_type_name(t.value):
                        self.errors.append(ParserError(
                            t.value,
                            t.line,
                            t.start_pos,
                            f"Ошибка в типе данных: «{t.value}» не является допустимым типом "
                            f"(ожидаются: {', '.join(sorted(DATA_TYPE_NAMES))})",
                        ))
                    type_tok = t
                    children.append(SyntaxTreeNode(
                        "type", type_tok.value, type_tok.line, type_tok.start_pos))
                    self._consume()
                    state = 4
                    continue
                self._add_error_mismatch(state, t)
                self._irons_sync_after_error()
                return None

            if state == 3:
                if t.type == TokenType.ASSIGN and self._peek_is(1, TokenType.NUMBER):
                    # «NAME: = 100;» — пропущен тип данных, но дальше можно разобрать инициализатор.
                    self.errors.append(ParserError(
                        "<тип>",
                        t.line,
                        t.start_pos,
                        "Пропущен тип данных между ':' и '='",
                        cursor_only=True,
                    ))
                    type_tok = Token(
                        TokenType.TYPE,
                        "",
                        t.line,
                        t.start_pos,
                        t.start_pos,
                    )
                    children.append(SyntaxTreeNode(
                        "type", type_tok.value,
                        type_tok.line, type_tok.start_pos))
                    self._consume_repeated_assign()
                    state = 5
                    continue
                if t.type == TokenType.COLON:
                    first, count = self._consume_repeated_colon() or (t, 1)
                    frag = ":" * max(1, count)
                    self.errors.append(ParserError(
                        frag,
                        first.line,
                        first.start_pos,
                        "Лишние двоеточия перед типом данных (после имени должен быть ровно один ':')",
                    ))
                    continue
                if t.type == TokenType.ASSIGN:
                    first, count = self._consume_repeated_assign_run() or (t, 1)
                    frag = "=" * max(1, count)
                    self.errors.append(ParserError(
                        frag,
                        first.line,
                        first.start_pos,
                        "Лишние символы '=' перед типом данных (после ':' должен идти тип, например i32)",
                    ))
                    continue
                if t.type == TokenType.TYPE:
                    type_tok = self._consume()
                    if not _is_valid_data_type_name(type_tok.value):
                        self.errors.append(ParserError(
                            type_tok.value,
                            type_tok.line,
                            type_tok.start_pos,
                            f"Ошибка в типе данных: «{type_tok.value}» не является допустимым типом "
                            f"(ожидаются: {', '.join(sorted(DATA_TYPE_NAMES))})",
                        ))
                    children.append(SyntaxTreeNode(
                        "type", type_tok.value, type_tok.line, type_tok.start_pos))
                    state = 4
                    continue
                if t.type == TokenType.IDENTIFIER:
                    # «...: i 32 = ...» — лишний пробел в имени типа (склеиваем i32).
                    if (
                        self._peek_is(1, TokenType.NUMBER)
                        and self._peek_token(1) is not None
                        and self._gap(t, self._peek_token(1))
                        and self._peek_is(2, TokenType.ASSIGN)
                    ):
                        t1 = self._peek_token(1)
                        assert t1 is not None
                        raw_spaced = f"{t.value} {t1.value}"
                        merged = (t.value + t1.value)
                        self.errors.append(ParserError(
                            raw_spaced,
                            t.line,
                            t.start_pos,
                            "Лишний пробел внутри имени типа данных (напишите тип одним словом, например i32)",
                        ))
                        type_tok = Token(
                            TokenType.TYPE,
                            merged,
                            t.line,
                            t.start_pos,
                            t1.end_pos,
                        )
                        children.append(SyntaxTreeNode(
                            "type", type_tok.value, type_tok.line, type_tok.start_pos))
                        self._consume()
                        self._consume()
                        state = 4
                        continue
                    mug = self._gather_mangled_type_token_cluster(self.position)
                    if mug is not None:
                        raw, assign_idx, ast_name, spanned = mug
                        exp = ", ".join(sorted(DATA_TYPE_NAMES))
                        # Лексические ошибки внутри «i3'2» и т.п. обычно не показываем в синтаксисе.
                        self._suppress_embedded_lex_errors(spanned)
                        self.errors.append(ParserError(
                            raw,
                            spanned[0].line,
                            spanned[0].start_pos,
                            f"Ожидался тип данных, получено «{raw}» "
                            "(напишите имя типа одним словом без «=», «:», «;», кавычек и посторонних символов "
                            "между буквами и цифрами). "
                            f"Допустимые имена: {exp}.",
                        ))
                        type_tok = Token(
                            TokenType.TYPE,
                            ast_name,
                            spanned[0].line,
                            spanned[0].start_pos,
                            spanned[-1].end_pos,
                        )
                        children.append(SyntaxTreeNode(
                            "type", type_tok.value,
                            type_tok.line, type_tok.start_pos))
                        self.position = assign_idx
                        self._update()
                        state = 4
                        continue
                    nxt = self._peek_token(1)
                    broken_type_then_lex = (
                        not _is_valid_data_type_name(t.value)
                        and nxt is not None
                        and nxt.is_error
                    )
                    if not _is_valid_data_type_name(t.value):
                        self.errors.append(ParserError(
                            t.value,
                            t.line,
                            t.start_pos,
                            f"Ошибка в типе данных: «{t.value}» не является допустимым типом "
                            f"(ожидаются: {', '.join(sorted(DATA_TYPE_NAMES))})",
                        ))
                    type_tok = t
                    children.append(SyntaxTreeNode(
                        "type", type_tok.value, type_tok.line, type_tok.start_pos))
                    self._consume()
                    if broken_type_then_lex:
                        # «i3'2» и т.п.: лексема ERROR уже в ошибках; не даём каскада про «=» и «;».
                        if self.current_token and self.current_token.is_error:
                            self._consume()
                        if (
                            self.current_token
                            and self.current_token.type == TokenType.NUMBER
                            and self._peek_is(1, TokenType.ASSIGN)
                        ):
                            self._consume()
                    state = 4
                    continue
                self._add_error_mismatch(state, t)
                self._irons_sync_after_error()
                return None

            if state == 4:
                if t.type == TokenType.COLON and type_tok is not None:
                    # «i32 : 100» — вместо «=» написано «:» перед литералом: одна ошибка, без каскада «пропущено =».
                    j = self.position
                    while (
                        j < len(self.significant_tokens)
                        and self.significant_tokens[j].type == TokenType.COLON
                    ):
                        j += 1
                    after_colons = (
                        self.significant_tokens[j] if j < len(self.significant_tokens) else None
                    )
                    if after_colons is not None and after_colons.type == TokenType.NUMBER:
                        first, count = self._consume_repeated_colon() or (t, 1)
                        frag = ":" * max(1, count)
                        msg = "Ожидался символ «=», найдено «:»"
                        if count > 1:
                            msg += f" ({count} раз подряд)"
                        self.errors.append(ParserError(
                            frag,
                            first.line,
                            first.start_pos,
                            msg,
                        ))
                        state = 5
                        continue
                    first, count = self._consume_repeated_colon() or (t, 1)
                    frag = ":" * max(1, count)
                    self.errors.append(ParserError(
                        frag,
                        first.line,
                        first.start_pos,
                        "Лишние двоеточия перед «=» (после типа должен быть оператор присваивания)",
                    ))
                    continue
                if t.type == TokenType.ASSIGN:
                    # «=!-», «=!», «=@@» и т.п. сразу после '=' (слитно) считаем одним неверным оператором
                    # присваивания, даже если дальше не число (чтобы не показывать отдельную лексику по ERROR).
                    nxt = self._peek_token(1)
                    # Если это случай вида «=!= 100» (есть продолжение до числа), пусть обработает
                    # _consume_repeated_assign через _mangled_assign_cluster_before_number.
                    if self._mangled_assign_cluster_before_number(
                        self.significant_tokens, self.position
                    ) is not None:
                        nxt = None
                    if (
                        nxt is not None
                        and nxt.is_error
                        and not _is_float_error_lexeme(nxt.value)
                        and _tokens_adjacent(t, nxt)
                        # «=-=» и т.п. оставляем для _consume_repeated_assign (он склеит в один оператор).
                        and not (
                            nxt.value == "-"
                            and self._peek_is(2, TokenType.ASSIGN)
                            and self._peek_token(2) is not None
                            and _tokens_adjacent(nxt, self._peek_token(2))
                        )
                    ):
                        sig = self.significant_tokens
                        j = self.position + 1
                        spanned_err: List[Token] = []
                        while (
                            j < len(sig)
                            and sig[j].is_error
                            and not _is_float_error_lexeme(sig[j].value)
                            and _tokens_adjacent(sig[j - 1], sig[j])
                        ):
                            spanned_err.append(sig[j])
                            j += 1
                        raw = "=" + "".join(x.value for x in spanned_err)
                        if spanned_err:
                            self._suppress_embedded_lex_errors(spanned_err)
                            self.errors.append(ParserError(
                                raw,
                                t.line,
                                t.start_pos,
                                f"Ожидался символ «=», найдено «{raw}»",
                            ))
                            self.position = j
                            self._update()
                            state = 5
                            continue
                    self._consume_repeated_assign()
                    state = 5
                    continue
                if t.type == TokenType.NUMBER and type_tok is not None:
                    self.errors.append(ParserError(
                        "=",
                        type_tok.line,
                        type_tok.end_pos + 1,
                        "Пропущено '=' между типом данных и числовым литералом",
                        cursor_only=True,
                    ))
                    state = 5
                    continue
                self._add_error_mismatch(state, t)
                self._irons_sync_after_error()
                return None

            if state == 5:
                # «... = 1 00;» — лишний пробел в числовом литерале (склеиваем 100).
                if (
                    t is not None
                    and t.type == TokenType.NUMBER
                    and self._peek_is(1, TokenType.NUMBER)
                    and self._peek_token(1) is not None
                    and self._gap(t, self._peek_token(1))
                ):
                    t1 = self._peek_token(1)
                    assert t1 is not None
                    merged = t.value + t1.value
                    raw_spaced = f"{t.value} {t1.value}"
                    self.errors.append(ParserError(
                        raw_spaced,
                        t.line,
                        t.start_pos,
                        "Лишний пробел внутри числового литерала (напишите число слитно, например 100)",
                    ))
                    value_tok = Token(
                        TokenType.NUMBER,
                        merged,
                        t.line,
                        t.start_pos,
                        t1.end_pos,
                    )
                    children.append(SyntaxTreeNode(
                        "value", value_tok.value, value_tok.line, value_tok.start_pos))
                    self._consume()
                    self._consume()
                    state = 6
                    continue
                lit = self._gather_mangled_int_literal_cluster(self.position)
                if lit is not None:
                    raw, j, digits, spanned, ln, spos, epos = lit
                    # Лексические ошибки внутри «10!0» и т.п. не показываем в синтаксисе.
                    self._suppress_embedded_lex_errors(spanned)
                    self.errors.append(ParserError(
                        raw,
                        ln,
                        spos,
                        "Ошибка в числовом литерале: допустимы только цифры целого числа; "
                        f"получено «{raw}».",
                    ))
                    value_tok = Token(
                        TokenType.NUMBER,
                        digits,
                        ln,
                        spos,
                        epos,
                    )
                    self.position = j
                    self._update()
                    children.append(SyntaxTreeNode(
                        "value", digits, ln, spos))
                    # Если дальше действительно стоит ';' — съедим её здесь.
                    # Иначе (EOF/const) ошибка про ';' будет добавлена в state==6.
                    if self._cur_is(TokenType.SEMICOLON):
                        self._consume_repeated_semicolon()
                        for c in children:
                            decl.add_child(c)
                        return decl
                    state = 6
                    continue
                while self.current_token and self.current_token.is_error:
                    self._advance()
                t = self.current_token
                if t is not None and t.type == TokenType.IDENTIFIER:
                    self.errors.append(ParserError(
                        t.value,
                        t.line,
                        t.start_pos,
                        f"Ошибка в числовом литерале: ожидалось целое число, получено «{t.value}».",
                    ))
                    self._irons_sync_after_error()
                    return None
                if t is None or t.type != TokenType.NUMBER:
                    self._add_error_mismatch(state, t)
                    # Если это последний токен (например, "... = i32" на EOF),
                    # дополнительно показываем, что отсутствует ';' в конце объявления.
                    if t is not None and self._peek_token(1) is None:
                        self.errors.append(ParserError(
                            ";",
                            t.line,
                            t.end_pos + 1,
                            "Пропущена ';' в конце объявления: после значения константы "
                            "должна стоять точка с запятой",
                            cursor_only=True,
                        ))
                    self._irons_sync_after_error()
                    return None
                value_tok = self._consume()
                children.append(SyntaxTreeNode(
                    "value", value_tok.value, value_tok.line, value_tok.start_pos))
                state = 6
                continue

            if state == 6:
                if t.type == TokenType.SEMICOLON:
                    self._consume_repeated_semicolon()
                    for c in children:
                        decl.add_child(c)
                    return decl
                if t.type == TokenType.CONST:
                    if value_tok:
                        self.errors.append(ParserError(
                            ";",
                            value_tok.line,
                            value_tok.end_pos + 1,
                            "Пропущена «;» в конце объявления: после числового литерала "
                            "должна стоять точка с запятой",
                            cursor_only=True,
                        ))
                    return None
                if value_tok:
                    self.errors.append(ParserError(
                        t.value,
                        value_tok.line,
                        value_tok.end_pos + 1,
                        "Пропущена «;» в конце объявления после числового литерала; "
                        f"вместо «;» указан лишний фрагмент «{t.value}».",
                        cursor_only=True,
                    ))
                else:
                    self.errors.append(ParserError(
                        t.value,
                        t.line,
                        t.start_pos,
                        f"Ожидался символ «;», найдено «{t.value}»",
                    ))
                self._advance()
                while (
                        self.current_token
                        and self.current_token.type not in (
                            TokenType.SEMICOLON,
                            TokenType.CONST,
                        )):
                    self._advance()
                if self._cur_is(TokenType.SEMICOLON):
                    self._consume_repeated_semicolon()
                    for c in children:
                        decl.add_child(c)
                    return decl
                return None

        return None

    def _mangled_assign_cluster_before_number(
        self, sig: List[Token], j0: int,
    ) -> Optional[tuple]:
        """
        Цепочка только «=» и ERROR (не float): между собой только смежные лексемы (без пробела).
        Число — сразу следующая значимая лексема после цепочки (перед числом пробел допустим).
        Иначе None (например «= !» — раздельные ошибки).
        Иначе (raw, index_of_NUMBER, error_tokens_for_suppress).
        """
        if j0 >= len(sig):
            return None
        t0 = sig[j0]
        if t0.type != TokenType.ASSIGN and not (t0.is_error and not _is_float_error_lexeme(t0.value)):
            return None
        # «! ==», «!!==» (слитно): лексика по «!», «==» — отдельно.
        if t0.is_error and not _is_float_error_lexeme(t0.value):
            e = 1
            idx = j0 + 1
            while (
                idx < len(sig)
                and sig[idx].is_error
                and not _is_float_error_lexeme(sig[idx].value)
                and _tokens_adjacent(sig[idx - 1], sig[idx])
            ):
                e += 1
                idx += 1
            if (
                e >= 1
                and idx + 1 < len(sig)
                and sig[idx].type == TokenType.ASSIGN
                and sig[idx + 1].type == TokenType.ASSIGN
                and _tokens_adjacent(sig[idx], sig[idx + 1])
            ):
                return None
            # «! = 100» — перед корректным «=» и числом: «!» не склеиваем с «=».
            if (
                e >= 1
                and idx < len(sig)
                and sig[idx].type == TokenType.ASSIGN
                and idx + 1 < len(sig)
                and sig[idx + 1].type == TokenType.NUMBER
            ):
                return None
        cluster: List[int] = [j0]
        i = j0 + 1
        while i < len(sig):
            ti = sig[i]
            if ti.type == TokenType.NUMBER:
                break
            if not _tokens_adjacent(sig[cluster[-1]], ti):
                break
            if ti.is_error and _is_float_error_lexeme(ti.value):
                return None
            if ti.type == TokenType.ASSIGN or (ti.is_error and not _is_float_error_lexeme(ti.value)):
                cluster.append(i)
                i += 1
                continue
            return None
        if i >= len(sig) or sig[i].type != TokenType.NUMBER:
            return None
        number_idx = i
        only_assigns = all(sig[j].type == TokenType.ASSIGN for j in cluster)
        if only_assigns:
            return None
        has_assign_in_cluster = any(sig[j].type == TokenType.ASSIGN for j in cluster)
        # Только «!» / «!!» с пробелом до числа — лексика + «пропущено =»; не одна «вместо =».
        if (
            not has_assign_in_cluster
            and not _tokens_adjacent(sig[cluster[-1]], sig[number_idx])
        ):
            return None
        raw = "".join(
            "=" if sig[j].type == TokenType.ASSIGN else sig[j].value
            for j in cluster
        )
        err_toks = [sig[j] for j in cluster if sig[j].is_error]
        return raw, number_idx, err_toks

    def _consume_repeated_assign(self):
        start = self.current_token
        if self._cur_is(TokenType.ASSIGN):
            got = self._mangled_assign_cluster_before_number(
                self.significant_tokens, self.position)
            if got is not None:
                raw, k, err_toks = got
                self._suppress_embedded_lex_errors(err_toks)
                first = self.significant_tokens[self.position]
                self.errors.append(ParserError(
                    raw,
                    first.line,
                    first.start_pos,
                    f"Ожидался символ «=», найдено «{raw}»",
                ))
                self.position = k
                self._update()
                return
        count = 0
        while self._cur_is(TokenType.ASSIGN):
            if count > 0:
                prev = self.significant_tokens[self.position - 1]
                if not _tokens_adjacent(prev, self.current_token):
                    break
            count += 1
            self._advance()
        # «=-=», «=--=» и т.п. — один "сломаный" оператор присваивания.
        if start and count == 1:
            spanned: List[Token] = []
            raw_parts: List[str] = ["="]
            while (
                self.current_token
                and self.current_token.is_error
                and self.current_token.value == "-"
                and self._peek_is(1, TokenType.ASSIGN)
            ):
                spanned.append(self.current_token)
                raw_parts.append(self.current_token.value)
                self._advance()
                spanned.append(self.current_token)  # '='
                raw_parts.append(self.current_token.value)
                self._advance()
            if spanned:
                # Лексический '-' внутри оператора не показываем отдельно в синтаксисе.
                self._suppress_embedded_lex_errors(spanned)
                raw = "".join(raw_parts)
                self.errors.append(ParserError(
                    raw,
                    start.line,
                    start.start_pos,
                    f"Ожидался символ «=», найдено «{raw}»",
                ))
        if count > 1 and start:
            self.errors.append(ParserError(
                "=" * count,
                start.line,
                start.start_pos,
                f"Повторяющийся оператор '=' ({count} раз)",
            ))

    def _consume_repeated_colon(self) -> Optional[tuple]:
        """Съедает подряд идущие ':' и возвращает (first_token, count)."""
        first = self.current_token
        if not self._cur_is(TokenType.COLON):
            return None
        count = 0
        while self._cur_is(TokenType.COLON):
            count += 1
            self._advance()
        return first, count

    def _consume_repeated_assign_run(self) -> Optional[tuple]:
        """Съедает подряд идущие '=' и возвращает (first_token, count) без формирования ошибок."""
        first = self.current_token
        if not self._cur_is(TokenType.ASSIGN):
            return None
        count = 0
        while self._cur_is(TokenType.ASSIGN):
            count += 1
            self._advance()
        return first, count

    def _consume_repeated_semicolon(self):
        start = self.current_token
        count = 0
        while self._cur_is(TokenType.SEMICOLON):
            count += 1
            self._advance()
        if count > 1 and start:
            self.errors.append(ParserError(
                ";" * count,
                start.line,
                start.start_pos,
                f"Повторяющийся оператор ';' ({count} раз)",
            ))

    def _add_error_mismatch(self, state: int, t: Token):
        exp = _expected_ru(state)
        got = _token_kind_ru(t)
        self.errors.append(ParserError(
            t.value,
            t.line,
            t.start_pos,
            f"Ожидался {exp}, найден {got}",
        ))

    def _add_error_eof(self, state: int):
        last = self.significant_tokens[-1] if self.significant_tokens else None
        exp = _expected_ru(state)
        base_line = last.line if last else 0
        base_pos = (last.end_pos + 1) if last else 0

        # Для EOF показываем все недостающие токены/символы до конца объявления.
        eof_expected_chain = {
            0: [("const", "Неожиданный конец ввода: ожидалось ключевое слово «const»")],
            1: [
                ("<идентификатор>", "Неожиданный конец ввода: после «const» должно следовать имя константы"),
                (":", "Неожиданный конец ввода: пропущено ':' перед типом данных"),
                ("<тип>", "Неожиданный конец ввода: пропущен тип данных (например, i32)"),
                ("=", "Неожиданный конец ввода: пропущен символ '=' перед значением"),
                ("<число>", "Неожиданный конец ввода: пропущен числовой литерал инициализатора"),
                (";", "Неожиданный конец ввода: пропущена ';' в конце объявления"),
            ],
            2: [
                (":", "Неожиданный конец ввода: пропущено ':' перед типом данных"),
                ("<тип>", "Неожиданный конец ввода: пропущен тип данных (например, i32)"),
                ("=", "Неожиданный конец ввода: пропущен символ '=' перед значением"),
                ("<число>", "Неожиданный конец ввода: пропущен числовой литерал инициализатора"),
                (";", "Неожиданный конец ввода: пропущена ';' в конце объявления"),
            ],
            3: [
                ("<тип>", "Неожиданный конец ввода: пропущен тип данных (например, i32)"),
                ("=", "Неожиданный конец ввода: пропущен символ '=' перед значением"),
                ("<число>", "Неожиданный конец ввода: пропущен числовой литерал инициализатора"),
                (";", "Неожиданный конец ввода: пропущена ';' в конце объявления"),
            ],
            4: [
                ("=", "Неожиданный конец ввода: пропущен символ '=' перед значением"),
                ("<число>", "Неожиданный конец ввода: пропущен числовой литерал инициализатора"),
                (";", "Неожиданный конец ввода: пропущена ';' в конце объявления"),
            ],
            5: [
                ("<число>", "Неожиданный конец ввода: пропущен числовой литерал инициализатора"),
                (";", "Неожиданный конец ввода: пропущена ';' в конце объявления"),
            ],
        }
        chain = eof_expected_chain.get(state)
        if chain is None:
            chain = [("EOF", f"Неожиданный конец ввода: ожидался {exp}")]

        for frag, msg in chain:
            self.errors.append(ParserError(
                frag,
                base_line,
                base_pos,
                msg,
                cursor_only=True,
            ))

    def _irons_sync_after_error(self):
        """Метод Айронса: пропуск до ';' или 'const'."""
        while self.current_token is not None:
            typ = self.current_token.type
            if typ == TokenType.ERROR:
                self._advance()
                continue
            if typ == TokenType.SEMICOLON:
                self._advance()
                return
            if typ == TokenType.CONST:
                return
            self._advance()

    def _cur_is(self, token_type) -> bool:
        return self.current_token is not None and self.current_token.type == token_type

    def _consume(self) -> Token:
        tok = self.current_token
        assert tok is not None
        self._advance()
        return tok

    def _advance(self):
        self.position += 1
        self._update()

    def _update(self):
        if self.position < len(self.significant_tokens):
            self.current_token = self.significant_tokens[self.position]
        else:
            self.current_token = None
