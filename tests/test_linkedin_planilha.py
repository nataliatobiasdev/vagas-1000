"""Script de planilha sem IA: regras de aderência/senioridade e o CSV que o importador do app lê."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "linkedin-jobs"))

import planilha  # noqa: E402
from scraper import importer  # noqa: E402

SAMPLE = ROOT / "tests" / "fixtures" / "linkedin_salesforce_sample.csv"


class RulesTests(unittest.TestCase):
    def test_fit_alta_needs_salesforce_in_title_plus_stack_or_seniority(self):
        self.assertEqual(planilha.aderencia("Desenvolvedor Salesforce Sênior", "x"), "Alta")
        self.assertEqual(planilha.aderencia("Salesforce Developer", "Apex e LWC no dia a dia"), "Alta")
        self.assertEqual(planilha.aderencia("Salesforce Admin", "Sales Cloud"), "Média")
        self.assertEqual(planilha.aderencia("Engenheiro de software", "Salesforce e Apex"), "Média")
        self.assertEqual(planilha.aderencia("Backend Go Senior", "AWS"), "Baixa")

    def test_senioridade_names_the_signal_found(self):
        self.assertEqual(planilha.criterio_senioridade("Arquiteto de soluções", ""), "título: arquiteto")
        self.assertEqual(planilha.criterio_senioridade("Tech Lead", ""), "título: lead/gerência")
        self.assertEqual(planilha.criterio_senioridade("Dev", "mínimo de 5+ anos de experiência"), "descrição: 5+ anos de experiência")
        self.assertEqual(planilha.criterio_senioridade("Dev", ""), "não identificado")

    def test_workplace_contract_spanish_and_brazil_eligibility(self):
        self.assertEqual(planilha.modalidade("Híbrido (2 dias presenciais)"), "Híbrido")
        self.assertEqual(planilha.tipo_contrato("", "contrato PJ de 6 meses"), "Contrato")
        self.assertEqual(planilha.espanhol("Espanhol é desejável"), "desejável")
        self.assertEqual(planilha.espanhol("Sem menção"), "não citado")
        self.assertEqual(planilha.elegibilidade("São Paulo, Brasil", "Brasil"), "Vaga no Brasil")
        self.assertEqual(planilha.elegibilidade("Remote - USA only", "América Latina"), "Restrito a outros países")


class CsvTests(unittest.TestCase):
    def test_the_generated_csv_is_read_by_the_app_importer(self):
        vaga = {"job_id": "123456789", "url": "https://www.linkedin.com/jobs/view/123456789/", "title": "Salesforce Architect Sênior",
                "company": "Acme", "location": "São Paulo, Brasil", "posted": "há 2 horas", "applicants": "35 candidaturas",
                "description": "Apex, LWC e SOQL. Espanhol é desejável.", "workplace": "Remoto", "salary": "R$ 20 mil"}
        linha = planilha.linha(vaga, "Brasil")
        self.assertEqual(list(linha.keys()), planilha.COLUNAS)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "planilha.csv"
            planilha.escrever(out, [linha])
            self.assertEqual(out.read_bytes()[:3], b"\xef\xbb\xbf")               # BOM: o Excel abre com acentos
            with out.open(encoding="utf-8-sig", newline="") as fh:
                self.assertEqual(next(csv.reader(fh))[:3], ["id", "url", "titulo"])
            jobs = importer.parse_file(out)
        j = jobs[0]
        self.assertEqual((j.title, j.company_name, j.location), ("Salesforce Architect Sênior", "Acme", "São Paulo, Brasil"))
        self.assertEqual(j.metadata["aderência (planilha)"], "Alta")
        self.assertEqual(j.metadata["senioridade"], "título: sênior")
        self.assertEqual(j.workplace_type, "remote")
        self.assertIn("Apex", j.description)

    def test_the_rules_agree_with_the_classification_in_the_real_capture_sample(self):
        """Nas 3 vagas do arquivo de exemplo (copiado da captura de 17/11), a regra bate com a classificação do Claude."""
        with SAMPLE.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        acertos = sum(planilha.aderencia(r["titulo"], r["descricao"]) == r["aderencia_salesforce"] for r in rows)
        self.assertGreaterEqual(acertos, 2)


if __name__ == "__main__":
    unittest.main()
