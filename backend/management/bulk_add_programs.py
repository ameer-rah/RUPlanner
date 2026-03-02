#!/usr/bin/env python3
"""
One-time script to add all missing SAS programs and catalog entries.
Run from backend/:  python -m management.bulk_add_programs
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CATALOG_PATH = DATA_DIR / "sas_catalog.json"
PROGRAMS_PATH = DATA_DIR / "sas_programs.json"

# ---------------------------------------------------------------------------
# NEW CATALOG ENTRIES
# ---------------------------------------------------------------------------
NEW_CATALOG_ENTRIES = [
    # -- CS / Data Science --
    {"code": "CS142", "title": "Data 101: Data Literacy", "credits": 4, "prerequisites": []},
    {"code": "CS439", "title": "Introduction to Data Science", "credits": 3, "prerequisites": ["CS142", "STAT291"]},
    {"code": "CS461", "title": "Machine Learning: Principles and Practice", "credits": 3, "prerequisites": ["MATH250", "CS112"]},
    {"code": "CS462", "title": "Deep Learning", "credits": 3, "prerequisites": ["CS461"]},
    # -- STAT additions --
    {"code": "STAT295", "title": "Data Wrangling and Management with R", "credits": 3, "prerequisites": ["STAT291"]},
    {"code": "STAT365", "title": "Bayesian Data Analysis", "credits": 3, "prerequisites": ["STAT291"]},
    # -- MATH additions --
    {"code": "MATH252", "title": "Elementary Differential Equations", "credits": 3, "prerequisites": ["MATH152"]},
    {"code": "MATH285", "title": "Introduction to Interest Theory for Actuarial Science", "credits": 3, "prerequisites": ["MATH152"]},
    {"code": "MATH336", "title": "Dynamical Models in Biology", "credits": 3, "prerequisites": ["MATH252", "BIO101"]},
    {"code": "MATH338", "title": "Discrete and Probabilistic Models in Biology", "credits": 3, "prerequisites": ["MATH250", "BIO101"]},
    {"code": "MATH477", "title": "Mathematical Theory of Probability", "credits": 3, "prerequisites": ["MATH251"]},
    {"code": "MATH481", "title": "Mathematical Theory of Statistics", "credits": 3, "prerequisites": ["MATH477"]},
    # -- ECON additions --
    {"code": "ECON422", "title": "Advanced Econometrics I", "credits": 3, "prerequisites": ["ECON322"]},
    {"code": "ECON424", "title": "Machine Learning for Economics", "credits": 3, "prerequisites": ["ECON322"]},
    # -- ITI (Information Technology & Informatics) --
    {"code": "ITI103", "title": "IT and Informatics", "credits": 3, "prerequisites": []},
    {"code": "ITI201", "title": "Information Technology Fundamentals", "credits": 3, "prerequisites": []},
    {"code": "ITI321", "title": "Information Visualization", "credits": 3, "prerequisites": ["CS142"]},
    {"code": "ITI301", "title": "Web Design and Development", "credits": 3, "prerequisites": ["ITI201"]},
    {"code": "ITI302", "title": "Database Design", "credits": 3, "prerequisites": ["ITI201"]},
    {"code": "ITI401", "title": "Advanced Topics in IT", "credits": 3, "prerequisites": ["ITI301"]},
    # -- GEOSC additions for EPS programs --
    {"code": "GEOSC300", "title": "Introduction to Sedimentary Geology", "credits": 4, "prerequisites": ["GEOSC101"]},
    {"code": "GEOSC302", "title": "Petrology", "credits": 4, "prerequisites": ["GEOSC301"]},
    {"code": "GEOSC304", "title": "Introduction to Geochemistry", "credits": 4, "prerequisites": ["GEOSC301", "CHEM161"]},
    {"code": "GEOSC306", "title": "Introduction to Geophysics", "credits": 4, "prerequisites": ["GEOSC101", "PHYS203", "MATH152"]},
    {"code": "GEOSC410", "title": "Field Geology", "credits": 3, "prerequisites": ["GEOSC301"]},
    {"code": "GEOSC413", "title": "Environmental Geochemistry", "credits": 3, "prerequisites": ["GEOSC304"]},
    {"code": "GEOSC428", "title": "Hydrogeology", "credits": 3, "prerequisites": ["GEOSC306"]},
    {"code": "GEOSC222", "title": "Planet Mars", "credits": 3, "prerequisites": ["GEOSC101"]},
    {"code": "GEOSC441", "title": "Structure and Formation of Terrestrial Planets", "credits": 3, "prerequisites": ["GEOSC301", "PHYS203"]},
    # -- PHYS additions --
    {"code": "PHYS313", "title": "Mathematical Methods in Physics", "credits": 3, "prerequisites": ["PHYS227", "MATH251"]},
    {"code": "PHYS323", "title": "Advanced Mechanics", "credits": 3, "prerequisites": ["PHYS227", "MATH152"]},
    {"code": "PHYS324", "title": "Electrodynamics", "credits": 3, "prerequisites": ["PHYS323", "MATH251"]},
    # -- Languages: FRENCH --
    {"code": "FREN101", "title": "Elementary French I", "credits": 4, "prerequisites": []},
    {"code": "FREN102", "title": "Elementary French II", "credits": 4, "prerequisites": ["FREN101"]},
    {"code": "FREN131", "title": "Intensive Intermediate French", "credits": 4, "prerequisites": ["FREN102"]},
    {"code": "FREN213", "title": "Advanced French I", "credits": 3, "prerequisites": ["FREN131"]},
    {"code": "FREN214", "title": "Advanced French II", "credits": 3, "prerequisites": ["FREN213"]},
    {"code": "FREN215", "title": "Introduction to French Literature I", "credits": 3, "prerequisites": ["FREN213"]},
    {"code": "FREN216", "title": "Introduction to French Literature II", "credits": 3, "prerequisites": ["FREN213"]},
    {"code": "FREN301", "title": "Topics in French Literature", "credits": 3, "prerequisites": ["FREN214"]},
    {"code": "FREN302", "title": "Topics in French Culture", "credits": 3, "prerequisites": ["FREN214"]},
    {"code": "FREN303", "title": "French Film and Media", "credits": 3, "prerequisites": ["FREN214"]},
    {"code": "FREN401", "title": "Advanced Topics in French Studies", "credits": 3, "prerequisites": ["FREN301"]},
    {"code": "FREN402", "title": "Francophone Literatures", "credits": 3, "prerequisites": ["FREN301"]},
    {"code": "FREN480", "title": "Senior Seminar in French", "credits": 3, "prerequisites": ["FREN301"]},
    # -- GERMAN --
    {"code": "GERM101", "title": "Elementary German I", "credits": 4, "prerequisites": []},
    {"code": "GERM102", "title": "Elementary German II", "credits": 4, "prerequisites": ["GERM101"]},
    {"code": "GERM201", "title": "Intermediate German I", "credits": 3, "prerequisites": ["GERM102"]},
    {"code": "GERM202", "title": "Intermediate German II", "credits": 3, "prerequisites": ["GERM201"]},
    {"code": "GERM232", "title": "Advanced German", "credits": 3, "prerequisites": ["GERM202"]},
    {"code": "GERM301", "title": "Topics in German Literature", "credits": 3, "prerequisites": ["GERM232"]},
    {"code": "GERM302", "title": "Topics in German Culture", "credits": 3, "prerequisites": ["GERM232"]},
    {"code": "GERM303", "title": "German Film and Media", "credits": 3, "prerequisites": ["GERM232"]},
    {"code": "GERM401", "title": "Advanced Topics in German Studies", "credits": 3, "prerequisites": ["GERM301"]},
    {"code": "GERM402", "title": "German Intellectual History", "credits": 3, "prerequisites": ["GERM301"]},
    # -- ITALIAN --
    {"code": "ITAL101", "title": "Elementary Italian I", "credits": 3, "prerequisites": []},
    {"code": "ITAL102", "title": "Elementary Italian II", "credits": 3, "prerequisites": ["ITAL101"]},
    {"code": "ITAL121", "title": "Intensive Intermediate Italian", "credits": 4, "prerequisites": ["ITAL101"]},
    {"code": "ITAL131", "title": "Intermediate Italian", "credits": 3, "prerequisites": ["ITAL102"]},
    {"code": "ITAL201", "title": "Advanced Italian I", "credits": 3, "prerequisites": ["ITAL131"]},
    {"code": "ITAL202", "title": "Advanced Italian II", "credits": 3, "prerequisites": ["ITAL201"]},
    {"code": "ITAL231", "title": "Italian Culture I", "credits": 3, "prerequisites": ["ITAL201"]},
    {"code": "ITAL232", "title": "Italian Culture II", "credits": 3, "prerequisites": ["ITAL201"]},
    {"code": "ITAL321", "title": "Advanced Conversation in Italian", "credits": 3, "prerequisites": ["ITAL201"]},
    {"code": "ITAL322", "title": "Advanced Conversation through Italian Cinema", "credits": 3, "prerequisites": ["ITAL201"]},
    {"code": "ITAL301", "title": "Introduction to Italian Literature I", "credits": 3, "prerequisites": ["ITAL201"]},
    {"code": "ITAL302", "title": "Introduction to Italian Literature II", "credits": 3, "prerequisites": ["ITAL201"]},
    {"code": "ITAL401", "title": "Advanced Topics in Italian Studies", "credits": 3, "prerequisites": ["ITAL301"]},
    # -- JAPANESE --
    {"code": "JPN101", "title": "Elementary Japanese I", "credits": 4, "prerequisites": []},
    {"code": "JPN102", "title": "Elementary Japanese II", "credits": 4, "prerequisites": ["JPN101"]},
    {"code": "JPN201", "title": "Intermediate Japanese I", "credits": 4, "prerequisites": ["JPN102"]},
    {"code": "JPN202", "title": "Intermediate Japanese II", "credits": 4, "prerequisites": ["JPN201"]},
    {"code": "JPN301", "title": "Advanced Japanese I", "credits": 3, "prerequisites": ["JPN202"]},
    {"code": "JPN302", "title": "Advanced Japanese II", "credits": 3, "prerequisites": ["JPN301"]},
    {"code": "JPN401", "title": "Topics in Japanese Culture", "credits": 3, "prerequisites": ["JPN301"]},
    {"code": "JPN402", "title": "Topics in Japanese Literature", "credits": 3, "prerequisites": ["JPN301"]},
    # -- CHINESE --
    {"code": "CHN101", "title": "Elementary Chinese I", "credits": 4, "prerequisites": []},
    {"code": "CHN102", "title": "Elementary Chinese II", "credits": 4, "prerequisites": ["CHN101"]},
    {"code": "CHN201", "title": "Intermediate Chinese I", "credits": 4, "prerequisites": ["CHN102"]},
    {"code": "CHN202", "title": "Intermediate Chinese II", "credits": 4, "prerequisites": ["CHN201"]},
    {"code": "CHN301", "title": "Advanced Chinese I", "credits": 3, "prerequisites": ["CHN202"]},
    {"code": "CHN302", "title": "Advanced Chinese II", "credits": 3, "prerequisites": ["CHN301"]},
    {"code": "CHN401", "title": "Topics in Chinese Culture and Literature", "credits": 3, "prerequisites": ["CHN301"]},
    {"code": "CHN402", "title": "Topics in Chinese Civilization", "credits": 3, "prerequisites": ["CHN301"]},
    # -- KOREAN --
    {"code": "KOR101", "title": "Elementary Korean I", "credits": 4, "prerequisites": []},
    {"code": "KOR102", "title": "Elementary Korean II", "credits": 4, "prerequisites": ["KOR101"]},
    {"code": "KOR201", "title": "Intermediate Korean I", "credits": 4, "prerequisites": ["KOR102"]},
    {"code": "KOR202", "title": "Intermediate Korean II", "credits": 4, "prerequisites": ["KOR201"]},
    {"code": "KOR301", "title": "Advanced Korean I", "credits": 3, "prerequisites": ["KOR202"]},
    {"code": "KOR302", "title": "Advanced Korean II", "credits": 3, "prerequisites": ["KOR301"]},
    {"code": "KOR401", "title": "Topics in Korean Language and Culture", "credits": 3, "prerequisites": ["KOR301"]},
    # -- RUSSIAN --
    {"code": "RUSS101", "title": "Elementary Russian I", "credits": 4, "prerequisites": []},
    {"code": "RUSS102", "title": "Elementary Russian II", "credits": 4, "prerequisites": ["RUSS101"]},
    {"code": "RUSS201", "title": "Intermediate Russian I", "credits": 3, "prerequisites": ["RUSS102"]},
    {"code": "RUSS202", "title": "Intermediate Russian II", "credits": 3, "prerequisites": ["RUSS201"]},
    {"code": "RUSS301", "title": "Advanced Russian", "credits": 3, "prerequisites": ["RUSS202"]},
    {"code": "RUSS302", "title": "Russian Literature in Translation", "credits": 3, "prerequisites": ["RUSS202"]},
    {"code": "RUSS401", "title": "Topics in Russian Literature and Culture", "credits": 3, "prerequisites": ["RUSS301"]},
    {"code": "RUSS402", "title": "Topics in Russian Civilization", "credits": 3, "prerequisites": ["RUSS301"]},
    # -- PORTUGUESE --
    {"code": "PORT101", "title": "Elementary Portuguese I", "credits": 4, "prerequisites": []},
    {"code": "PORT102", "title": "Elementary Portuguese II", "credits": 4, "prerequisites": ["PORT101"]},
    {"code": "PORT201", "title": "Intermediate Portuguese I", "credits": 3, "prerequisites": ["PORT102"]},
    {"code": "PORT202", "title": "Intermediate Portuguese II", "credits": 3, "prerequisites": ["PORT201"]},
    {"code": "PORT301", "title": "Advanced Portuguese", "credits": 3, "prerequisites": ["PORT202"]},
    {"code": "PORT302", "title": "Portuguese Literature and Culture", "credits": 3, "prerequisites": ["PORT202"]},
    {"code": "PORT401", "title": "Topics in Lusophone Literature and Culture", "credits": 3, "prerequisites": ["PORT301"]},
    {"code": "PORT402", "title": "Topics in Brazilian Literature", "credits": 3, "prerequisites": ["PORT301"]},
    # -- MUSIC --
    {"code": "MUS101", "title": "Introduction to Music Theory", "credits": 3, "prerequisites": []},
    {"code": "MUS102", "title": "Music Theory II", "credits": 3, "prerequisites": ["MUS101"]},
    {"code": "MUS105", "title": "Introduction to Music and its Literature", "credits": 3, "prerequisites": []},
    {"code": "MUS202", "title": "Music History I: Ancient to Baroque", "credits": 3, "prerequisites": []},
    {"code": "MUS203", "title": "Music History II: Classical and Romantic", "credits": 3, "prerequisites": []},
    {"code": "MUS204", "title": "Music History III: 20th Century to Present", "credits": 3, "prerequisites": []},
    {"code": "MUS207", "title": "Music Theory III", "credits": 3, "prerequisites": ["MUS102"]},
    {"code": "MUS208", "title": "Music Theory IV: Form and Analysis", "credits": 3, "prerequisites": ["MUS207"]},
    {"code": "MUS301", "title": "Music Composition", "credits": 3, "prerequisites": ["MUS207"]},
    {"code": "MUS302", "title": "Topics in Music Studies", "credits": 3, "prerequisites": ["MUS207"]},
    {"code": "MUS303", "title": "Ethnomusicology", "credits": 3, "prerequisites": []},
    {"code": "MUS400", "title": "Advanced Seminar in Music", "credits": 3, "prerequisites": ["MUS301"]},
    # -- THEATER ARTS --
    {"code": "THEA101", "title": "Introduction to Theater Arts", "credits": 3, "prerequisites": []},
    {"code": "THEA102", "title": "Acting I", "credits": 3, "prerequisites": []},
    {"code": "THEA103", "title": "Technical Theater", "credits": 3, "prerequisites": []},
    {"code": "THEA200", "title": "History of Theater I", "credits": 3, "prerequisites": []},
    {"code": "THEA201", "title": "Acting II", "credits": 3, "prerequisites": ["THEA102"]},
    {"code": "THEA202", "title": "Directing", "credits": 3, "prerequisites": ["THEA101"]},
    {"code": "THEA203", "title": "Stagecraft and Design", "credits": 3, "prerequisites": []},
    {"code": "THEA204", "title": "History of Theater II", "credits": 3, "prerequisites": []},
    {"code": "THEA301", "title": "Advanced Acting", "credits": 3, "prerequisites": ["THEA201"]},
    {"code": "THEA302", "title": "Dramatic Literature", "credits": 3, "prerequisites": ["THEA101"]},
    {"code": "THEA303", "title": "Playwriting", "credits": 3, "prerequisites": ["THEA101"]},
    {"code": "THEA400", "title": "Senior Seminar in Theater", "credits": 3, "prerequisites": ["THEA301"]},
    # -- DANCE --
    {"code": "DANC101", "title": "Introduction to Dance", "credits": 3, "prerequisites": []},
    {"code": "DANC102", "title": "Dance Technique I", "credits": 3, "prerequisites": []},
    {"code": "DANC200", "title": "History of Dance", "credits": 3, "prerequisites": []},
    {"code": "DANC201", "title": "Dance Technique II", "credits": 3, "prerequisites": ["DANC102"]},
    {"code": "DANC202", "title": "Dance Composition I", "credits": 3, "prerequisites": ["DANC101"]},
    {"code": "DANC203", "title": "Dance and Culture", "credits": 3, "prerequisites": []},
    {"code": "DANC301", "title": "Advanced Dance Technique", "credits": 3, "prerequisites": ["DANC201"]},
    {"code": "DANC302", "title": "Dance Composition II", "credits": 3, "prerequisites": ["DANC202"]},
    {"code": "DANC303", "title": "Choreography", "credits": 3, "prerequisites": ["DANC202"]},
    {"code": "DANC400", "title": "Senior Seminar in Dance", "credits": 3, "prerequisites": ["DANC301"]},
    # -- CINEMA STUDIES --
    {"code": "CINE201", "title": "Introduction to Cinema Studies", "credits": 3, "prerequisites": []},
    {"code": "CINE202", "title": "Film History I", "credits": 3, "prerequisites": []},
    {"code": "CINE203", "title": "Film History II", "credits": 3, "prerequisites": ["CINE202"]},
    {"code": "CINE301", "title": "Film Theory", "credits": 3, "prerequisites": ["CINE201"]},
    {"code": "CINE302", "title": "Topics in World Cinema", "credits": 3, "prerequisites": ["CINE201"]},
    {"code": "CINE303", "title": "Documentary Film", "credits": 3, "prerequisites": ["CINE201"]},
    {"code": "CINE401", "title": "Advanced Topics in Cinema Studies", "credits": 3, "prerequisites": ["CINE301"]},
    {"code": "CINE402", "title": "Senior Seminar in Cinema", "credits": 3, "prerequisites": ["CINE301"]},
    # -- RELIGION --
    {"code": "RELGS101", "title": "Introduction to Religion", "credits": 3, "prerequisites": []},
    {"code": "RELGS200", "title": "World Religions", "credits": 3, "prerequisites": []},
    {"code": "RELGS201", "title": "Religion and Society", "credits": 3, "prerequisites": []},
    {"code": "RELGS301", "title": "Topics in Religious Studies", "credits": 3, "prerequisites": ["RELGS101"]},
    {"code": "RELGS302", "title": "Religion and Culture", "credits": 3, "prerequisites": ["RELGS101"]},
    {"code": "RELGS303", "title": "Religion in America", "credits": 3, "prerequisites": []},
    {"code": "RELGS401", "title": "Advanced Topics in Religion", "credits": 3, "prerequisites": ["RELGS301"]},
    # -- CLASSICS --
    {"code": "CLASS101", "title": "Introduction to Classical Studies", "credits": 3, "prerequisites": []},
    {"code": "CLASS102", "title": "Greek Civilization", "credits": 3, "prerequisites": []},
    {"code": "CLASS103", "title": "Roman Civilization", "credits": 3, "prerequisites": []},
    {"code": "CLASS201", "title": "Classical Mythology", "credits": 3, "prerequisites": []},
    {"code": "CLASS202", "title": "Classical Literature in Translation", "credits": 3, "prerequisites": []},
    {"code": "CLASS301", "title": "Topics in Greek Literature", "credits": 3, "prerequisites": ["CLASS201"]},
    {"code": "CLASS302", "title": "Topics in Roman Literature", "credits": 3, "prerequisites": ["CLASS201"]},
    {"code": "CLASS401", "title": "Advanced Topics in Classics", "credits": 3, "prerequisites": ["CLASS301"]},
    {"code": "GREK101", "title": "Elementary Ancient Greek I", "credits": 4, "prerequisites": []},
    {"code": "GREK102", "title": "Elementary Ancient Greek II", "credits": 4, "prerequisites": ["GREK101"]},
    {"code": "GREK201", "title": "Intermediate Ancient Greek", "credits": 3, "prerequisites": ["GREK102"]},
    {"code": "GREK301", "title": "Advanced Greek Readings", "credits": 3, "prerequisites": ["GREK201"]},
    {"code": "LAT101", "title": "Elementary Latin I", "credits": 4, "prerequisites": []},
    {"code": "LAT102", "title": "Elementary Latin II", "credits": 4, "prerequisites": ["LAT101"]},
    {"code": "LAT201", "title": "Intermediate Latin", "credits": 3, "prerequisites": ["LAT102"]},
    {"code": "LAT301", "title": "Advanced Latin Readings", "credits": 3, "prerequisites": ["LAT201"]},
    # -- COMPARATIVE LITERATURE --
    {"code": "COMPLIT201", "title": "Introduction to Comparative Literature", "credits": 3, "prerequisites": []},
    {"code": "COMPLIT202", "title": "World Literature", "credits": 3, "prerequisites": []},
    {"code": "COMPLIT301", "title": "Topics in Comparative Literature", "credits": 3, "prerequisites": ["COMPLIT201"]},
    {"code": "COMPLIT302", "title": "Literature and Theory", "credits": 3, "prerequisites": ["COMPLIT201"]},
    {"code": "COMPLIT401", "title": "Advanced Topics in Comparative Literature", "credits": 3, "prerequisites": ["COMPLIT301"]},
    {"code": "COMPLIT402", "title": "Senior Seminar in Comparative Literature", "credits": 3, "prerequisites": ["COMPLIT301"]},
    # -- JOURNALISM & MEDIA STUDIES --
    {"code": "JOUR101", "title": "Introduction to Journalism and Media Studies", "credits": 3, "prerequisites": []},
    {"code": "JOUR201", "title": "News Writing and Reporting", "credits": 3, "prerequisites": ["JOUR101"]},
    {"code": "JOUR202", "title": "Media and Society", "credits": 3, "prerequisites": []},
    {"code": "JOUR203", "title": "Digital Media Production", "credits": 3, "prerequisites": ["JOUR101"]},
    {"code": "JOUR301", "title": "Advanced Reporting", "credits": 3, "prerequisites": ["JOUR201"]},
    {"code": "JOUR302", "title": "Broadcast Journalism", "credits": 3, "prerequisites": ["JOUR201"]},
    {"code": "JOUR303", "title": "Sports Journalism", "credits": 3, "prerequisites": ["JOUR201"]},
    {"code": "JOUR401", "title": "Media Law and Ethics", "credits": 3, "prerequisites": ["JOUR201"]},
    {"code": "JOUR402", "title": "Senior Seminar in Journalism", "credits": 3, "prerequisites": ["JOUR301"]},
    # -- STUDIO ART --
    {"code": "ART101", "title": "Foundation Drawing", "credits": 3, "prerequisites": []},
    {"code": "ART102", "title": "Foundation 2D Design", "credits": 3, "prerequisites": []},
    {"code": "ART103", "title": "Foundation 3D Design", "credits": 3, "prerequisites": []},
    {"code": "ART201", "title": "Intermediate Drawing", "credits": 3, "prerequisites": ["ART101"]},
    {"code": "ART202", "title": "Painting I", "credits": 3, "prerequisites": ["ART101"]},
    {"code": "ART203", "title": "Sculpture I", "credits": 3, "prerequisites": ["ART103"]},
    {"code": "ART204", "title": "Printmaking I", "credits": 3, "prerequisites": ["ART101"]},
    {"code": "ART205", "title": "Photography I", "credits": 3, "prerequisites": []},
    {"code": "ART301", "title": "Advanced Drawing", "credits": 3, "prerequisites": ["ART201"]},
    {"code": "ART302", "title": "Painting II", "credits": 3, "prerequisites": ["ART202"]},
    {"code": "ART303", "title": "Sculpture II", "credits": 3, "prerequisites": ["ART203"]},
    {"code": "ART401", "title": "Senior Studio", "credits": 3, "prerequisites": ["ART301"]},
    {"code": "ART402", "title": "Senior Seminar in Art", "credits": 3, "prerequisites": ["ART301"]},
    # -- EXERCISE SCIENCE (Kinesiology) --
    {"code": "EXSC140", "title": "Foundations of Kinesiology and Health", "credits": 3, "prerequisites": []},
    {"code": "EXSC200", "title": "Principles of a Healthy Lifestyle", "credits": 3, "prerequisites": []},
    {"code": "EXSC225", "title": "Human Anatomy", "credits": 3, "prerequisites": ["BIO101"]},
    {"code": "EXSC226", "title": "Human Physiology", "credits": 3, "prerequisites": ["EXSC225"]},
    {"code": "EXSC227", "title": "Anatomy and Physiology Lab", "credits": 1, "prerequisites": ["EXSC225"]},
    {"code": "EXSC301", "title": "Exercise Physiology", "credits": 3, "prerequisites": ["EXSC226"]},
    {"code": "EXSC302", "title": "Biomechanics", "credits": 3, "prerequisites": ["PHYS203"]},
    {"code": "EXSC303", "title": "Motor Behavior", "credits": 3, "prerequisites": []},
    {"code": "EXSC304", "title": "Exercise Testing and Prescription", "credits": 3, "prerequisites": ["EXSC301"]},
    {"code": "EXSC305", "title": "Sport Nutrition", "credits": 3, "prerequisites": ["EXSC226"]},
    {"code": "EXSC400", "title": "Advanced Exercise Physiology", "credits": 3, "prerequisites": ["EXSC301"]},
    {"code": "EXSC401", "title": "Clinical Exercise Physiology", "credits": 3, "prerequisites": ["EXSC304"]},
    {"code": "EXSC490", "title": "Internship in Exercise Science", "credits": 6, "prerequisites": ["EXSC304"]},
    # -- SPORT MANAGEMENT --
    {"code": "SPMD101", "title": "Introduction to Sport Management", "credits": 3, "prerequisites": []},
    {"code": "SPMD201", "title": "Sport Marketing", "credits": 3, "prerequisites": ["SPMD101"]},
    {"code": "SPMD202", "title": "Sport Finance", "credits": 3, "prerequisites": ["SPMD101"]},
    {"code": "SPMD203", "title": "Sport Communication", "credits": 3, "prerequisites": ["SPMD101"]},
    {"code": "SPMD301", "title": "Sport Law", "credits": 3, "prerequisites": ["SPMD101"]},
    {"code": "SPMD302", "title": "Sport Event Management", "credits": 3, "prerequisites": ["SPMD201"]},
    {"code": "SPMD401", "title": "Sport Management Capstone", "credits": 3, "prerequisites": ["SPMD302"]},
    {"code": "SPMD490", "title": "Sport Management Internship", "credits": 3, "prerequisites": ["SPMD201"]},
    # -- PUBLIC HEALTH --
    {"code": "PUBH201", "title": "Principles of Public Health", "credits": 3, "prerequisites": []},
    {"code": "PUBH212", "title": "Introduction to Health Disparities", "credits": 3, "prerequisites": []},
    {"code": "PUBH240", "title": "Global Health Perspectives", "credits": 3, "prerequisites": []},
    {"code": "PUBH335", "title": "Epidemiology", "credits": 3, "prerequisites": ["STAT211", "PUBH201"]},
    {"code": "PUBH356", "title": "Public Health Law and Ethics", "credits": 3, "prerequisites": ["PUBH201"]},
    {"code": "PUBH395", "title": "Research Methods in Public Health", "credits": 4, "prerequisites": ["STAT211"]},
    {"code": "PUBH450", "title": "Leadership Seminar in Public Health", "credits": 3, "prerequisites": ["PUBH335"]},
    {"code": "PUBH499", "title": "Professional Practice Internship in Public Health", "credits": 6, "prerequisites": ["PUBH335"]},
    # -- PUBLIC POLICY --
    {"code": "PUBP201", "title": "Introduction to Public Policy", "credits": 3, "prerequisites": []},
    {"code": "PUBP301", "title": "Policy Analysis", "credits": 3, "prerequisites": ["PUBP201"]},
    {"code": "PUBP302", "title": "Public Finance", "credits": 3, "prerequisites": ["PUBP201", "ECON102"]},
    {"code": "PUBP303", "title": "Public Administration", "credits": 3, "prerequisites": ["PUBP201"]},
    {"code": "PUBP401", "title": "Advanced Policy Seminar", "credits": 3, "prerequisites": ["PUBP301"]},
    {"code": "PUBP402", "title": "Policy Capstone", "credits": 3, "prerequisites": ["PUBP301"]},
    # -- HEALTH ADMINISTRATION --
    {"code": "HLAD201", "title": "Introduction to Health Administration", "credits": 3, "prerequisites": []},
    {"code": "HLAD202", "title": "Health Care Organization and Delivery", "credits": 3, "prerequisites": []},
    {"code": "HLAD301", "title": "Health Care Systems", "credits": 3, "prerequisites": ["HLAD201"]},
    {"code": "HLAD302", "title": "Health Policy", "credits": 3, "prerequisites": ["HLAD201"]},
    {"code": "HLAD303", "title": "Health Care Finance", "credits": 3, "prerequisites": ["HLAD201"]},
    {"code": "HLAD401", "title": "Health Administration Internship", "credits": 6, "prerequisites": ["HLAD301"]},
    # -- LABOR STUDIES & EMPLOYMENT RELATIONS --
    {"code": "LER101", "title": "Introduction to Labor Studies", "credits": 3, "prerequisites": []},
    {"code": "LER102", "title": "Work, Labor, and Society", "credits": 3, "prerequisites": []},
    {"code": "LER201", "title": "Employment Relations", "credits": 3, "prerequisites": ["LER101"]},
    {"code": "LER202", "title": "Labor History", "credits": 3, "prerequisites": []},
    {"code": "LER301", "title": "Labor Law", "credits": 3, "prerequisites": ["LER101"]},
    {"code": "LER302", "title": "Collective Bargaining", "credits": 3, "prerequisites": ["LER201"]},
    {"code": "LER401", "title": "Advanced Topics in Labor Studies", "credits": 3, "prerequisites": ["LER301"]},
    {"code": "LER490", "title": "Internship in Labor Studies", "credits": 3, "prerequisites": ["LER201"]},
    # -- HUMAN RESOURCE MANAGEMENT --
    {"code": "HRM201", "title": "Human Resource Management", "credits": 3, "prerequisites": []},
    {"code": "HRM202", "title": "Organizational Behavior", "credits": 3, "prerequisites": []},
    {"code": "HRM301", "title": "Staffing and Recruitment", "credits": 3, "prerequisites": ["HRM201"]},
    {"code": "HRM302", "title": "Compensation and Benefits", "credits": 3, "prerequisites": ["HRM201"]},
    {"code": "HRM303", "title": "Training and Development", "credits": 3, "prerequisites": ["HRM201"]},
    {"code": "HRM401", "title": "Strategic Human Resource Management", "credits": 3, "prerequisites": ["HRM301"]},
    # -- SOCIAL WORK --
    {"code": "SOCW101", "title": "Introduction to Social Work", "credits": 3, "prerequisites": []},
    {"code": "SOCW201", "title": "Social Welfare Policy", "credits": 3, "prerequisites": []},
    {"code": "SOCW202", "title": "Human Behavior and the Social Environment", "credits": 3, "prerequisites": []},
    {"code": "SOCW301", "title": "Social Work Practice I", "credits": 3, "prerequisites": ["SOCW101"]},
    {"code": "SOCW302", "title": "Social Work Practice II", "credits": 3, "prerequisites": ["SOCW301"]},
    {"code": "SOCW401", "title": "Social Work Field Practicum", "credits": 6, "prerequisites": ["SOCW302"]},
    # -- URBAN PLANNING & DESIGN / CITY AND REGIONAL PLANNING --
    {"code": "UPD101", "title": "Introduction to Urban Planning", "credits": 3, "prerequisites": []},
    {"code": "UPD201", "title": "Urban Planning History and Theory", "credits": 3, "prerequisites": []},
    {"code": "UPD202", "title": "Planning Methods", "credits": 3, "prerequisites": ["UPD201"]},
    {"code": "UPD301", "title": "Land Use Planning", "credits": 3, "prerequisites": ["UPD201"]},
    {"code": "UPD302", "title": "Transportation Planning", "credits": 3, "prerequisites": ["UPD201"]},
    {"code": "UPD303", "title": "Environmental Planning", "credits": 3, "prerequisites": ["UPD201"]},
    {"code": "UPD401", "title": "Advanced Planning Studio", "credits": 3, "prerequisites": ["UPD301"]},
    {"code": "UPD402", "title": "Planning Capstone", "credits": 3, "prerequisites": ["UPD301"]},
    # -- AREA STUDIES --
    # Jewish Studies
    {"code": "JWST101", "title": "Introduction to Jewish Studies", "credits": 3, "prerequisites": []},
    {"code": "JWST201", "title": "Jewish History I: Ancient to Medieval", "credits": 3, "prerequisites": []},
    {"code": "JWST202", "title": "Jewish History II: Modern", "credits": 3, "prerequisites": []},
    {"code": "JWST301", "title": "Topics in Jewish Culture and Thought", "credits": 3, "prerequisites": ["JWST101"]},
    {"code": "JWST302", "title": "Topics in Jewish Literature", "credits": 3, "prerequisites": ["JWST101"]},
    {"code": "JWST401", "title": "Advanced Topics in Jewish Studies", "credits": 3, "prerequisites": ["JWST301"]},
    # Asian Studies
    {"code": "AMES101", "title": "Introduction to Asian Studies", "credits": 3, "prerequisites": []},
    {"code": "AMES201", "title": "Asian History and Culture", "credits": 3, "prerequisites": []},
    {"code": "AMES202", "title": "Contemporary Asia", "credits": 3, "prerequisites": []},
    {"code": "AMES301", "title": "Topics in Asian Studies", "credits": 3, "prerequisites": ["AMES101"]},
    {"code": "AMES401", "title": "Advanced Topics in Asian Studies", "credits": 3, "prerequisites": ["AMES301"]},
    # Latin American Studies
    {"code": "LAS101", "title": "Introduction to Latin American Studies", "credits": 3, "prerequisites": []},
    {"code": "LAS201", "title": "Latin American History", "credits": 3, "prerequisites": []},
    {"code": "LAS202", "title": "Latin American Culture and Society", "credits": 3, "prerequisites": []},
    {"code": "LAS301", "title": "Topics in Latin American Studies", "credits": 3, "prerequisites": ["LAS101"]},
    {"code": "LAS401", "title": "Advanced Topics in Latin American Studies", "credits": 3, "prerequisites": ["LAS301"]},
    # Latino and Caribbean Studies
    {"code": "LCS101", "title": "Introduction to Latino and Caribbean Studies", "credits": 3, "prerequisites": []},
    {"code": "LCS201", "title": "Latinos in the United States", "credits": 3, "prerequisites": []},
    {"code": "LCS202", "title": "Caribbean History and Culture", "credits": 3, "prerequisites": []},
    {"code": "LCS301", "title": "Topics in Latino and Caribbean Studies", "credits": 3, "prerequisites": ["LCS101"]},
    {"code": "LCS401", "title": "Advanced Topics in Latino and Caribbean Studies", "credits": 3, "prerequisites": ["LCS301"]},
    # European Studies
    {"code": "EURO101", "title": "Introduction to European Studies", "credits": 3, "prerequisites": []},
    {"code": "EURO201", "title": "European History and Culture", "credits": 3, "prerequisites": []},
    {"code": "EURO202", "title": "Contemporary European Politics", "credits": 3, "prerequisites": []},
    {"code": "EURO301", "title": "Topics in European Studies", "credits": 3, "prerequisites": ["EURO101"]},
    {"code": "EURO401", "title": "Advanced Topics in European Studies", "credits": 3, "prerequisites": ["EURO301"]},
    # Middle Eastern Studies
    {"code": "MES101", "title": "Introduction to Middle Eastern Studies", "credits": 3, "prerequisites": []},
    {"code": "MES201", "title": "Middle Eastern History", "credits": 3, "prerequisites": []},
    {"code": "MES202", "title": "Islam: History and Civilization", "credits": 3, "prerequisites": []},
    {"code": "MES301", "title": "Topics in Middle Eastern Studies", "credits": 3, "prerequisites": ["MES101"]},
    {"code": "MES401", "title": "Advanced Topics in Middle Eastern Studies", "credits": 3, "prerequisites": ["MES301"]},
    # AMESALL (African, Middle Eastern & South Asian Languages & Literatures)
    {"code": "AMESALL101", "title": "Introduction to African and Asian Languages and Literatures", "credits": 3, "prerequisites": []},
    {"code": "AMESALL201", "title": "Literatures of the Middle East", "credits": 3, "prerequisites": []},
    {"code": "AMESALL202", "title": "Literatures of South Asia", "credits": 3, "prerequisites": []},
    {"code": "AMESALL301", "title": "Advanced Topics in African and Asian Studies", "credits": 3, "prerequisites": ["AMESALL101"]},
    {"code": "AMESALL401", "title": "Senior Seminar in AMESALL", "credits": 3, "prerequisites": ["AMESALL301"]},
    # Global Humanities
    {"code": "GLHUM101", "title": "Introduction to Global Humanities", "credits": 3, "prerequisites": []},
    {"code": "GLHUM201", "title": "Global Cultures and Texts", "credits": 3, "prerequisites": []},
    {"code": "GLHUM301", "title": "Topics in Global Humanities", "credits": 3, "prerequisites": ["GLHUM201"]},
    {"code": "GLHUM401", "title": "Senior Seminar in Global Humanities", "credits": 3, "prerequisites": ["GLHUM301"]},
    # Medieval Studies
    {"code": "MEDST201", "title": "Introduction to Medieval Studies", "credits": 3, "prerequisites": []},
    {"code": "MEDST202", "title": "Medieval Literature", "credits": 3, "prerequisites": []},
    {"code": "MEDST203", "title": "Medieval History and Culture", "credits": 3, "prerequisites": []},
    {"code": "MEDST301", "title": "Topics in Medieval Studies", "credits": 3, "prerequisites": ["MEDST201"]},
    {"code": "MEDST401", "title": "Advanced Topics in Medieval Studies", "credits": 3, "prerequisites": ["MEDST301"]},
]

# ---------------------------------------------------------------------------
# NEW PROGRAMS
# ---------------------------------------------------------------------------
NEW_PROGRAMS = {
    # ===================== STEM =====================
    "biological_sciences_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Biological Sciences",
        "catalog_year": "2025-2026",
        "required_courses": [
            "BIO101", "BIO102",
            "CHEM161", "CHEM162", "CHEM171",
            "CHEM307", "CHEM308", "CHEM309", "CHEM311",
            "PHYS203", "PHYS205", "PHYS204", "PHYS206",
            "MATH151",
            "GENET380"
        ],
        "electives": {
            "count": 6,
            "min_level_300_plus": 4,
            "options": [
                "CBN245", "CBN270", "CBN322", "CBN328", "CBN340", "CBN356",
                "GENET302", "GENET352", "GENET354", "GENET356", "GENET370",
                "MCB301", "MCB407", "MCB408", "MCB411", "MCB413", "MCB420",
                "BIO307", "BIO308"
            ],
            "any_from_catalog": False
        }
    },

    "biomathematics_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Biomathematics",
        "catalog_year": "2025-2026",
        "required_courses": [
            "BIO101", "BIO102",
            "CHEM161", "CHEM162", "CHEM171",
            "MATH151", "MATH152", "MATH251", "MATH250", "MATH252",
            "MATH336", "MATH338", "MATH477", "MATH481"
        ],
        "electives": {
            "count": 1,
            "min_level_300_plus": 1,
            "options": [
                "MATH350", "MATH373", "MATH423", "MATH461",
                "MATH477", "MATH481"
            ],
            "any_from_catalog": False
        }
    },

    "mathematics_actuarial_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Mathematics (Actuarial)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "MATH151", "MATH152", "MATH251", "MATH250", "MATH252",
            "MATH285",
            "MATH477", "MATH481",
            "STAT381", "STAT382",
            "ECON102", "ECON103"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "MATH311", "MATH312", "MATH351", "MATH352",
                "STAT384", "STAT463", "STAT476", "STAT486",
                "ECON320", "ECON321", "ECON322"
            ],
            "any_from_catalog": False
        }
    },

    "statistics_mathematics_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Statistics/Mathematics",
        "catalog_year": "2025-2026",
        "required_courses": [
            "MATH151", "MATH152", "MATH251", "MATH250",
            "MATH300",
            "STAT381", "STAT382", "STAT384"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "MATH311", "MATH312", "MATH351", "MATH352",
                "MATH373", "MATH423", "MATH461",
                "STAT463", "STAT467", "STAT476", "STAT486", "STAT490"
            ],
            "any_from_catalog": False
        }
    },

    "data_science_cs_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Data Science (Computer Science Track)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CS142", "STAT291", "CS210",
            "MATH151", "MATH152", "MATH251", "MATH250",
            "ITI321",
            "CS111", "CS112", "CS205", "CS206",
            "CS336",
            "CS439",
            "STAT463", "STAT486"
        ],
        "electives": {
            "count": 1,
            "min_level_300_plus": 1,
            "options": ["CS461", "CS462"],
            "any_from_catalog": False
        }
    },

    "data_science_statistics_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Data Science (Statistics Track)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CS142", "STAT291", "STAT295",
            "MATH151", "MATH152", "MATH250",
            "CS111", "CS112",
            "STAT463", "STAT486"
        ],
        "electives": {
            "count": 1,
            "min_level_300_plus": 1,
            "options": ["STAT365", "STAT467", "STAT490"],
            "any_from_catalog": False
        }
    },

    "data_science_economics_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Data Science (Economics Track)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CS142", "STAT291", "CS210",
            "MATH151", "MATH152", "MATH250",
            "ITI321",
            "ECON102", "ECON103",
            "ECON320", "ECON321", "ECON322",
            "ECON421"
        ],
        "electives": {
            "count": 1,
            "min_level_300_plus": 1,
            "options": ["ECON422", "ECON424"],
            "any_from_catalog": False
        }
    },

    "data_science_societal_impact_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Data Science (Societal Impact Track)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CS142", "STAT291", "STAT295",
            "MATH151", "MATH250",
            "ITI103", "ITI201", "ITI321",
            "STAT463", "STAT486"
        ],
        "electives": {
            "count": 1,
            "min_level_300_plus": 1,
            "options": ["STAT365", "STAT467", "STAT490"],
            "any_from_catalog": False
        }
    },

    "data_science_chemical_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Data Science (Chemical Data Science Track)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CS142", "STAT291", "CS210",
            "MATH151", "MATH152", "MATH250",
            "CS111",
            "CHEM161", "CHEM162", "CHEM171", "CHEM172",
            "CHEM307", "CHEM308",
            "STAT463"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "CHEM251", "CHEM309", "CHEM311", "CHEM328", "CHEM341",
                "CHEM348", "CHEM351"
            ],
            "any_from_catalog": False
        }
    },

    "anthropology_evolutionary_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Anthropology (Evolutionary)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "ANTH102",
            "ANTH310", "ANTH325", "ANTH328",
            "ANTH336", "ANTH338", "ANTH350",
            "BIO101", "BIO102",
            "STAT211"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "ANTH302", "ANTH303", "ANTH304", "ANTH305",
                "ANTH307", "ANTH308", "ANTH309",
                "ANTH312", "ANTH314", "ANTH317", "ANTH318",
                "ANTH320", "ANTH326", "ANTH341"
            ],
            "any_from_catalog": False
        }
    },

    "physics_applied_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Physics (Applied Option)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "PHYS203", "PHYS205", "PHYS204", "PHYS206",
            "PHYS227", "PHYS228",
            "PHYS323", "PHYS324",
            "PHYS345", "PHYS341", "PHYS342", "PHYS351", "PHYS361",
            "PHYS382", "PHYS385", "PHYS388",
            "MATH151", "MATH152", "MATH251",
            "CS111"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "PHYS406", "PHYS417", "PHYS421",
                "PHYS441", "PHYS442", "PHYS443", "PHYS444"
            ],
            "any_from_catalog": False
        }
    },

    "physics_planetary_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Physics (Planetary Physics Option)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "PHYS203", "PHYS205", "PHYS204", "PHYS206",
            "PHYS227", "PHYS228",
            "PHYS323", "PHYS324",
            "PHYS345", "PHYS346", "PHYS342", "PHYS351",
            "PHYS382", "PHYS385",
            "MATH151", "MATH152", "MATH251",
            "GEOSC442"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "PHYS406", "PHYS417", "PHYS441", "PHYS442",
                "PHYS443", "PHYS444",
                "GEOSC224", "GEOSC303", "GEOSC441", "GEOSC480"
            ],
            "any_from_catalog": False
        }
    },

    "earth_planetary_sciences_general_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Earth and Planetary Sciences (General Option)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "GEOSC101",
            "CHEM161",
            "MATH151",
            "GEOSC300", "GEOSC301", "GEOSC302", "GEOSC303",
            "GEOSC407", "GEOSC411"
        ],
        "electives": {
            "count": 2,
            "min_level_300_plus": 1,
            "options": [
                "GEOSC201", "GEOSC202", "GEOSC212", "GEOSC224",
                "GEOSC225", "GEOSC304", "GEOSC306", "GEOSC410",
                "GEOSC414", "GEOSC442", "GEOSC480"
            ],
            "any_from_catalog": False
        }
    },

    "earth_planetary_sciences_environmental_geology_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Earth and Planetary Sciences (Environmental Geology)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CHEM161",
            "MATH151", "MATH152",
            "PHYS203",
            "GEOSC101", "GEOSC202",
            "GEOSC300", "GEOSC301", "GEOSC302",
            "GEOSC306",
            "GEOSC407", "GEOSC410",
            "GEOSC413", "GEOSC428"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "GEOSC303", "GEOSC304", "GEOSC414",
                "GEOSC442", "GEOSC480"
            ],
            "any_from_catalog": False
        }
    },

    "earth_planetary_sciences_planetary_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Earth and Planetary Sciences (Planetary Science)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CHEM161", "CHEM162",
            "MATH151", "MATH152", "MATH251",
            "PHYS203", "PHYS205", "PHYS204", "PHYS206",
            "GEOSC101", "GEOSC222",
            "GEOSC301", "GEOSC302", "GEOSC304",
            "GEOSC442", "GEOSC480"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "GEOSC224", "GEOSC225", "GEOSC303",
                "GEOSC306", "GEOSC413", "GEOSC441"
            ],
            "any_from_catalog": False
        }
    },

    "exercise_science_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Exercise Science",
        "catalog_year": "2025-2026",
        "required_courses": [
            "EXSC140", "EXSC200",
            "BIO101", "BIO102",
            "EXSC225", "EXSC226", "EXSC227",
            "EXSC301", "EXSC302", "EXSC303", "EXSC304", "EXSC305",
            "STAT211",
            "PSYC101"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "EXSC400", "EXSC401",
                "CBN245", "CBN270",
                "PSYC301", "PSYC302"
            ],
            "any_from_catalog": False
        }
    },

    "sport_management_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Sport Management",
        "catalog_year": "2025-2026",
        "required_courses": [
            "SPMD101", "SPMD201", "SPMD202", "SPMD203",
            "SPMD301", "SPMD302", "SPMD401",
            "EXSC140",
            "STAT211",
            "PSYC101"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "SPMD490",
                "ECON102", "ECON103",
                "SOC101", "SOC311"
            ],
            "any_from_catalog": False
        }
    },

    "public_health_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Public Health",
        "catalog_year": "2025-2026",
        "required_courses": [
            "PUBH201", "PUBH212", "PUBH240",
            "PUBH335", "PUBH356",
            "PUBH395",
            "PUBH450", "PUBH499",
            "STAT211",
            "CHEM161"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 3,
            "options": [
                "SOC101", "SOC201", "PSYC101",
                "ECON102", "POLS101"
            ],
            "any_from_catalog": False
        }
    },

    "public_policy_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Public Policy",
        "catalog_year": "2025-2026",
        "required_courses": [
            "PUBP201", "PUBP301", "PUBP302", "PUBP303",
            "PUBP401", "PUBP402",
            "ECON102", "ECON103",
            "STAT211",
            "POLS101"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "ECON320", "ECON321", "ECON322",
                "POLS301", "POLS302",
                "SOC201", "SOC311"
            ],
            "any_from_catalog": False
        }
    },

    "health_administration_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Health Administration",
        "catalog_year": "2025-2026",
        "required_courses": [
            "HLAD201", "HLAD202",
            "HLAD301", "HLAD302", "HLAD303",
            "HLAD401",
            "PUBH201",
            "STAT211",
            "ECON102"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "PUBH212", "PUBH240", "PUBH356",
                "SOC201", "PSYC101"
            ],
            "any_from_catalog": False
        }
    },

    # ===================== CHEMISTRY BA OPTIONS =====================
    "chemistry_core_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Chemistry (Core Option)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CHEM161", "CHEM162", "CHEM171", "CHEM172",
            "CHEM307", "CHEM308", "CHEM309", "CHEM311",
            "CHEM341",
            "MATH151", "MATH152",
            "PHYS203", "PHYS205", "PHYS204", "PHYS206"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 3,
            "options": [
                "CHEM251", "CHEM328", "CHEM329", "CHEM348",
                "CHEM351", "CHEM496"
            ],
            "any_from_catalog": False
        }
    },

    "chemistry_chemical_biology_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Chemistry (Chemical Biology Option)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CHEM161", "CHEM162", "CHEM171", "CHEM172",
            "CHEM307", "CHEM308", "CHEM309", "CHEM311",
            "CHEM341",
            "BIO101", "BIO102",
            "MATH151", "MATH152",
            "PHYS203", "PHYS205"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "CBN245", "MCB301", "MCB407", "MCB408",
                "GENET380", "CHEM348", "CHEM351"
            ],
            "any_from_catalog": False
        }
    },

    "chemistry_environmental_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Chemistry (Environmental Option)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CHEM161", "CHEM162", "CHEM171", "CHEM172",
            "CHEM307", "CHEM308", "CHEM309", "CHEM311",
            "CHEM341",
            "MATH151", "MATH152",
            "PHYS203", "PHYS205",
            "GEOSC101"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "CHEM251", "CHEM348", "CHEM351",
                "GEOSC202", "GEOSC304", "GEOSC413"
            ],
            "any_from_catalog": False
        }
    },

    "chemistry_forensic_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Chemistry (Forensic Chemistry Option)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CHEM161", "CHEM162", "CHEM171", "CHEM172",
            "CHEM307", "CHEM308", "CHEM309", "CHEM311",
            "CHEM251", "CHEM341", "CHEM348",
            "MATH151", "MATH152",
            "PHYS203", "PHYS205"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "CRIM201", "CRIM202", "CRIM301",
                "MCB301", "CBN245", "CHEM351"
            ],
            "any_from_catalog": False
        }
    },

    "chemistry_business_law_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Chemistry (Business/Law Option)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CHEM161", "CHEM162", "CHEM171", "CHEM172",
            "CHEM307", "CHEM308", "CHEM309", "CHEM311",
            "CHEM341",
            "MATH151",
            "ECON102", "ECON103"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "CHEM251", "CHEM348", "CHEM351",
                "ECON320", "ECON390", "ECON395"
            ],
            "any_from_catalog": False
        }
    },

    # ===================== LANGUAGE PROGRAMS =====================
    "french_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "French",
        "catalog_year": "2025-2026",
        "required_courses": [
            "FREN101", "FREN102", "FREN131",
            "FREN213", "FREN214",
            "FREN215", "FREN216",
            "FREN480"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 5,
            "options": [
                "FREN301", "FREN302", "FREN303",
                "FREN401", "FREN402"
            ],
            "any_from_catalog": False
        }
    },

    "german_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "German",
        "catalog_year": "2025-2026",
        "required_courses": [
            "GERM101", "GERM102",
            "GERM201", "GERM202", "GERM232"
        ],
        "electives": {
            "count": 7,
            "min_level_300_plus": 5,
            "options": [
                "GERM301", "GERM302", "GERM303",
                "GERM401", "GERM402"
            ],
            "any_from_catalog": False
        }
    },

    "italian_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Italian",
        "catalog_year": "2025-2026",
        "required_courses": [
            "ITAL101", "ITAL102", "ITAL131", "ITAL201", "ITAL202",
            "ITAL321"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 3,
            "options": [
                "ITAL231", "ITAL232",
                "ITAL301", "ITAL302",
                "ITAL401"
            ],
            "any_from_catalog": False
        }
    },

    "japanese_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Japanese",
        "catalog_year": "2025-2026",
        "required_courses": [
            "JPN101", "JPN102", "JPN201", "JPN202",
            "JPN301", "JPN302"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 4,
            "options": [
                "JPN401", "JPN402"
            ],
            "any_from_catalog": False
        }
    },

    "chinese_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Chinese",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CHN101", "CHN102", "CHN201", "CHN202",
            "CHN301", "CHN302"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 4,
            "options": [
                "CHN401", "CHN402"
            ],
            "any_from_catalog": False
        }
    },

    "korean_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Korean",
        "catalog_year": "2025-2026",
        "required_courses": [
            "KOR101", "KOR102", "KOR201", "KOR202",
            "KOR301", "KOR302"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 4,
            "options": [
                "KOR401"
            ],
            "any_from_catalog": False
        }
    },

    "russian_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Russian",
        "catalog_year": "2025-2026",
        "required_courses": [
            "RUSS101", "RUSS102",
            "RUSS201", "RUSS202",
            "RUSS301", "RUSS302"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 4,
            "options": [
                "RUSS401", "RUSS402"
            ],
            "any_from_catalog": False
        }
    },

    "portuguese_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Portuguese",
        "catalog_year": "2025-2026",
        "required_courses": [
            "PORT101", "PORT102",
            "PORT201", "PORT202",
            "PORT301", "PORT302"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 4,
            "options": [
                "PORT401", "PORT402"
            ],
            "any_from_catalog": False
        }
    },

    "spanish_intensive_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Spanish (Spanish Intensive)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "SPAN101", "SPAN102", "SPAN201", "SPAN202",
            "SPAN301", "SPAN302", "SPAN303",
            "SPAN320"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 5,
            "options": [
                "SPAN304", "SPAN305", "SPAN306",
                "SPAN310", "SPAN311", "SPAN330",
                "SPAN340", "SPAN350",
                "SPAN401", "SPAN410", "SPAN420"
            ],
            "any_from_catalog": False
        }
    },

    # ===================== HUMANITIES =====================
    "art_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Art",
        "catalog_year": "2025-2026",
        "required_courses": [
            "ART101", "ART102", "ART103",
            "ART201", "ART401", "ART402",
            "ARTH106"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 3,
            "options": [
                "ART202", "ART203", "ART204", "ART205",
                "ART301", "ART302", "ART303"
            ],
            "any_from_catalog": False
        }
    },

    "music_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Music",
        "catalog_year": "2025-2026",
        "required_courses": [
            "MUS101", "MUS102", "MUS207", "MUS208",
            "MUS202", "MUS203", "MUS204",
            "MUS400"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "MUS301", "MUS302", "MUS303"
            ],
            "any_from_catalog": False
        }
    },

    "theater_arts_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Theater Arts",
        "catalog_year": "2025-2026",
        "required_courses": [
            "THEA101", "THEA102", "THEA103",
            "THEA200", "THEA201", "THEA204",
            "THEA301", "THEA400"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "THEA202", "THEA203",
                "THEA302", "THEA303"
            ],
            "any_from_catalog": False
        }
    },

    "dance_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Dance",
        "catalog_year": "2025-2026",
        "required_courses": [
            "DANC101", "DANC102",
            "DANC200",
            "DANC201", "DANC202", "DANC203",
            "DANC301", "DANC400"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "DANC302", "DANC303"
            ],
            "any_from_catalog": False
        }
    },

    "cinema_studies_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Cinema Studies",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CINE201", "CINE202", "CINE203",
            "CINE301", "CINE402"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 4,
            "options": [
                "CINE302", "CINE303", "CINE401"
            ],
            "any_from_catalog": False
        }
    },

    "journalism_media_studies_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Journalism and Media Studies",
        "catalog_year": "2025-2026",
        "required_courses": [
            "JOUR101", "JOUR201", "JOUR202", "JOUR203",
            "JOUR401", "JOUR402"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "JOUR301", "JOUR302", "JOUR303"
            ],
            "any_from_catalog": False
        }
    },

    "religion_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Religion",
        "catalog_year": "2025-2026",
        "required_courses": [
            "RELGS101", "RELGS200", "RELGS201"
        ],
        "electives": {
            "count": 7,
            "min_level_300_plus": 4,
            "options": [
                "RELGS301", "RELGS302", "RELGS303",
                "RELGS401"
            ],
            "any_from_catalog": False
        }
    },

    "classics_classical_humanities_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Classics (Classical Humanities)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "CLASS101", "CLASS102", "CLASS103",
            "CLASS201", "CLASS202"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 4,
            "options": [
                "CLASS301", "CLASS302", "CLASS401",
                "HIST301", "HIST310",
                "PHIL201", "PHIL210"
            ],
            "any_from_catalog": False
        }
    },

    "classics_greek_latin_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Classics (Greek and Latin)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "GREK101", "GREK102", "GREK201", "GREK301",
            "LAT101", "LAT102", "LAT201", "LAT301",
            "CLASS201"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 3,
            "options": [
                "CLASS301", "CLASS302", "CLASS401"
            ],
            "any_from_catalog": False
        }
    },

    "comparative_literature_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Comparative Literature",
        "catalog_year": "2025-2026",
        "required_courses": [
            "COMPLIT201", "COMPLIT202",
            "COMPLIT301", "COMPLIT302",
            "COMPLIT402"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 4,
            "options": [
                "COMPLIT401",
                "ENGL201", "ENGL202", "ENGL203",
                "FREN215", "FREN216",
                "SPAN302", "SPAN303"
            ],
            "any_from_catalog": False
        }
    },

    "medieval_studies_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Medieval Studies",
        "catalog_year": "2025-2026",
        "required_courses": [
            "MEDST201", "MEDST202", "MEDST203"
        ],
        "electives": {
            "count": 7,
            "min_level_300_plus": 4,
            "options": [
                "MEDST301", "MEDST401",
                "HIST301", "HIST310",
                "ENGL201", "ENGL202",
                "CLASS301", "CLASS302",
                "RELGS301"
            ],
            "any_from_catalog": False
        }
    },

    "global_humanities_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Global Humanities",
        "catalog_year": "2025-2026",
        "required_courses": [
            "GLHUM101", "GLHUM201", "GLHUM301", "GLHUM401"
        ],
        "electives": {
            "count": 6,
            "min_level_300_plus": 4,
            "options": [
                "ENGL201", "ENGL202",
                "HIST201", "HIST202",
                "PHIL201", "PHIL210",
                "COMPLIT201", "COMPLIT202",
                "RELGS200", "RELGS201"
            ],
            "any_from_catalog": False
        }
    },

    "jewish_studies_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Jewish Studies",
        "catalog_year": "2025-2026",
        "required_courses": [
            "JWST101", "JWST201", "JWST202"
        ],
        "electives": {
            "count": 7,
            "min_level_300_plus": 4,
            "options": [
                "JWST301", "JWST302", "JWST401",
                "HIST301", "HIST310",
                "RELGS301", "RELGS302"
            ],
            "any_from_catalog": False
        }
    },

    "asian_studies_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Asian Studies",
        "catalog_year": "2025-2026",
        "required_courses": [
            "AMES101", "AMES201", "AMES202"
        ],
        "electives": {
            "count": 7,
            "min_level_300_plus": 4,
            "options": [
                "AMES301", "AMES401",
                "JPN101", "CHN101", "KOR101",
                "HIST201", "HIST202",
                "RELGS200"
            ],
            "any_from_catalog": False
        }
    },

    "latin_american_studies_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Latin American Studies",
        "catalog_year": "2025-2026",
        "required_courses": [
            "LAS101", "LAS201", "LAS202"
        ],
        "electives": {
            "count": 7,
            "min_level_300_plus": 4,
            "options": [
                "LAS301", "LAS401",
                "SPAN302", "SPAN303", "SPAN310", "SPAN311", "SPAN330",
                "PORT301", "PORT302",
                "HIST201", "HIST202",
                "SOC201", "POLS201"
            ],
            "any_from_catalog": False
        }
    },

    "latino_caribbean_studies_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Latino and Caribbean Studies",
        "catalog_year": "2025-2026",
        "required_courses": [
            "LCS101", "LCS201", "LCS202"
        ],
        "electives": {
            "count": 7,
            "min_level_300_plus": 4,
            "options": [
                "LCS301", "LCS401",
                "SPAN302", "SPAN303", "SPAN330", "SPAN340",
                "HIST201", "HIST202",
                "SOC201"
            ],
            "any_from_catalog": False
        }
    },

    "european_studies_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "European Studies",
        "catalog_year": "2025-2026",
        "required_courses": [
            "EURO101", "EURO201", "EURO202"
        ],
        "electives": {
            "count": 7,
            "min_level_300_plus": 4,
            "options": [
                "EURO301", "EURO401",
                "HIST201", "HIST202",
                "FREN215", "FREN216",
                "GERM301", "GERM302",
                "ITAL301", "ITAL302",
                "POLS201", "POLS301"
            ],
            "any_from_catalog": False
        }
    },

    "middle_eastern_studies_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Middle Eastern Studies",
        "catalog_year": "2025-2026",
        "required_courses": [
            "MES101", "MES201", "MES202"
        ],
        "electives": {
            "count": 7,
            "min_level_300_plus": 4,
            "options": [
                "MES301", "MES401",
                "RELGS200", "RELGS201", "RELGS301",
                "HIST201", "HIST202",
                "POLS201"
            ],
            "any_from_catalog": False
        }
    },

    "amesall_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "African, Middle Eastern and South Asian Languages and Literatures",
        "catalog_year": "2025-2026",
        "required_courses": [
            "AMESALL101", "AMESALL201", "AMESALL202",
            "AMESALL301", "AMESALL401"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 4,
            "options": [
                "MES201", "MES202", "MES301",
                "RELGS200", "RELGS201",
                "HIST201", "HIST202"
            ],
            "any_from_catalog": False
        }
    },

    # ===================== SOCIAL SCIENCES =====================
    "information_technology_informatics_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Information Technology and Informatics",
        "catalog_year": "2025-2026",
        "required_courses": [
            "ITI103", "ITI201",
            "ITI301", "ITI302", "ITI321",
            "ITI401",
            "CS111",
            "STAT211"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "CS112", "CS205", "CS210",
                "CS336", "CS344",
                "STAT291"
            ],
            "any_from_catalog": False
        }
    },

    "human_resource_management_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Human Resource Management",
        "catalog_year": "2025-2026",
        "required_courses": [
            "HRM201", "HRM202",
            "HRM301", "HRM302", "HRM303",
            "HRM401",
            "ECON102",
            "STAT211"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "LER101", "LER201", "LER301",
                "SOC201", "SOC311",
                "PSYC301"
            ],
            "any_from_catalog": False
        }
    },

    "labor_studies_employment_relations_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Labor Studies and Employment Relations",
        "catalog_year": "2025-2026",
        "required_courses": [
            "LER101", "LER102",
            "LER201", "LER202",
            "LER301", "LER302",
            "LER401"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "LER490",
                "ECON102", "ECON103",
                "SOC201", "SOC311",
                "POLS201", "POLS301"
            ],
            "any_from_catalog": False
        }
    },

    "social_work_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Social Work",
        "catalog_year": "2025-2026",
        "required_courses": [
            "SOCW101", "SOCW201", "SOCW202",
            "SOCW301", "SOCW302",
            "SOCW401",
            "PSYC101",
            "STAT211"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "SOC201", "SOC311",
                "PSYC301", "PSYC302",
                "ECON102"
            ],
            "any_from_catalog": False
        }
    },

    "urban_planning_design_bs": {
        "school": "SAS",
        "degree_level": "bachelor_bs",
        "major_name": "Urban Planning and Design",
        "catalog_year": "2025-2026",
        "required_courses": [
            "UPD101", "UPD201", "UPD202",
            "UPD301", "UPD302", "UPD303",
            "UPD401", "UPD402",
            "STAT211",
            "ECON102"
        ],
        "electives": {
            "count": 3,
            "min_level_300_plus": 2,
            "options": [
                "GEOG301", "GEOG302", "GEOG303",
                "ENVST301",
                "SOC311"
            ],
            "any_from_catalog": False
        }
    },

    "city_regional_planning_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "City and Regional Planning",
        "catalog_year": "2025-2026",
        "required_courses": [
            "UPD101", "UPD201", "UPD202",
            "UPD301", "UPD302",
            "UPD401",
            "STAT211"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "GEOG301", "GEOG302", "GEOG303",
                "ENVST301",
                "ECON320", "POLS301"
            ],
            "any_from_catalog": False
        }
    },

    # ===================== COMMUNICATION TRACKS =====================
    "communication_technology_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Communication (Communication and Technology)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "COMMUN101", "COMMUN200", "COMMUN201",
            "COMMUN359", "COMMUN402",
            "COMMUN380"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "COMMUN300", "COMMUN354", "COMMUN355",
                "COMMUN356", "COMMUN357",
                "COMMUN400", "COMMUN401", "COMMUN403", "COMMUN404"
            ],
            "any_from_catalog": False
        }
    },

    "communication_health_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Communication (Health and Wellness)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "COMMUN101", "COMMUN200", "COMMUN201",
            "COMMUN354", "COMMUN403",
            "COMMUN380"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "COMMUN300", "COMMUN355", "COMMUN356",
                "COMMUN357", "COMMUN359",
                "COMMUN400", "COMMUN401", "COMMUN402", "COMMUN404"
            ],
            "any_from_catalog": False
        }
    },

    "communication_leadership_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Communication (Leadership in Organizations and Community)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "COMMUN101", "COMMUN200", "COMMUN201",
            "COMMUN355", "COMMUN404",
            "COMMUN380"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "COMMUN300", "COMMUN354", "COMMUN356",
                "COMMUN357", "COMMUN359",
                "COMMUN400", "COMMUN401", "COMMUN402", "COMMUN403"
            ],
            "any_from_catalog": False
        }
    },

    "communication_relationships_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Communication (Relationships and Family)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "COMMUN101", "COMMUN200", "COMMUN201",
            "COMMUN356", "COMMUN357",
            "COMMUN380"
        ],
        "electives": {
            "count": 4,
            "min_level_300_plus": 3,
            "options": [
                "COMMUN300", "COMMUN354", "COMMUN355",
                "COMMUN359",
                "COMMUN400", "COMMUN401", "COMMUN402", "COMMUN403", "COMMUN404"
            ],
            "any_from_catalog": False
        }
    },

    "communication_strategic_ba": {
        "school": "SAS",
        "degree_level": "bachelor_ba",
        "major_name": "Communication (Strategic Public Communication)",
        "catalog_year": "2025-2026",
        "required_courses": [
            "COMMUN101", "COMMUN200", "COMMUN201",
            "COMMUN401",
            "COMMUN380"
        ],
        "electives": {
            "count": 5,
            "min_level_300_plus": 4,
            "options": [
                "COMMUN300", "COMMUN354", "COMMUN355",
                "COMMUN356", "COMMUN357", "COMMUN359",
                "COMMUN400", "COMMUN402", "COMMUN403", "COMMUN404"
            ],
            "any_from_catalog": False
        }
    },
}


def main():
    # Load catalog
    with open(CATALOG_PATH) as f:
        catalog = json.load(f)
    existing_codes = {e["code"] for e in catalog}

    # Add new catalog entries (skip if already exists)
    added_catalog = 0
    for entry in NEW_CATALOG_ENTRIES:
        if entry["code"] not in existing_codes:
            catalog.append(entry)
            existing_codes.add(entry["code"])
            added_catalog += 1
        else:
            print(f"  Catalog: {entry['code']} already exists, skipping")

    # Write catalog
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)
    print(f"Catalog: added {added_catalog} new entries. Total: {len(catalog)}")

    # Load programs
    with open(PROGRAMS_PATH) as f:
        programs_data = json.load(f)
    programs = programs_data["programs"]

    # Add new programs (skip if already exists)
    added_programs = 0
    for key, prog in NEW_PROGRAMS.items():
        if key not in programs:
            programs[key] = prog
            added_programs += 1
        else:
            print(f"  Program: {key} already exists, skipping")

    # Write programs
    with open(PROGRAMS_PATH, "w") as f:
        json.dump(programs_data, f, indent=2)
    print(f"Programs: added {added_programs} new entries. Total: {len(programs)}")


if __name__ == "__main__":
    main()
