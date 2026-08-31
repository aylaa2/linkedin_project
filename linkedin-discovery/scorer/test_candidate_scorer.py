import json
from pathlib import Path
import unittest

from candidate_scorer import process_candidates_pipeline
from models import Candidate

class TestCandidateScorerIntegration(unittest.TestCase):
    def setUp(self):
        # Setup paths to test data
        self.test_data_dir = Path("test_data")
        self.req_path = self.test_data_dir / "recruiter_requirement.txt"
        self.candidates_path = self.test_data_dir / "mock_candidates.json"

    def test_pipeline_integration(self):
        """
        Testează pipeline-ul complet (Reranker + Groq LLM + Heuristici) 
        folosind datele din folderul test_data.
        Atenție: Acest test folosește API-ul real Groq.
        """
        # 1. Verificăm dacă fișierele există
        self.assertTrue(self.req_path.exists(), "Fișierul recruiter_requirement.txt lipsește din test_data.")
        self.assertTrue(self.candidates_path.exists(), "Fișierul mock_candidates.json lipsește din test_data.")

        # 2. Încărcăm cerința
        recruiter_requirement = self.req_path.read_text(encoding="utf-8")
        
        # 3. Încărcăm și validăm candidații
        payload = json.loads(self.candidates_path.read_text(encoding="utf-8"))
        candidates = [Candidate.model_validate(item) for item in payload]
        
        self.assertGreater(len(candidates), 0, "Lista de candidați este goală.")

        # 4. Rulăm pipeline-ul complet
        print("\\nÎncepem testul de integrare a pipeline-ului...")
        results = process_candidates_pipeline(
            recruiter_requirement=recruiter_requirement,
            candidates=candidates
        )

        # 5. Verificăm rezultatele
        self.assertEqual(len(results), len(candidates), "Numărul de rezultate trebuie să fie egal cu numărul de candidați.")
        
        # Salvăm un fișier de debug în test_data ca să poată fi verificat de utilizator
        output_path = self.test_data_dir / "test_results.json"
        output_path.write_text(
            json.dumps([r.model_dump() for r in results], indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"\\nTest completat cu succes! Rezultatele au fost salvate în: {output_path}")

        # Verificări de bază
        for result in results:
            self.assertIsNotNone(result.candidate_name)
            self.assertIsNotNone(result.profile_url)
            self.assertIn(result.evaluation_status, ["FULL_EVALUATION", "SKIPPED_BY_RERANKER"])
            
            if result.evaluation_status == "FULL_EVALUATION":
                self.assertIsNotNone(result.final_score)
                self.assertTrue(0 <= result.final_score <= 100)
                self.assertIsNotNone(result.extracted_requirements)

if __name__ == "__main__":
    unittest.main()
