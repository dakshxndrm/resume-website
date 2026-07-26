"""25 hand-written (resume, job, expected_min, expected_max) cases.

Needs no downloads — run this first.

The intervals are written from what a trustworthy ATS scorer *should* output for
each situation, decided before the scorer was run and left alone afterwards. They
are not fitted to the current implementation. A FAIL here is a finding about the
scorer, not a bug in the case; the failure analysis at the bottom prints the
category breakdown so each one can be traced to the responsible component.

Three cases are mandated by the benchmark spec:
  #3  unrelated-industry resume must score under 30
  #4  the job description pasted 20 times must not exceed 50
  #1  a near-perfect match must clear 70

Usage:
  cd eval/external && ../../backend/.venv/Scripts/python stress_intervals.py
  SBERT_DISABLED=1 ... to measure the lexical-only path
"""
from __future__ import annotations

from dataclasses import dataclass

from _harness import categories_of, sbert_mode, score_text

# --------------------------------------------------------------------------
# job descriptions
# --------------------------------------------------------------------------
JD_BACKEND = """Senior Backend Engineer — Python
We are hiring a backend engineer to design and ship REST APIs in Python using
FastAPI and Django. You will own PostgreSQL schema design, Redis caching, and
Docker-based deployments to AWS. Experience with Kubernetes, CI/CD pipelines and
writing unit tests is required. You will mentor junior engineers and review pull
requests. 5+ years of backend experience expected."""

JD_FRONTEND = """Frontend Engineer — React
Build accessible, fast user interfaces with React, TypeScript and Next.js.
You will work with Tailwind CSS, write tests in Jest, and optimise bundle size
with Webpack and Vite. Strong CSS and HTML fundamentals required. You will
partner with designers on a component library and care deeply about
accessibility. 3+ years of frontend experience."""

JD_DATA = """Data Scientist
Build predictive models with Python, Pandas, NumPy and scikit-learn. Experience
with PyTorch or TensorFlow for deep learning is required, along with SQL for
data extraction and statistics for experiment design. You will do NLP work on
customer text and present findings with data visualization. Machine learning in
production is a plus."""

JD_NURSE = """Registered Nurse — Medical Surgical Unit
Provide direct patient care on a 32-bed medical surgical unit. Administer
medications, monitor vital signs, and document in the electronic health record.
BSN and active RN licence required. Two years of acute care experience
preferred. Strong communication and teamwork skills essential. BLS and ACLS
certification required."""


# --------------------------------------------------------------------------
# resumes
# --------------------------------------------------------------------------
R_BACKEND_SENIOR = """PRIYA SHARMA
Senior Backend Engineer | priya@example.com | Bangalore, India

SUMMARY
Backend engineer with 7 years building REST APIs in Python. Owns PostgreSQL
schema design and Docker deployments to AWS.

EXPERIENCE
Senior Backend Engineer, Fintech Corp — 2021 - Present
Designed REST APIs in Python with FastAPI serving 40M requests per day.
Led PostgreSQL schema redesign that cut p95 latency 45%.
Built Redis caching layer and moved deployments to Docker on AWS.
Ran the CI/CD pipeline and mentored four junior engineers.
Reviewed pull requests and raised unit test coverage from 40% to 85%.

Backend Engineer, LogiSoft — 2018 - 2021
Built Django services backed by PostgreSQL and Redis.
Introduced Kubernetes for container orchestration across 12 services.

EDUCATION
B.Tech in Computer Science, PES University — 2014 - 2018

SKILLS
Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes, AWS, CI/CD,
Git, Linux, SQL, REST APIs, Microservices"""

R_FRONTEND_MID = """ALEX CHEN
Frontend Engineer | alex@example.com | Remote

SUMMARY
Frontend engineer with 4 years building accessible interfaces in React and
TypeScript.

EXPERIENCE
Frontend Engineer, ShopStack — 2021 - Present
Built the customer dashboard in React, TypeScript and Next.js.
Cut bundle size 38% by migrating Webpack to Vite.
Wrote Jest tests covering the component library.
Drove accessibility work to WCAG AA across 40 screens.

Junior Frontend Developer, Webly — 2019 - 2021
Built responsive marketing pages with HTML, CSS and Tailwind CSS.
Maintained shared Redux state for the checkout flow.

EDUCATION
B.Sc in Information Technology, Manipal University — 2015 - 2019

SKILLS
React, TypeScript, Next.js, Tailwind CSS, Jest, Webpack, Vite, HTML, CSS,
JavaScript, Redux, Accessibility, Git"""

R_BARISTA = """SAM RIVERA
Barista and Shift Supervisor | sam@example.com | Portland, OR

SUMMARY
Hospitality professional with six years in specialty coffee. Known for
consistent espresso quality and calm service during peak hours.

EXPERIENCE
Shift Supervisor, Bean & Bloom — 2021 - Present
Supervised a team of eight baristas across opening and closing shifts.
Cut milk waste 22% by retraining staff on steaming technique.
Handled cash reconciliation and daily inventory ordering.
Resolved customer complaints and maintained a 4.8 star store rating.

Barista, Roast House — 2018 - 2021
Pulled 300+ espresso drinks per shift and trained four new hires.
Managed pastry case rotation and health inspection readiness.

EDUCATION
High School Diploma, Lincoln High School — 2014 - 2018

SKILLS
Espresso, Latte Art, Customer Service, Inventory, Cash Handling, Food Safety,
Scheduling, Barista Training"""

R_JUNIOR_PROJECTS = """DEV PATEL
Computer Science Student | dev@example.com | Pune, India

SUMMARY
Final-year CS student looking for a backend role. No industry experience yet;
everything below is self-built.

PROJECTS
Expense Tracker API — a REST API in Python with FastAPI and PostgreSQL.
Added Redis caching and Docker packaging. Deployed to AWS free tier.

Chat Application — real-time messaging with WebSockets, Python and SQLite.
Wrote unit tests and set up a CI/CD pipeline with GitHub Actions.

Portfolio Site — built with React and Tailwind CSS.

EDUCATION
B.Tech in Computer Science, VIT Pune — 2021 - 2025

SKILLS
Python, FastAPI, PostgreSQL, Redis, Docker, SQL, Git, Linux, React"""

R_TEACHER_TO_DATA = """MARIA GOMEZ
High School Teacher moving into Data Science | maria@example.com

SUMMARY
Eight years teaching mathematics and statistics, now retraining in data
science. Completed a nine-month analytics bootcamp.

EXPERIENCE
Mathematics Teacher, Riverside High — 2016 - 2024
Taught statistics and calculus to 140 students per year.
Built spreadsheets tracking student performance and ran data analysis on
outcomes to redesign the curriculum.
Presented findings to the district board using data visualization.

EDUCATION
M.Sc in Mathematics, State University — 2014 - 2016
B.Sc in Mathematics, State University — 2010 - 2014

SKILLS
Python, Pandas, SQL, Statistics, Data Analysis, Data Visualization,
Communication, Teamwork"""

R_PARAPHRASED = """JORDAN LEE
Software Engineer | jordan@example.com

SUMMARY
Engineer who builds server-side web services and the data stores behind them.

EXPERIENCE
Software Engineer, Northwind Systems — 2019 - Present
Designed and shipped web service endpoints that other teams consume over HTTP.
Modelled and tuned the relational database that backs the billing platform.
Packaged services into containers and ran them on a managed cloud cluster.
Set up the automated build-and-release chain so every merge ships safely.
Kept an in-memory key-value store in front of the hottest read paths.
Mentored two newer engineers and reviewed their merge requests daily.

EDUCATION
B.E in Computer Engineering, Anna University — 2015 - 2019

SKILLS
Server-side development, relational data modelling, containerisation,
release automation, code review, mentoring"""

R_SKILLS_ONLY = """RAHUL VERMA
rahul@example.com

SKILLS
Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes, AWS, CI/CD,
Git, Linux, SQL, REST APIs, Microservices, Bash, MongoDB, GraphQL, Flask"""

R_INTERN = """LI WEI
Software Engineering Intern | li@example.com

EXPERIENCE
Backend Intern, Startup Labs — Jun 2024 - Aug 2024
Fixed bugs in a Python FastAPI service and wrote unit tests.
Added two PostgreSQL migrations under supervision.

EDUCATION
B.Tech in Computer Science, IIT Hyderabad — 2022 - 2026

SKILLS
Python, FastAPI, PostgreSQL, Git"""

R_DATA_SCIENTIST = """AISHA KHAN
Data Scientist | aisha@example.com | Hyderabad, India

SUMMARY
Data scientist with 5 years building predictive models in production.

EXPERIENCE
Data Scientist, RetailIQ — 2020 - Present
Built demand forecasting models with Python, Pandas, NumPy and scikit-learn.
Shipped a PyTorch deep learning model for NLP on customer support text.
Ran A/B experiments using statistics to size effects before rollout.
Wrote SQL to extract features from a 4TB warehouse.
Presented results with data visualization to non-technical stakeholders.

EDUCATION
M.Sc in Statistics, University of Hyderabad — 2016 - 2018
B.Sc in Mathematics, Osmania University — 2013 - 2016

SKILLS
Python, Pandas, NumPy, scikit-learn, PyTorch, TensorFlow, SQL, Statistics,
NLP, Machine Learning, Deep Learning, Data Visualization, Data Analysis"""

R_NURSE = """DANIELLE OKAFOR
Registered Nurse | danielle@example.com | Chicago, IL

SUMMARY
Registered nurse with four years on a 32-bed medical surgical unit.

EXPERIENCE
Registered Nurse, Mercy General Hospital — 2020 - Present
Provided direct patient care for up to six acute care patients per shift.
Administered medications and monitored vital signs across 12-hour shifts.
Documented all care in the electronic health record within policy windows.
Precepted three new graduate nurses through unit orientation.

EDUCATION
BSN in Nursing, University of Illinois — 2016 - 2020

SKILLS
Patient Care, Medication Administration, Electronic Health Record, BLS, ACLS,
Communication, Teamwork, Acute Care"""

R_PHD_NO_WORK = """SOFIA ROSSI
PhD Candidate | sofia@example.com

EDUCATION
PhD in Computer Science, ETH Zurich — 2019 - 2024
Thesis on distributed systems consistency models.
M.Sc in Computer Science, ETH Zurich — 2017 - 2019
B.Sc in Computer Science, University of Bologna — 2014 - 2017

SKILLS
Python, Distributed Systems, Statistics, Linux, Git"""

R_PERFECT_SKILLS_NO_DATES = """OMAR HADDAD
Backend Engineer | omar@example.com

SUMMARY
Backend engineer building REST APIs in Python with FastAPI and Django, backed
by PostgreSQL and Redis, deployed with Docker and Kubernetes on AWS.

EXPERIENCE
Senior Backend Engineer, Payments Inc
Owned the payments API written in Python and FastAPI.
Designed the PostgreSQL schema and the Redis caching layer.
Ran CI/CD and Docker based deployments to AWS and Kubernetes.
Mentored junior engineers and reviewed pull requests.

EDUCATION
B.Tech in Computer Science, Cairo University

SKILLS
Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes, AWS, CI/CD,
Git, REST APIs, Unit Testing"""

R_CONTRACTOR = """NINA PETROVA
Contract Backend Engineer | nina@example.com

EXPERIENCE
Contract Backend Engineer, MedTech — 2023 - 2024
Built REST APIs in Python and FastAPI against PostgreSQL.

Contract Backend Engineer, FinServe — 2022 - 2023
Migrated a Django monolith to Docker on AWS with a CI/CD pipeline.

Contract Backend Engineer, RetailCo — 2021 - 2022
Added Redis caching and wrote unit tests for a Python service.

Contract Backend Engineer, LogiCorp — 2020 - 2021
Maintained Kubernetes manifests and PostgreSQL migrations.

EDUCATION
B.Sc in Software Engineering, Moscow State — 2015 - 2019

SKILLS
Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes, AWS, CI/CD, Git"""

R_ACRONYMS = """T. NGUYEN
Backend Engineer | tn@example.com

EXPERIENCE
Backend Engineer, ACME — 2019 - Present
Built REST APIs (Python, FastAPI) on PG and Redis, shipped via CI/CD to AWS
ECS/EKS. Owned SLOs, on-call, and IaC. Cut TTFB 30% and raised UT coverage.
Ran PR review for a team of six. Used K8s, Docker, and GHA daily.

EDUCATION
BS CS, HCMUT — 2015 - 2019

SKILLS
Python, FastAPI, PG, Redis, Docker, K8s, AWS, CI/CD, IaC, GHA, SQL, Git"""

R_OVERLONG = R_BACKEND_SENIOR + "\n\nADDITIONAL EXPERIENCE\n" + (
    "Delivered production Python services with FastAPI, PostgreSQL and Redis, "
    "deployed through Docker and CI/CD to AWS, with unit tests and code review. "
) * 60

R_VERY_SHORT = """KIM PARK
Backend Engineer | kim@example.com
Python, FastAPI and PostgreSQL developer. Built REST APIs at a startup
from 2021 - 2024. B.Tech in Computer Science."""

R_GIBBERISH = """asdkjh qwlekjq lkjqwe lkjqwlkej qlwkej qlwkej
zxcvbnm asdfghjkl qwertyuiop
!!!! ???? ####
lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod"""

R_NAME_ONLY = "John Smith"


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------
@dataclass
class Case:
    id: int
    name: str
    resume: str
    job: str | None
    lo: int
    hi: int
    why: str


CASES: list[Case] = [
    Case(1, "near-perfect backend match", R_BACKEND_SENIOR, JD_BACKEND, 70, 95,
         "SPEC: near-perfect match must exceed 70. Every required skill present, "
         "7 years relevant experience, degree, right seniority."),
    Case(2, "near-perfect frontend match", R_FRONTEND_MID, JD_FRONTEND, 70, 95,
         "Same situation in a different stack — a good scorer is not backend-specific."),
    Case(3, "unrelated industry (barista -> backend)", R_BARISTA, JD_BACKEND, 0, 30,
         "SPEC: unrelated-industry resume must score under 30. Zero transferable "
         "technical skills; an ATS that ranks this highly is worthless."),
    Case(4, "job description pasted 20 times", JD_BACKEND * 20, JD_BACKEND, 0, 50,
         "SPEC: keyword stuffing must not exceed 50. Contains no experience, no "
         "education, no evidence — only the posting's own words echoed back."),
    Case(5, "empty resume", "", JD_BACKEND, 0, 30,
         "Nothing to evaluate. Any score above 30 is invented."),
    Case(6, "name only", R_NAME_ONLY, JD_BACKEND, 0, 30,
         "Two words. Same reasoning as the empty case."),
    Case(7, "gibberish text", R_GIBBERISH, JD_BACKEND, 0, 30,
         "Unparseable noise must not earn credit."),
    Case(8, "strong junior, projects but no jobs", R_JUNIOR_PROJECTS, JD_BACKEND, 45, 70,
         "Right skills and real projects, but zero industry experience against a "
         "5+ years posting. Solidly mid, not top."),
    Case(9, "intern vs senior posting", R_INTERN, JD_BACKEND, 30, 55,
         "One summer internship against a 5+ year senior role. Under-qualified but "
         "not unqualified — should sit below the junior with a project portfolio."),
    Case(10, "career changer, partial overlap", R_TEACHER_TO_DATA, JD_DATA, 35, 60,
         "Genuine Python/statistics/data-analysis overlap, but no industry data "
         "science work. Mid-low, clearly under a real data scientist."),
    Case(11, "data scientist, on target", R_DATA_SCIENTIST, JD_DATA, 70, 95,
         "Every listed requirement met with 5 years of production experience."),
    Case(12, "data scientist vs frontend posting", R_DATA_SCIENTIST, JD_FRONTEND, 20, 45,
         "Strong resume, wrong job. Must score far below case 11 — this is the "
         "single clearest test that the JD actually influences the result."),
    Case(13, "frontend resume vs backend posting", R_FRONTEND_MID, JD_BACKEND, 30, 55,
         "Adjacent discipline: shares Git and general engineering, misses the whole "
         "backend stack. Should land between an unrelated industry and a real match."),
    Case(14, "paraphrased skills, no keyword overlap", R_PARAPHRASED, JD_BACKEND, 40, 65,
         "Describes the same work in different words ('container', 'relational "
         "database'). Lexical matching scores ~0; SBERT should rescue it partway. "
         "This case is the reason SBERT was added."),
    Case(15, "skills list only, no experience", R_SKILLS_ONLY, JD_BACKEND, 30, 55,
         "A keyword list with no evidence behind any of it. Should not beat "
         "candidates who actually did the work."),
    Case(16, "perfect skills, no dates anywhere", R_PERFECT_SKILLS_NO_DATES, JD_BACKEND, 45, 75,
         "Content-identical to a strong match but with no date ranges — a formatting "
         "quirk should cost a few points, not collapse the score."),
    Case(17, "contractor, many short stints", R_CONTRACTOR, JD_BACKEND, 55, 85,
         "Four relevant roles in four years. Fragmented but genuinely experienced."),
    Case(18, "acronym-heavy on-target resume", R_ACRONYMS, JD_BACKEND, 55, 85,
         "Uses PG/K8s/UT instead of PostgreSQL/Kubernetes/unit tests. Real resumes do "
         "this; an ATS that only reads expanded forms punishes the wrong thing."),
    Case(19, "overlong resume (1000+ words), on target", R_OVERLONG, JD_BACKEND, 65, 90,
         "Strong candidate, padded. Length should cost a little, not much."),
    Case(20, "very short resume, on target", R_VERY_SHORT, JD_BACKEND, 35, 60,
         "Right keywords but almost no substance. Thin resumes should read as thin."),
    Case(21, "PhD, no industry work", R_PHD_NO_WORK, JD_BACKEND, 35, 60,
         "Top-tier education, zero industry experience, few of the required tools."),
    Case(22, "nurse vs nursing posting", R_NURSE, JD_NURSE, 45, 75,
         "Non-tech match. The skill vocabulary is tech-heavy, so this measures how "
         "badly the scorer degrades outside software."),
    Case(23, "nurse vs backend posting", R_NURSE, JD_BACKEND, 0, 30,
         "Second unrelated-industry probe from a different domain, to show case 3 "
         "is not a one-off."),
    Case(24, "strong backend resume, no job description", R_BACKEND_SENIOR, None, 55, 85,
         "No JD: semantic returns its neutral 60 by design. Quality signals alone "
         "should still place a genuinely strong resume above average."),
    Case(25, "barista resume, no job description", R_BARISTA, None, 30, 60,
         "No JD, so this is pure quality scoring. A well-written resume for a "
         "different field should read as mediocre, not strong."),
]


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------
def main() -> int:
    print("=" * 78)
    print("STRESS INTERVALS — 25 hand-written cases".center(78))
    print("=" * 78)
    print(f"semantic path: {sbert_mode()}")
    print("pipeline:      text -> .docx -> parse_resume() -> score_resume()")
    print("intervals were written before running and have NOT been adjusted.\n")

    results = []
    for case in CASES:
        report = score_text(case.resume, case.job)
        total = report["total"]
        ok = case.lo <= total <= case.hi
        results.append((case, total, ok, categories_of(report)))

    print(f"{'#':>3} {'case':<44} {'want':>9} {'got':>5}  result")
    print("-" * 78)
    for case, total, ok, _ in results:
        print(f"{case.id:>3} {case.name[:44]:<44} {f'{case.lo}-{case.hi}':>9} "
              f"{total:>5}  {'PASS' if ok else 'FAIL'}")

    passed = sum(1 for _, _, ok, _ in results if ok)
    failed = [(c, t, cats) for c, t, ok, cats in results if not ok]

    print("-" * 78)
    print(f"{passed}/{len(results)} passed, {len(failed)} failed\n")

    spec_ids = {1: "near-perfect > 70", 3: "unrelated industry < 30", 4: "20x stuffing <= 50"}
    print("SPEC-MANDATED CASES")
    for case, total, ok, _ in results:
        if case.id in spec_ids:
            print(f"  case {case.id}: {spec_ids[case.id]:<26} got {total:>3}  "
                  f"{'PASS' if ok else 'FAIL'}")
    print()

    if failed:
        print("=" * 78)
        print("FAILURE ANALYSIS".center(78))
        print("=" * 78)
        for case, total, cats in failed:
            direction = "ABOVE" if total > case.hi else "BELOW"
            print(f"\ncase {case.id}: {case.name}")
            print(f"  expected {case.lo}-{case.hi}, got {total} ({direction} the interval)")
            print(f"  why the interval: {case.why}")
            print("  categories: " + "  ".join(f"{k}={v}" for k, v in cats.items()))

    scores = [t for _, t, _, _ in results]
    print("\n" + "=" * 78)
    print(f"score range across all 25 cases: {min(scores)} .. {max(scores)} "
          f"(spread {max(scores) - min(scores)})")
    print("=" * 78)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
