"""Матрица проверок лексера/парсера. Запуск: python test_parser_matrix.py"""
from __future__ import annotations

from lexical_analyzer import LexicalAnalyzer
from parser import Parser


def _analyze(source: str):
    tokens = LexicalAnalyzer().analyze(source)
    tree, syn_errs = Parser().parse(tokens)
    n_decl = 0
    if tree is not None:
        if tree.node_type == "program":
            n_decl = sum(1 for c in tree.children if c.node_type == "const_declaration")
        elif tree.node_type == "const_declaration":
            n_decl = 1
    return len(syn_errs), n_decl


def main():
    cases = [
        ("const", 6, 0, "eof_after_const_missing_all_tokens"),
        ("const MARKS: i32 = 100;", 0, 1, "golden"),
        ("const MARKS: i32 = -100;", 0, 1, "negative_int_ok"),
        ("const A: i32 = 1; const B: i32 = 2;", 0, 2, "two_ok"),
        ("const i32 = 100", 3, 0, "missing_name_colon_semicolon_three_errors"),
        ("const i32: i32 = 100", 2, 0, "type_used_as_name_then_missing_semicolon"),
        ("const : i32 = 100;", 1, 1, "missing_name_before_colon_one_error"),
        ("const MARKS: = 100;", 1, 1, "missing_type_one_syntax"),
        ("const MARKS: i32 : 100;", 1, 1, "colon_instead_of_equals_before_literal_one_error"),
        ("const MARKS: i32 ! 100;", 2, 1, "invalid_char_before_number_spaced_two_errors"),
        ("const MARKS: i32 =!= 100;", 1, 1, "mangled_assign_eq_bang_eq_one_syntax"),
        ("const MARKS: i32 !=! 100;", 1, 1, "mangled_assign_bang_eq_bang_one_syntax"),
        ("const MARKS: i32 = ;", 1, 1, "missing_literal_before_semicolon_one_error"),
        ("const : i3!!2 = rtgy;", 3, 0, "missing_ident_mangled_type_and_bad_literal_three_errors"),
        ("const : i3!!2 =!- rtgy;", 4, 0, "missing_ident_mangled_type_bad_assign_and_bad_literal"),
        ("const : = 100;", 2, 1, "missing_name_and_type_two_errors"),
        ("i32 const MARKS: = 100;", 2, 1, "leading_type_then_const_missing_type"),
        ("const i32: i32 =-= 100", 3, 0, "mangled_assign_cluster_and_missing_semicolon"),
        ("const : MARKS: i32 : = 100", 3, 0, "extra_colons_and_missing_semicolon"),
        ("const ::::: MARKS:::: i32 :::: = 100:", 4, 0, "group_repeated_colons"),
        ("const ;;;; MARKS: i32 = 100;", 1, 1, "group_repeated_misplaced_semicolons"),
        ("const == MARKS:== i32 = 100;", 2, 1, "group_repeated_equals_like_colons"),
        ("con@st MA@RKS: i3@2 = 10@0;", 4, 1, "embedded_at_behaves_like_hash"),
        ("con#st MARKS: i32 = 10#0", 3, 0, "mangled_int_literal_without_semicolon"),
        ("const MARKS: i32 = 100\"", 1, 0, "trailing_invalid_char_after_number_one_error"),
        ("conN°st (( MAR#KS: MARKS\" = i32;", 5, 0, "embedded_identifier_has_single_error"),
        ("const A: i32 = 1\nconst B: i32 = 2;", 1, 1, "first_no_semicolon_second_ok"),
        ("MARKS: i32 = 100;", 1, 1, "no_const_recovered_ast"),
        ("const X: i32 = 1.5;", 1, 0, "float_literal"),
        ("con!st MARKS:: i32 = 1.0", 4, 0, "float_at_eof_also_missing_semicolon_syntax"),
        ("MA!RKS:: i32 = 1.0", 5, 0, "no_const_mangled_ident_double_colon_float_eof"),
        ("const X: i32 = 100;;", 1, 1, "double_semicolon_ok_decl"),
        ("cont MARKS i32 = 100", 3, 0, "typo_const_missing_colon_semicolon"),
        ("co!nst 100: i3##2 = @ 1000", 5, 0, "typo_const_number_as_name_bad_type_lex_at_missing_semicolon"),
        ("co!nst 100: i:::===3##2 = 1!0\"0", 5, 0, "mangled_type_equals_inside_and_mangled_int_literal_no_semicolon"),
        ("const MARKS: i!32 = 1,00:", 3, 0, "mangled_type_mangled_number_trailing_colon_seen_as_missing_semicolon"),
        ("const MARKS i32 = 100", 2, 0, "missing_colon_semicolon"),
        ("const MARKS: i32 = 100", 1, 0, "missing_semicolon_only"),
        ("con st MA RKS: i 32 = 1 00;", 4, 1, "spaces_inside_lexemes_four_errors_but_decl_recovers"),
        ("cost MARKS i2  100", 5, 0, "five_syntax_keyword_colon_type_eq_semi"),
        ("cost # MARKS # i2 100", 7, 0, "lex_hash_plus_syntax_seven_errors"),
        ("i32 : i32 = 100", 3, 0, "leading_type_missing_name_and_semicolon"),
        ("i32 MARKS: i32 = 100", 2, 0, "leading_type_then_name_missing_semicolon"),
        ("const MARKS: i32 = 100; fgh", 1, 1, "trailing_garbage_after_semicolon"),
        ("const MARKS: i32 = 100; @@@@", 1, 1, "trailing_invalid_chars_after_semicolon_one_error"),
        ("con#st MAR#KS: i32 =! 100S", 4, 0, "heavily_corrupted_line_four_errors_no_embedded_lex"),
        ("MARKS MARKS: i32 = 100;", 1, 1, "duplicate_name_instead_of_const_one_error"),
        ("MARKSIK MARKS: i32 = 100;", 1, 1, "two_names_before_colon_missing_const_one_error"),
        ("const MARKS MARKS: i32 = 100;", 1, 1, "const_then_two_names_before_colon"),
        ("const i32: MARKS = 100;", 2, 1, "swapped_identifier_and_type_two_errors"),
        ("const MARKS: i3'2 = 100;", 1, 1, "mangled_type_one_syntax_no_embedded_lex"),
        ("con'st MARKS: i3'2 = 100;", 2, 1, "mangled_const_and_type_two_syntax_no_embedded_lex"),
        ("con;st MA;RKS: i3;2 = 100;", 3, 1, "semicolons_inside_keyword_name_type_three_errors"),
        ("con:st MAR:KS: i3:2 = 100;", 3, 1, "colons_inside_keyword_name_type_three_errors"),
        ("con=st MAR=KS: i3=2 = 100;", 3, 1, "equals_inside_keyword_name_type_three_errors"),
        ("const MARKS: i32 = 10!0;", 1, 1, "mangled_int_literal_one_syntax_no_embedded_lex"),
        ("const MARKS: i\"32 = 100;", 1, 1, "mangled_type_embedded_quote_one_syntax"),
        ("const MARKS: i!3\"2 = 100;", 1, 1, "mangled_type_mixed_errors_and_digits_one_syntax"),
        ("con#st ) MAR#KS: i32 =! 100;", 4, 1, "embedded_hash_but_standalone_paren_and_bang_lex"),
        ("con#st № MAR#KS № : ) i32 =! 100;", 6, 1, "standalone_numero_sign_kept_as_lex_errors"),
        ("con-st - MAR-KS: - i3-2 = 10-0;", 6, 1, "hyphen_inside_words_like_separators"),
        ("con(st i32: i2 == 100", 5, 0, "paren_in_const_then_swapped_and_missing_semicolon"),
        ("conN°st MAR#KS i2 ! == 10!0:", 8, 0, "mangled_number_and_trailing_colon_eight_errors"),
        ("con:::st MA::RKS: i:::32 = 1:::00;", 4, 1, "multi_colon_inside_tokens_single_errors"),
        ("co:::::nst MAR====KS: i:::3;;;;;2 = 100;", 3, 1, "mangled_type_with_many_colon_semicolon_one_error"),
    ]
    for src, exp_syn, exp_decl, label in cases:
        syn, decl = _analyze(src)
        assert syn == exp_syn, f"{label}: syn {syn} != {exp_syn}\n{src!r}"
        assert decl == exp_decl, f"{label}: decl {decl} != {exp_decl}\n{src!r}"
    print("test_parser_matrix: OK (%d cases)" % len(cases))


if __name__ == "__main__":
    main()
