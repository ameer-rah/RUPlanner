import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.planner import heuristic_plan, _parse_major_entry, CATALOG_YEAR
from app.schemas import PlanRequest

client = TestClient(app)


def plan(majors, minors=None, completed=None, seasons=None, grad="Spring 2030", max_cr=18):
    return heuristic_plan(PlanRequest(
        degree_level="bachelor",
        majors=majors,
        minors=minors or [],
        completed_courses=completed or [],
        target_grad_term=grad,
        max_credits_per_term=max_cr,
        preferred_seasons=seasons or ["Spring", "Fall"],
    ))


def api_plan(majors, minors=None, completed=None, seasons=None, grad="Spring 2030", max_cr=18):
    return client.post("/plan", json={
        "majors": majors,
        "minors": minors or [],
        "completed_courses": completed or [],
        "target_grad_term": grad,
        "max_credits_per_term": max_cr,
        "preferred_seasons": seasons or ["Spring", "Fall"],
    })


def all_codes(resp):
    return {c["code"] for t in resp.json()["terms"] for c in t["courses"]}


def elective_codes(resp):
    return [c["code"] for t in resp.json()["terms"] for c in t["courses"] if c["is_elective"]]


class TestParseMajorEntry:
    def test_bs(self):
        school, level, name = _parse_major_entry("Computer Science (BS, SAS)", "bachelor")
        assert school == "SAS" and level == "bachelor_bs" and name == "Computer Science"

    def test_ba(self):
        school, level, name = _parse_major_entry("Computer Science (BA, SAS)", "bachelor")
        assert level == "bachelor_ba"

    def test_bfa(self):
        school, level, name = _parse_major_entry("Dance (BFA, MGSA)", "bachelor")
        assert school == "MGSA" and level == "bachelor_bfa"

    def test_bm(self):
        school, level, name = _parse_major_entry("Music (Composition) (BM, MGSA)", "bachelor")
        assert level == "bachelor_bm"

    def test_bsba(self):
        school, level, name = _parse_major_entry("Accounting (BSBA, RBS)", "bachelor")
        assert school == "RBS" and level == "bachelor_bsba"

    def test_bsla(self):
        school, level, name = _parse_major_entry("Landscape Architecture (BSLA, SEBS)", "bachelor")
        assert school == "SEBS" and level == "bachelor_bsla"

    def test_minor(self):
        school, level, name = _parse_major_entry("Mathematics (Minor, SAS)", "minor")
        assert level == "minor"

    def test_sppp_minor(self):
        school, level, name = _parse_major_entry("Public Health (Minor, SPPP)", "minor")
        assert school == "SPPP" and level == "minor"

    def test_concentration(self):
        school, level, name = _parse_major_entry("Finance (Concentration, RBS)", "bachelor")
        assert school == "RBS" and level == "concentration"

    def test_soe_school(self):
        school, level, name = _parse_major_entry("Computer Engineering (BS, SOE)", "bachelor")
        assert school == "SOE" and level == "bachelor_bs"

    def test_sci_school(self):
        school, level, name = _parse_major_entry("Information Technology and Informatics (BA, SCI)", "bachelor")
        assert school == "SCI" and level == "bachelor_ba"


class TestSAS:
    def test_cs_bs(self):
        r = api_plan(["Computer Science (BS, SAS)"])
        assert r.status_code == 200
        assert len(r.json()["terms"]) > 0

    def test_cs_ba(self):
        r = api_plan(["Computer Science (BA, SAS)"])
        assert r.status_code == 200

    def test_math_bs(self):
        r = api_plan(["Mathematics (BS, SAS)"])
        assert r.status_code == 200
        codes = all_codes(r)
        assert "MATH151" in codes or "MATH251" in codes

    def test_data_science_cs_track(self):
        r = api_plan(["Data Science (Computer Science Track) (BS, SAS)"])
        assert r.status_code == 200

    def test_data_science_stats_track(self):
        r = api_plan(["Data Science (Statistics Track) (BA, SAS)"])
        assert r.status_code == 200

    def test_economics_ba(self):
        r = api_plan(["Economics (BA, SAS)"])
        assert r.status_code == 200

    def test_biology_ba(self):
        r = api_plan(["Biological Sciences (BA, SAS)"])
        assert r.status_code == 200

    def test_psychology_ba(self):
        r = api_plan(["Psychology (BA, SAS)"])
        assert r.status_code == 200

    def test_criminal_justice_ba(self):
        r = api_plan(["Criminal Justice (BA, SAS)"])
        assert r.status_code == 200

    def test_exercise_science_bs(self):
        r = api_plan(["Exercise Science (BS, SAS)"])
        assert r.status_code == 200

    def test_astrophysics_bs(self):
        r = api_plan(["Astrophysics (BS, SAS)"])
        assert r.status_code == 200

    def test_cognitive_science_ba(self):
        r = api_plan(["Cognitive Science (BA, SAS)"])
        assert r.status_code == 200

    def test_credit_cap_respected(self):
        r = api_plan(["Computer Science (BS, SAS)"], max_cr=12)
        for t in r.json()["terms"]:
            assert t["total_credits"] <= 12


class TestSCI:
    def test_iti_ba(self):
        r = api_plan(["Information Technology and Informatics (BA, SCI)"])
        assert r.status_code == 200
        codes = all_codes(r)
        assert "ITI200" in codes or "ITI201" in codes

    def test_communication_ba(self):
        r = api_plan(["Communication (BA, SCI)"])
        assert r.status_code == 200

    def test_journalism_ba(self):
        r = api_plan(["Journalism and Media Studies (BA, SCI)"])
        assert r.status_code == 200

    def test_iti_has_required_courses(self):
        r = api_plan(["Information Technology and Informatics (BA, SCI)"])
        codes = all_codes(r)
        iti_core = {"SCI103", "ITI200", "ITI201", "ITI202", "ITI210"}
        assert iti_core.issubset(codes)

    def test_iti_elective_count(self):
        r = api_plan(["Information Technology and Informatics (BA, SCI)"])
        electives = elective_codes(r)
        assert len(electives) == 7

    def test_iti_sas_iti_vs_sci_iti_different(self):
        r_sci = api_plan(["Information Technology and Informatics (BA, SCI)"])
        r_sas = api_plan(["Information Technology and Informatics (BA, SAS)"])
        assert r_sci.status_code == 200
        assert r_sas.status_code == 200
        sci_codes = all_codes(r_sci)
        sas_codes = all_codes(r_sas)
        assert "SCI103" in sci_codes


class TestSOE:
    def test_computer_engineering_bs(self):
        r = api_plan(["Computer Engineering (BS, SOE)"])
        assert r.status_code == 200
        codes = all_codes(r)
        assert "ECE221" in codes

    def test_electrical_engineering_bs(self):
        r = api_plan(["Electrical Engineering (BS, SOE)"])
        assert r.status_code == 200

    def test_mechanical_engineering_bs(self):
        r = api_plan(["Mechanical Engineering (BS, SOE)"])
        assert r.status_code == 200

    def test_biomedical_engineering_bs(self):
        r = api_plan(["Biomedical Engineering (BS, SOE)"])
        assert r.status_code == 200

    def test_civil_engineering_bs(self):
        r = api_plan(["Civil Engineering (BS, SOE)"])
        assert r.status_code == 200

    def test_chemical_engineering_bs(self):
        r = api_plan(["Chemical Engineering (BS, SOE)"])
        assert r.status_code == 200

    def test_industrial_engineering_bs(self):
        r = api_plan(["Industrial Engineering (BS, SOE)"])
        assert r.status_code == 200

    def test_aerospace_engineering_bs(self):
        r = api_plan(["Aerospace Engineering (BS, SOE)"])
        assert r.status_code == 200

    def test_env_engineering_no_electives(self):
        r = api_plan(["Environmental Engineering (BS, SOE)"])
        assert r.status_code == 200
        electives = elective_codes(r)
        assert len(electives) == 0

    def test_soe_shared_core_in_plan(self):
        r = api_plan(["Computer Engineering (BS, SOE)"])
        codes = all_codes(r)
        for core in ("ENG101", "MATH151", "PHYS123"):
            assert core in codes, f"Missing SOE core: {core}"


class TestRBS:
    def test_accounting_bsba(self):
        r = api_plan(["Accounting (BSBA, RBS)"])
        assert r.status_code == 200
        codes = all_codes(r)
        assert "ACCT272" in codes

    def test_finance_bsba(self):
        r = api_plan(["Finance (BSBA, RBS)"])
        assert r.status_code == 200

    def test_marketing_bsba(self):
        r = api_plan(["Marketing (BSBA, RBS)"])
        assert r.status_code == 200

    def test_bait_bsba(self):
        r = api_plan(["Business Analytics and Information Technology (BSBA, RBS)"])
        assert r.status_code == 200

    def test_supply_chain_bsba(self):
        r = api_plan(["Supply Chain Management (BSBA, RBS)"])
        assert r.status_code == 200

    def test_leadership_mgmt_bsba(self):
        r = api_plan(["Leadership and Management (BSBA, RBS)"])
        assert r.status_code == 200

    def test_accounting_no_electives_still_schedules(self):
        r = api_plan(["Accounting (BSBA, RBS)"])
        assert r.status_code == 200
        assert len(r.json()["terms"]) > 0
        assert r.json()["remaining_courses"] == []

    def test_rbs_shared_core(self):
        r = api_plan(["Finance (BSBA, RBS)"])
        codes = all_codes(r)
        for core in ("EXPOS101", "MATH135", "ECON102", "ACCT272", "FIN300"):
            assert core in codes


class TestSEBS:
    def test_environmental_sciences_bs(self):
        r = api_plan(["Environmental Sciences (BS, SEBS)"])
        assert r.status_code == 200

    def test_marine_sciences_bs(self):
        r = api_plan(["Marine Sciences (BS, SEBS)"])
        assert r.status_code == 200

    def test_biochemistry_bs(self):
        r = api_plan(["Biochemistry (BS, SEBS)"])
        assert r.status_code == 200

    def test_animal_science_bs(self):
        r = api_plan(["Animal Science (BS, SEBS)"])
        assert r.status_code == 200

    def test_nutritional_sciences_bs(self):
        r = api_plan(["Nutritional Sciences (BS, SEBS)"])
        assert r.status_code == 200

    def test_food_science_bs(self):
        r = api_plan(["Food Science (BS, SEBS)"])
        assert r.status_code == 200

    def test_microbiology_bs(self):
        r = api_plan(["Microbiology (BS, SEBS)"])
        assert r.status_code == 200

    def test_landscape_architecture_bsla(self):
        r = api_plan(["Landscape Architecture (BSLA, SEBS)"])
        assert r.status_code == 200

    def test_meteorology_bs(self):
        r = api_plan(["Meteorology (BS, SEBS)"])
        assert r.status_code == 200

    def test_bioengineering_bs(self):
        r = api_plan(["Bioenvironmental Engineering (BS, SEBS)"])
        assert r.status_code == 200


class TestSPPP:
    def test_public_health_bs(self):
        r = api_plan(["Public Health (BS, SPPP)"])
        assert r.status_code == 200

    def test_public_policy_bs(self):
        r = api_plan(["Public Policy (BS, SPPP)"])
        assert r.status_code == 200

    def test_health_administration_bs(self):
        r = api_plan(["Health Administration (BS, SPPP)"])
        assert r.status_code == 200

    def test_urban_planning_bs(self):
        r = api_plan(["Urban Planning and Design (BS, SPPP)"])
        assert r.status_code == 200

    def test_city_planning_ba(self):
        r = api_plan(["City and Regional Planning (BA, SPPP)"])
        assert r.status_code == 200


class TestSSW:
    def test_social_work_ba(self):
        r = api_plan(["Social Work (BA, SSW)"])
        assert r.status_code == 200

    def test_social_work_has_courses(self):
        r = api_plan(["Social Work (BA, SSW)"])
        assert len(r.json()["terms"]) > 0
        assert r.json()["remaining_courses"] == []


class TestSMLR:
    def test_hrm_ba(self):
        r = api_plan(["Human Resource Management (BA, SMLR)"])
        assert r.status_code == 200

    def test_labor_studies_ba(self):
        r = api_plan(["Labor Studies and Employment Relations (BA, SMLR)"])
        assert r.status_code == 200

    def test_labor_relations_bs(self):
        r = api_plan(["Labor and Employment Relations (BS, SMLR)"])
        assert r.status_code == 200


class TestSON:
    def test_nursing_bs(self):
        r = api_plan(["Nursing (BS, SON)"])
        assert r.status_code == 200

    def test_nursing_has_many_courses(self):
        r = api_plan(["Nursing (BS, SON)"])
        codes = all_codes(r)
        assert len(codes) >= 20

    def test_rn_to_bsn(self):
        r = api_plan(["Nursing (RN to BSN) (BS, SON)"])
        assert r.status_code == 200


class TestMGSA:
    def test_dance_bfa(self):
        r = api_plan(["Dance (BFA, MGSA)"])
        assert r.status_code == 200
        codes = all_codes(r)
        assert "DANC100" in codes

    def test_design_bfa(self):
        r = api_plan(["Design (BFA, MGSA)"])
        assert r.status_code == 200

    def test_digital_filmmaking_bfa(self):
        r = api_plan(["Digital Filmmaking (BFA, MGSA)"])
        assert r.status_code == 200

    def test_theater_acting_bfa(self):
        r = api_plan(["Theater (Acting) (BFA, MGSA)"])
        assert r.status_code == 200

    def test_visual_arts_bfa(self):
        r = api_plan(["Visual Arts (BFA, MGSA)"])
        assert r.status_code == 200

    def test_music_composition_bm(self):
        r = api_plan(["Music (Composition) (BM, MGSA)"])
        assert r.status_code == 200

    def test_music_jazz_bm(self):
        r = api_plan(["Music (Jazz Studies) (BM, MGSA)"])
        assert r.status_code == 200

    def test_music_performance_bm(self):
        r = api_plan(["Music (Performance) (BM, MGSA)"])
        assert r.status_code == 200


class TestCrossSchoolDualMajors:
    def test_cs_sas_plus_comp_eng_soe(self):
        r = api_plan([
            "Computer Science (BS, SAS)",
            "Computer Engineering (BS, SOE)",
        ])
        assert r.status_code == 200
        codes = all_codes(r)
        assert "CS111" in codes
        assert "ECE221" in codes or "ENG101" in codes

    def test_cs_sas_plus_iti_sci(self):
        r = api_plan([
            "Computer Science (BS, SAS)",
            "Information Technology and Informatics (BA, SCI)",
        ])
        assert r.status_code == 200
        codes = all_codes(r)
        assert "CS111" in codes
        assert "ITI200" in codes or "SCI103" in codes

    def test_cs_sas_plus_data_science(self):
        r = api_plan([
            "Computer Science (BS, SAS)",
            "Data Science (Computer Science Track) (BS, SAS)",
        ])
        assert r.status_code == 200

    def test_math_sas_plus_econ_sas(self):
        r = api_plan([
            "Mathematics (BS, SAS)",
            "Economics (BA, SAS)",
        ])
        assert r.status_code == 200

    def test_cs_sas_plus_electrical_soe(self):
        r = api_plan([
            "Computer Science (BS, SAS)",
            "Electrical Engineering (BS, SOE)",
        ])
        assert r.status_code == 200
        codes = all_codes(r)
        assert "CS111" in codes
        assert "ECE221" in codes or "ENG101" in codes

    def test_finance_rbs_plus_econ_sas(self):
        r = api_plan([
            "Finance (BSBA, RBS)",
            "Economics (BA, SAS)",
        ])
        assert r.status_code == 200

    def test_public_health_plus_biology(self):
        r = api_plan([
            "Public Health (BS, SPPP)",
            "Biological Sciences (BA, SAS)",
        ])
        assert r.status_code == 200

    def test_iti_sci_plus_communication_sci(self):
        r = api_plan([
            "Information Technology and Informatics (BA, SCI)",
            "Communication (BA, SCI)",
        ])
        assert r.status_code == 200

    def test_cs_sas_plus_journalism_sci(self):
        r = api_plan([
            "Computer Science (BS, SAS)",
            "Journalism and Media Studies (BA, SCI)",
        ])
        assert r.status_code == 200

    def test_biomedical_soe_plus_biochem_sebs(self):
        r = api_plan([
            "Biomedical Engineering (BS, SOE)",
            "Biochemistry (BS, SEBS)",
        ])
        assert r.status_code == 200

    def test_cross_school_no_remaining_with_enough_time(self):
        r = api_plan(
            ["Computer Science (BS, SAS)", "Computer Engineering (BS, SOE)"],
            grad="Spring 2032", max_cr=21,
        )
        assert r.status_code == 200
        assert r.json()["remaining_courses"] == []

    def test_dual_major_elective_count_summed(self):
        r = api_plan(
            ["Computer Science (BS, SAS)", "Mathematics (BS, SAS)"],
            grad="Spring 2032", max_cr=21,
        )
        assert r.status_code == 200
        n = len(elective_codes(r))
        assert n == 9, f"Expected 9 electives (5 CS + 4 Math), got {n}"


class TestCSPlusITIWithCISMinor:
    def test_cs_iti_critical_intelligence_minor(self):
        r = api_plan(
            ["Computer Science (BS, SAS)", "Information Technology and Informatics (BA, SCI)"],
            minors=["Critical Intelligence Studies (Minor, SAS)"],
            grad="Spring 2032",
            max_cr=18,
        )
        assert r.status_code == 200

    def test_critical_intelligence_minor_courses_appear(self):
        r = api_plan(
            ["Computer Science (BS, SAS)"],
            minors=["Critical Intelligence Studies (Minor, SAS)"],
            grad="Spring 2032",
            max_cr=18,
        )
        assert r.status_code == 200
        codes = all_codes(r)
        assert len(codes) > 0

    def test_cs_iti_cis_minor_no_remaining(self):
        r = api_plan(
            ["Computer Science (BS, SAS)", "Information Technology and Informatics (BA, SCI)"],
            minors=["Critical Intelligence Studies (Minor, SAS)"],
            grad="Spring 2032",
            max_cr=21,
        )
        assert r.status_code == 200
        assert r.json()["remaining_courses"] == []


class TestMinorsFromVariousSchools:
    def test_data_science_minor_sas(self):
        r = api_plan(
            ["Computer Science (BS, SAS)"],
            minors=["Data Science (Minor, SAS)"],
        )
        assert r.status_code == 200

    def test_physics_minor_sas(self):
        r = api_plan(
            ["Computer Science (BS, SAS)"],
            minors=["Physics (Minor, SAS)"],
        )
        assert r.status_code == 200

    def test_business_minor_rbs_not_applicable(self):
        r = api_plan(["Computer Science (BS, SAS)"])
        assert r.status_code == 200

    def test_public_health_minor_sppp(self):
        r = api_plan(
            ["Computer Science (BS, SAS)"],
            minors=["Public Health (Minor, SPPP)"],
            grad="Spring 2032",
            max_cr=18,
        )
        assert r.status_code == 200

    def test_urban_planning_minor_sppp(self):
        r = api_plan(
            ["Computer Science (BS, SAS)"],
            minors=["Urban Planning and Design (Minor, SPPP)"],
            grad="Spring 2032",
            max_cr=18,
        )
        assert r.status_code == 200

    def test_city_planning_minor_sppp(self):
        r = api_plan(
            ["Economics (BA, SAS)"],
            minors=["City and Regional Planning (Minor, SPPP)"],
        )
        assert r.status_code == 200

    def test_health_admin_minor_sppp(self):
        r = api_plan(
            ["Biological Sciences (BA, SAS)"],
            minors=["Health Administration (Minor, SPPP)"],
        )
        assert r.status_code == 200

    def test_two_minors_different_schools(self):
        r = api_plan(
            ["Computer Science (BS, SAS)"],
            minors=["Data Science (Minor, SAS)", "Public Health (Minor, SPPP)"],
            grad="Spring 2032",
            max_cr=18,
        )
        assert r.status_code == 200

    def test_three_minors(self):
        r = api_plan(
            ["Computer Science (BS, SAS)"],
            minors=[
                "Mathematics (Minor, SAS)",
                "Statistics (Minor, SAS)",
                "Data Science (Minor, SAS)",
            ],
            grad="Spring 2032",
            max_cr=21,
        )
        assert r.status_code == 200


class TestCompletedCoursesAllSchools:
    def test_soe_completed_core_not_rescheduled(self):
        completed = ["ENG101", "ENG102", "MATH151", "MATH152", "PHYS123", "PHYS124"]
        r = api_plan(["Computer Engineering (BS, SOE)"], completed=completed)
        assert r.status_code == 200
        codes = all_codes(r)
        for c in completed:
            assert c not in codes

    def test_rbs_completed_some_courses(self):
        completed = ["EXPOS101", "MATH135", "ECON102", "ECON103", "STAT285"]
        r = api_plan(["Finance (BSBA, RBS)"], completed=completed)
        assert r.status_code == 200
        codes = all_codes(r)
        for c in completed:
            assert c not in codes

    def test_nursing_completed_half_courses(self):
        completed = [
            "BIOL115", "BIOL116", "CHEM161", "CHEM162", "NUR100",
            "NUR115", "NUR120", "NUR200", "NUR201", "NUR210",
        ]
        r = api_plan(["Nursing (BS, SON)"], completed=completed)
        assert r.status_code == 200
        codes = all_codes(r)
        for c in completed:
            assert c not in codes

    def test_iti_sci_completed_electives_reduces_quota(self):
        from app.database import SessionLocal
        from app.models import Program
        db = SessionLocal()
        iti = db.query(Program).filter(
            Program.school == "SCI",
            Program.major_name == "Information Technology and Informatics"
        ).first()
        db.close()
        opts = iti.requirements["electives"]["options"][:3]
        r = api_plan(
            ["Information Technology and Informatics (BA, SCI)"],
            completed=opts,
        )
        assert r.status_code == 200
        n = len(elective_codes(r))
        assert n == 4, f"Expected 4 remaining electives after completing 3, got {n}"


class TestSeasonPreferences:
    def test_soe_spring_fall_only(self):
        r = api_plan(["Computer Engineering (BS, SOE)"], seasons=["Spring", "Fall"])
        assert r.status_code == 200
        for t in r.json()["terms"]:
            assert not t["term"].startswith("Summer")

    def test_rbs_spring_only(self):
        r = api_plan(["Finance (BSBA, RBS)"], seasons=["Spring"], grad="Spring 2035")
        assert r.status_code == 200
        for t in r.json()["terms"]:
            assert t["term"].startswith("Spring")

    def test_sci_all_seasons(self):
        r = api_plan(
            ["Information Technology and Informatics (BA, SCI)"],
            seasons=["Spring", "Summer", "Fall"],
        )
        assert r.status_code == 200

    def test_no_seasons_returns_warning(self):
        r = client.post("/plan", json={
            "majors": ["Computer Science (BS, SAS)"],
            "minors": [],
            "completed_courses": [],
            "target_grad_term": "Spring 2028",
            "max_credits_per_term": 15,
            "preferred_seasons": [],
        })
        assert r.status_code == 200
        assert len(r.json()["warnings"]) > 0
        assert r.json()["terms"] == []


class TestIntricateSameCampusDuals:
    def test_cs_bs_plus_math_bs(self):
        r = api_plan(["Computer Science (BS, SAS)", "Mathematics (BS, SAS)"],
                     grad="Spring 2032", max_cr=21)
        assert r.status_code == 200
        assert r.json()["remaining_courses"] == []

    def test_cs_bs_plus_physics_ba(self):
        r = api_plan(["Computer Science (BS, SAS)", "Physics (BA, SAS)"],
                     grad="Spring 2032", max_cr=21)
        assert r.status_code == 200

    def test_cs_bs_plus_cognitive_science_ba(self):
        r = api_plan(["Computer Science (BS, SAS)", "Cognitive Science (BA, SAS)"],
                     grad="Spring 2032", max_cr=21)
        assert r.status_code == 200

    def test_econ_ba_plus_political_science_ba(self):
        r = api_plan(["Economics (BA, SAS)", "Political Science (BA, SAS)"])
        assert r.status_code == 200

    def test_biol_ba_plus_chem_bs(self):
        r = api_plan(["Biological Sciences (BA, SAS)", "Chemistry (BS, SAS)"],
                     grad="Spring 2032", max_cr=21)
        assert r.status_code == 200

    def test_data_science_plus_stats(self):
        r = api_plan([
            "Data Science (Computer Science Track) (BS, SAS)",
            "Statistics (BS, SAS)",
        ], grad="Spring 2032", max_cr=21)
        assert r.status_code == 200

    def test_triple_minor_with_dual_major(self):
        r = api_plan(
            ["Computer Science (BS, SAS)", "Mathematics (BS, SAS)"],
            minors=[
                "Data Science (Minor, SAS)",
                "Statistics (Minor, SAS)",
                "Public Health (Minor, SPPP)",
            ],
            grad="Spring 2034",
            max_cr=21,
        )
        assert r.status_code == 200

    def test_cs_and_iti_same_school_sas(self):
        r = api_plan([
            "Computer Science (BS, SAS)",
            "Information Technology and Informatics (BA, SAS)",
        ], grad="Spring 2032", max_cr=21)
        assert r.status_code == 200


class TestPrereqOrderingAllSchools:
    def _term_index(self, term: str) -> int:
        from app.core.planner import _term_index
        return _term_index(term)

    def _scheduled_order(self, resp):
        return {
            c["code"]: t["term"]
            for t in resp.json()["terms"]
            for c in t["courses"]
        }

    def test_soe_math_before_advanced(self):
        r = api_plan(["Computer Engineering (BS, SOE)"])
        order = self._scheduled_order(r)
        if "MATH151" in order and "MATH152" in order:
            assert self._term_index(order["MATH151"]) < self._term_index(order["MATH152"])
        if "MATH152" in order and "MATH251" in order:
            assert self._term_index(order["MATH152"]) <= self._term_index(order["MATH251"])

    def test_rbs_acct272_before_acct325(self):
        r = api_plan(["Accounting (BSBA, RBS)"])
        order = self._scheduled_order(r)
        if "ACCT272" in order and "ACCT325" in order:
            assert self._term_index(order["ACCT272"]) < self._term_index(order["ACCT325"])

    def test_sci_iti200_before_iti201(self):
        r = api_plan(["Information Technology and Informatics (BA, SCI)"])
        order = self._scheduled_order(r)
        if "ITI200" in order and "ITI201" in order:
            assert self._term_index(order["ITI200"]) <= self._term_index(order["ITI201"])
