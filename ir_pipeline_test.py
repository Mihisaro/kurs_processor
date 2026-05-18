#!/usr/bin/env python3

import unittest

from ir_codegen import generate_tac
from ir_optimize import apply_optimizations
from semantic_analysis import analyze_semantics


class IRPipelineTest(unittest.TestCase):
    def test_const_marks_pipeline(self):
        src = "const MARKS: i32 = 100;\n"
        _fa, valid_ast, sem_errs, syn_errs = analyze_semantics(src)
        self.assertEqual(sem_errs, [])
        self.assertEqual(syn_errs, [])

        raw, opt1, opt2 = apply_optimizations(generate_tac(valid_ast))

        self.assertEqual(len(raw), 3)
        self.assertEqual(raw[0].op, "LOAD_CONST")
        self.assertEqual(raw[0].arg2, "100")
        self.assertEqual(raw[1].op, "STORE")
        self.assertEqual(raw[1].arg1, "MARKS")

        self.assertEqual(len(opt1), 2)
        self.assertEqual(opt1[0].op, "STORE")
        self.assertEqual(opt1[0].arg1, "MARKS")
        self.assertEqual(opt1[0].arg2, "100")

        self.assertEqual(len(opt2), 1)
        self.assertEqual(opt2[0].op, "CONST_DECL")
        self.assertEqual(opt2[0].arg1, "MARKS")
        self.assertEqual(opt2[0].arg2, "i32")
        self.assertEqual(opt2[0].arg3, "100")


if __name__ == "__main__":
    unittest.main(verbosity=2)
