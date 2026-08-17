from __future__ import annotations

import unittest
from pathlib import Path

from prefcal.release_audit import audit_release


ROOT = Path(__file__).resolve().parents[1]


class ReleaseEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = audit_release(ROOT)

    def test_gpt_frozen_stop(self) -> None:
        gpt = self.audit["systems"]["GPT-OSS-120B"]
        self.assertEqual(gpt["rows"], 148)
        self.assertEqual(gpt["source_recomputation"]["complete_blocks"], ["M2P00", "M2P06", "M2P07"])
        semantic = gpt["source_recomputation"]["factors"]["semantic_swap"]
        self.assertEqual((semantic["matches"], semantic["contrasts"]), (7, 48))
        self.assertEqual(semantic["best_case_final_rate"], 0.74375)
        self.assertFalse(semantic["frozen_75_percent_gate_reachable"])
        self.assertEqual(
            self.audit["gpt_oss_terminal_verdict"]["status"],
            "STOP_PROSPECTIVE_DETERMINISTIC_FUTILITY",
        )
        self.assertFalse(self.audit["gpt_oss_terminal_verdict"]["transport_run"])

    def test_matched_slice_fingerprints(self) -> None:
        expected = {
            "GPT-OSS-120B": {
                "identifier_A": 16,
                "physical_left": 8,
                "consistency": {
                    "semantic_swap": (0, 8),
                    "identifier_swap": (0, 8),
                    "answer_order_swap": (8, 8),
                    "template_idx": (8, 8),
                },
            },
            "Llama-3.3-70B (partial)": {
                "identifier_A": 9,
                "physical_left": 13,
                "consistency": {
                    "semantic_swap": (3, 8),
                    "identifier_swap": (5, 8),
                    "answer_order_swap": (5, 8),
                    "template_idx": (7, 8),
                },
            },
        }
        for name, target in expected.items():
            with self.subTest(name=name):
                observed = self.audit["systems"][name]["matched_M2P00_AB_slice"]
                self.assertEqual(observed["observed_conditions"], 16)
                self.assertEqual(observed["identifier_A"], target["identifier_A"])
                self.assertEqual(observed["physical_left"], target["physical_left"])
                for factor, counts in target["consistency"].items():
                    self.assertEqual(
                        (observed["consistency"][factor]["matches"], observed["consistency"][factor]["contrasts"]),
                        counts,
                    )

    def test_archived_file_hashes(self) -> None:
        gpt = self.audit["systems"]["GPT-OSS-120B"]
        llama = self.audit["systems"]["Llama-3.3-70B (partial)"]
        self.assertEqual(
            gpt["raw_file_sha256"],
            "41831de58ebce32a1252bf8aabde1205e977969a0896c7b97ca78c1afac323ab",
        )
        self.assertEqual(
            llama["raw_file_sha256"],
            "30dc5a3b4ed5e155b9bc012852efa99df33068ca33ac61d6ebea65dcc919f84c",
        )


if __name__ == "__main__":
    unittest.main()

