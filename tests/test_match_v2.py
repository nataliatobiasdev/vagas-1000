import json
import unittest
from pathlib import Path

from scraper.match_v2 import assess, snippets, ranking_key
from scraper.models import Job

PROFILE = json.loads((Path(__file__).resolve().parents[1] / 'config/match_profile.json').read_text(encoding='utf-8'))

def evaluate(title, description, location='Brazil'):
    return assess(Job('x', 'X', 'test', title, location=location, description=description), PROFILE)

class TestExperimentalMatch(unittest.TestCase):
    def test_specific_mandatory_skill_is_conditional(self):
        r = evaluate('Salesforce Developer Sênior', 'Requisitos:\nExperiência obrigatória com Interaction Studio.\nApex e LWC.')
        self.assertEqual(r['verdict'], 'CONDICIONAL')
        self.assertIn('personalization', r['unknown_required'])

    def test_preferred_is_not_mandatory(self):
        r = evaluate('Salesforce Developer Sênior', 'Diferenciais:\nExperiência em Marketing Cloud.\nRequisitos:\nExperiência obrigatória com Apex.')
        self.assertNotIn('marketing_cloud', r['unknown_required'])

    def test_negation_does_not_make_requirement(self):
        r = evaluate('Salesforce Engineer', 'Não é necessária experiência com AWS.')
        self.assertTrue(any(e['skill'] == 'aws' and e['kind'] == 'not_required' for e in r['evidence']))

    def test_empty_and_ambiguous_remote_are_not_confirmed(self):
        r = evaluate('Salesforce Developer', '', 'Remote')
        self.assertEqual(r['verdict'], 'INFORMAÇÕES INSUFICIENTES')
        self.assertEqual(r['confidence'], 'baixa')

    def test_clear_restriction_blocks(self):
        r = evaluate('Salesforce Engineer', 'Must be authorized to work in the United States.', 'USA Remote')
        self.assertEqual(r['verdict'], 'INCOMPATÍVEL')

    def test_specialty_does_not_receive_main_track(self):
        r = evaluate('Salesforce Marketing Cloud Consultant', 'Salesforce marketing cloud')
        self.assertNotEqual(r['track'], 'principal')

    def test_other_city_with_brazil_does_not_imply_eligibility(self):
        r = evaluate('Senior Salesforce Developer', 'Apex LWC integração. ' * 25, 'Recife, Pernambuco, Brasil')
        self.assertEqual(r['verdict'], 'INFORMAÇÕES INSUFICIENTES')

    def test_multicountry_location_is_not_confirmed(self):
        r = evaluate('Senior Salesforce Developer', 'Apex LWC integração. ' * 25, 'Bogota Colombia; São Paulo Brazil')
        self.assertEqual(r['verdict'], 'INFORMAÇÕES INSUFICIENTES')

    def test_alternative_skill_is_not_a_proven_gap(self):
        r = evaluate('Salesforce Developer', 'Requisitos:\nExperiência obrigatória com Apex ou Java.')
        self.assertIn('java', r['unknown_required'])
        self.assertEqual(r['verdict'], 'CONDICIONAL')

    def test_unrelated_and_midlevel_roles_not_promoted(self):
        for title in ('Product Owner Salesforce Sênior', 'Senior Software Engineer - Endpoint Security', 'Software Engineer Go PL', 'Head of Salesforce Engineering', 'Sr Lead Software Support Engineer Salesforce'):
            with self.subTest(title=title):
                self.assertEqual(evaluate(title, 'Apex LWC Salesforce API testing AWS. ' * 20)['track'], 'outra')

    def test_flattened_mandatory_certificate_section(self):
        desc = ('Desenvolver Apex e LWC. Obrigatórios Experiência sólida Salesforce. '
                'Conhecimento de integração. Certificação Salesforce Platform Developer I. '
                'Diferenciais Certificações Platform Developer II. Inglês avançado.')
        r = evaluate('Desenvolvedor Salesforce Sênior Tech Lead', desc)
        self.assertEqual(r['verdict'], 'CONDICIONAL')
        self.assertTrue(any('Platform Developer I' in warning for warning in r['warnings']))

    def test_generic_title_hides_marketing_cloud_specialty(self):
        text = 'Salesforce Marketing Cloud e Data Cloud. Marketing Cloud. Experiência em Marketing Cloud.'
        r = evaluate('Software Engineer (Salesforce)', text * 6)
        self.assertEqual(r['track'], 'outra')

    def test_singular_flattened_mandatory_section(self):
        text = 'Desenvolver Apex. Obrigatório Experiência com integrações MuleSoft. Diferenciais Certificações Salesforce.'
        r = evaluate('Senior Salesforce Developer', text)
        self.assertIn('mulesoft', r['unknown_required'])
        self.assertEqual(r['verdict'], 'CONDICIONAL')

    def test_outside_city_onsite_blocked(self):
        text = 'Salesforce Apex e LWC. Disponibilidade para trabalho presencial.' * 10
        self.assertEqual(evaluate('Senior Salesforce Developer', text, 'Recife, PE')['verdict'], 'INCOMPATÍVEL')

    def test_talent_pool_is_not_a_concrete_low_fit_role(self):
        r = evaluate('Banco de Talentos - TI Salesforce', 'Projetos e diversos cargos Salesforce. ' * 20, 'São Paulo')
        self.assertEqual(r['verdict'], 'INFORMAÇÕES INSUFICIENTES')

    def test_adjacent_track_requires_evidence_review(self):
        r = evaluate('Senior Backend Engineer', 'Requisitos:\nPython e APIs. ' * 30, 'Brasil')
        self.assertEqual(r['verdict'], 'CONDICIONAL')

    def test_specialized_omni_studio_is_not_invented(self):
        r = evaluate('Salesforce Developer', 'Requisitos:\nExperiência em Vlocity e OmniStudio.')
        self.assertIn('omni_studio', r['unknown_required'])

    def test_score_never_overrides_a_block(self):
        self.assertGreater(ranking_key('CONDICIONAL', 'expansão', 30), ranking_key('INCOMPATÍVEL', 'principal', 100))

    def test_foreign_location_keeps_geo_uncertain_even_when_conditional(self):
        r = evaluate('Senior Salesforce Developer', 'Requisitos:\nMuleSoft. ' * 30, 'Costa Rica')
        self.assertEqual(r['verdict'], 'INFORMAÇÕES INSUFICIENTES')
        self.assertTrue(any('Local internacional' in w for w in r['warnings']))

    def test_requirements_subheading_does_not_hide_required_queue(self):
        text = 'Requirements:\nWhat we are looking for:\nExperience with queue systems (SQS, Kafka).'
        r = evaluate('Staff Salesforce Engineer', text)
        self.assertIn('messaging', r['unknown_required'])
        self.assertEqual(r['verdict'], 'CONDICIONAL')

    def test_exigida_heading_captures_specialized_voice(self):
        r = evaluate('Arquiteto Salesforce', 'Experiência exigida:\nExperiência em Service Cloud Voice e Amazon Connect.')
        self.assertIn('voice', r['unknown_required'])
        self.assertEqual(r['verdict'], 'CONDICIONAL')

    def test_infrastructure_title_with_mulesoft_does_not_climb_as_salesforce_dev(self):
        text = ('Requisitos:\nOperações de MuleSoft e Azure. ' * 30)
        r = evaluate('Senior Infrastructure Engineer - Salesforce/MuleSoft', text)
        self.assertEqual(r['verdict'], 'BAIXA ADERÊNCIA')

    def test_component_limits_and_no_probability(self):
        r = evaluate('Senior Salesforce Tech Lead', ('Apex LWC API testing Git AWS architecture leadership. ' * 15))
        self.assertLessEqual(r['score'], 100)
        self.assertLessEqual(r['components']['função e atividades'], 30)
        self.assertLessEqual(r['components']['requisitos técnicos'], 35)
        self.assertLessEqual(r['components']['senioridade e escopo'], 20)
        self.assertLessEqual(r['components']['experiência transferível'], 15)

if __name__ == '__main__': unittest.main()
