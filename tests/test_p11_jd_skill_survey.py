"""
P11 tests: tools/jd_skill_survey.py (offline, descriptive role-capability survey).

Every fixture here is synthetic and authored for these tests (fictional companies, LinkedIn-shaped records).
No Round-1/2/3 fixture is read or modified, and the real pilot export is never used. Sockets are refused.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

from v02_support import no_network  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import jd_skill_survey as S  # noqa: E402

PROFILE = S.load_profile()


def html(*sections, preamble=""):
    out = f"<p>{preamble}</p>" if preamble else ""
    for heading, items in sections:
        out += f"<p><strong>{heading}</strong></p><ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
    return out


def text_of(h):
    return S.re.sub(r"<[^>]+>", "\n", h)


def rec(i, title="AI Engineer", company=None, desc_html="", **over):
    r = {"id": str(9000000 + i), "title": title, "companyName": company or f"Synthco {i}", "location": "Remote, India",
         "link": f"https://in.linkedin.com/jobs/view/ai-engineer-at-synthco-{9000000 + i}?trk=t{i}",
         "employmentType": "Full-time", "descriptionHtml": desc_html, "descriptionText": text_of(desc_html)}
    r.update(over)
    return {k: v for k, v in r.items() if v is not None}


def analyse(title, h):
    return S.analyse_job(title, h, text_of(h), PROFILE)


def write(tmp_path, records, name="x.json", jsonl=False):
    p = tmp_path / name
    if jsonl:
        p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    else:
        p.write_text(json.dumps(records), encoding="utf-8")
    return p


RAG_CORE = html(("Responsibilities", ["Build production RAG pipelines with embeddings and a vector database",
                                      "Design hybrid search with BM25 and reranking"]),
                ("Requirements", ["3+ years of Python experience", "Experience with FastAPI and REST APIs"]))


# ------------------------------------------------------------------ input / population (1-5)

def test_json_list_input(tmp_path):
    p = write(tmp_path, [rec(1, desc_html=RAG_CORE), rec(2, desc_html=RAG_CORE)])
    s = S.survey(p, with_jobops=False)
    assert len(s["jobs"]) == 2 and s["population"]["raw_rows"] == 2


def test_jsonl_input(tmp_path):
    p = write(tmp_path, [rec(1, desc_html=RAG_CORE), rec(2, desc_html=RAG_CORE)], name="x.jsonl", jsonl=True)
    assert len(S.survey(p, with_jobops=False)["jobs"]) == 2


def test_duplicate_ids_collapse_and_keep_richest(tmp_path):
    short = rec(1, desc_html=html(("Responsibilities", ["Build RAG pipelines"])))
    long = rec(1, desc_html=RAG_CORE, link="https://in.linkedin.com/jobs/view/ai-engineer-9000001?trk=other")
    s = S.survey(write(tmp_path, [short, long, rec(2, desc_html=RAG_CORE)]), with_jobops=False)
    m = S.metrics(s)
    assert (m["raw_jobs"], m["unique_jobs"], m["duplicates"]) == (3, 2, 1)
    job = next(j for j in s["jobs"] if j["job_id"] == "9000001")
    assert job["records"] == [0, 1] and "BM25" in job["terms"]  # the richer description represents the job


def test_duplicate_links_without_id(tmp_path):
    a = rec(1, desc_html=RAG_CORE, id=None, link="https://in.linkedin.com/jobs/view/ai-engineer-4400000001?trk=a")
    b = rec(2, desc_html=RAG_CORE, id=None, link="https://in.linkedin.com/jobs/view/ai-engineer-4400000001?trk=b")
    s = S.survey(write(tmp_path, [a, b]), with_jobops=False)
    assert len(s["jobs"]) == 1 and s["jobs"][0]["id_method"] == "link_view_id"


def test_missing_id_and_link_falls_back_to_company_title_location(tmp_path):
    a = rec(1, desc_html=RAG_CORE, id=None, link=None, company="Fallback Co")
    b = rec(2, desc_html=RAG_CORE, id=None, link=None, company="Fallback Co")
    c = rec(3, desc_html=RAG_CORE, id=None, link=None, company="Other Co")
    s = S.survey(write(tmp_path, [a, b, c]), with_jobops=False)
    assert len(s["jobs"]) == 2 and {j["id_method"] for j in s["jobs"]} == {"company_title_location"}
    assert all(not j["job_id"].startswith("ctl") for j in s["jobs"])  # hashed, stable id


# ------------------------------------------------------------------ placement (6-10)

def test_rag_core_requirement():
    a = analyse("AI Engineer", RAG_CORE)
    assert a["terms"]["RAG"]["placement"] == "CORE"
    assert a["clusters"]["C2"]["intensity"] == "HIGH"


def test_rag_preferred_requirement():
    a = analyse("AI Engineer", html(("Requirements", ["Strong Python and REST APIs experience"]),
                                    ("Nice to have", ["Exposure to RAG and vector databases"])))
    assert a["terms"]["RAG"]["placement"] == "PREFERRED"
    assert "RAG" not in a["clusters"]["C2"]["all_core"]


def test_preferred_cue_inside_required_section():
    a = analyse("AI Engineer", html(("Required Skills", ["Python", "Knowledge of RAG is a plus"])))
    assert a["terms"]["RAG"]["placement"] == "PREFERRED" and a["terms"]["Python"]["placement"] == "CORE"


def test_rag_incidental_mention():
    a = analyse("Backend Engineer", html(("About Us", ["Our platform uses RAG to answer customer questions"]),
                                         ("Requirements", ["Strong Java experience"])))
    assert a["terms"]["RAG"]["placement"] == "INCIDENTAL"
    assert a["clusters"]["C2"]["intensity"] == "NONE"


def test_unknown_placement_is_not_forced():
    a = analyse("AI Engineer", html(("Our Ecosystem Notes", ["RAG and LangChain appear across several teams"])))
    assert a["terms"]["RAG"]["placement"] == "UNKNOWN_PLACEMENT"
    assert a["clusters"]["C2"]["intensity"] == "UNKNOWN"
    assert a["clusters"]["C2"]["all_core"] == [] and a["clusters"]["C2"]["all_preferred"] == []


def test_preferred_section_ends_at_next_heading():
    a = analyse("AI Engineer", html(("Preferred", ["Kubernetes"]), ("Responsibilities", ["Build RAG pipelines"])))
    assert a["terms"]["Kubernetes"]["placement"] == "PREFERRED" and a["terms"]["RAG"]["placement"] == "CORE"


def test_title_only_rag():
    a = analyse("Senior RAG Engineer", html(("Requirements", ["Strong Python and SQL"])))
    assert "RAG" in a["title_only"] and "RAG" not in a["terms"]
    assert a["clusters"]["C2"]["intensity"] == "NONE"


# ------------------------------------------------------------------ clusters / archetypes (11-17, 25)

def test_agentic_core_requirement():
    a = analyse("AI Engineer", html(("Responsibilities", ["Develop multi-agent workflows with CrewAI",
                                                          "Build AI agents with tool calling", "Use MCP servers"])))
    assert a["clusters"]["C3"]["intensity"] == "HIGH"
    assert a["archetype"] == "LLM / RAG / Agentic — PRIMARY"


def test_langgraph_preferred():
    a = analyse("AI Engineer", html(("Responsibilities", ["Build agentic workflows"]),
                                    ("Good to have", ["LangGraph"])))
    assert a["terms"]["LangGraph"]["placement"] == "PREFERRED"
    assert "LangGraph" in a["alignment"]["preferred_only"] and "LangGraph" not in a["alignment"]["working_gaps"]


EVAL_JD = html(("Responsibilities", ["Design evaluation frameworks for LLM applications",
                                     "Build golden datasets and an evaluation harness",
                                     "Measure hallucination and faithfulness with Ragas and LLM-as-judge"]),
               ("Requirements", ["Python", "Experience with LLMs"]))


def test_evaluation_core_requirement():
    a = analyse("AI Quality Engineer", EVAL_JD)
    assert a["clusters"]["C4"]["intensity"] == "HIGH"
    assert a["archetype"] == "LLM Evaluation / AI Reliability — PRIMARY"


ML_JD = html(("Responsibilities", ["Train classification models with XGBoost", "Own feature engineering",
                                   "Run hyperparameter tuning", "Build forecasting models with scikit-learn"]),
             ("Requirements", ["Python", "Statistical modeling background"]))


def test_traditional_ml_heavy_role():
    a = analyse("Data Scientist", ML_JD)
    assert a["ml"]["ML_DOMINANT"] and a["archetype"] == "Traditional ML — PRIMARY"


def test_hybrid_llm_and_ml_role():
    h = html(("Responsibilities", ["Build RAG pipelines with embeddings", "Develop AI agents with LangChain",
                                   "Train classification models with XGBoost", "Own feature engineering"]))
    a = analyse("Applied AI Engineer", h)
    assert a["ml"]["ML_SUBSTANTIVE"] and a["archetype"] == "Hybrid LLM + Traditional ML"


def test_generic_ai_role():
    a = analyse("Software Engineer", html(("Requirements", ["Strong Java experience", "Kafka and Spark"])))
    assert a["archetype"] in ("Generic AI / Data / Other", "AI keyword only / insufficient evidence")
    a2 = analyse("Software Engineer", html(("Our Ecosystem Notes", ["We like AI"])))
    assert a2["archetype"] == "AI keyword only / insufficient evidence"


def test_ml_keyword_mention_does_not_make_role_ml_heavy():
    h = html(("Responsibilities", ["Build RAG pipelines with embeddings and a vector database",
                                   "Develop AI agents with tool calling",
                                   "Apply machine learning and AI/ML best practices"]),
             ("Requirements", ["Familiarity with PyTorch, TensorFlow, scikit-learn", "Data science mindset"]),
             ("Qualifications", ["Bachelor's degree in Computer Science, Statistics or Data Science"]))
    a = analyse("AI Engineer", h)
    assert a["ml"]["ML_MENTION"] and not a["ml"]["ML_SUBSTANTIVE"] and not a["ml"]["ML_DOMINANT"]
    assert a["archetype"] == "LLM / RAG / Agentic — PRIMARY"
    # The degree line names a field of study; it is not a capability requirement.
    assert "Statistical modeling" not in a["terms"]


def test_multiple_capability_clusters():
    h = html(("Responsibilities", ["Build RAG pipelines with embeddings", "Develop multi-agent systems with LangGraph",
                                   "Create evaluation pipelines with DeepEval", "Deploy FastAPI services on AWS with Docker"]))
    a = analyse("AI Engineer", h)
    lit = {c for c in S.CLUSTERS if a["clusters"][c]["intensity"] in ("HIGH", "MODERATE", "LOW")}
    assert {"C2", "C3", "C4", "C5"} <= lit
    assert a["archetype"] in S.ARCHETYPES  # exactly one primary archetype


# ------------------------------------------------------------------ candidate alignment / gaps (18-22)

def test_candidate_core_capability_match():
    a = analyse("AI Engineer", RAG_CORE)
    assert {"RAG", "BM25", "Embeddings", "Python", "FastAPI"} <= set(a["alignment"]["candidate_core_present"])
    assert a["alignment"]["primary_capability_alignment"] == "DIRECT"


def test_candidate_working_capability_is_working_gap_not_absence():
    a = analyse("AI Engineer", html(("Requirements", ["Hands-on LangGraph experience", "Build RAG pipelines"])))
    assert "LangGraph" in a["alignment"]["working_gaps"] and "LangGraph" not in a["alignment"]["core_gaps"]
    assert "LangGraph" in a["alignment"]["candidate_working_present"]


def test_candidate_limited_capability():
    a = analyse("Data Scientist", ML_JD)
    lim = set(a["alignment"]["candidate_limited"])
    assert {"Gradient boosting family", "Feature engineering", "Hyperparameter tuning"} <= lim
    assert lim <= set(a["alignment"]["core_gaps"])
    assert a["alignment"]["primary_capability_alignment"] == "LIMITED"


def test_genuine_core_gap():
    a = analyse("AI Engineer", html(("Requirements", ["Build RAG pipelines", "Must have Kubernetes in production"])))
    assert "Kubernetes" in a["alignment"]["core_gaps"]
    assert a["terms"]["Kubernetes"]["candidate"] == "NOT_ESTABLISHED"


def test_preferred_skill_is_never_a_core_gap():
    a = analyse("AI Engineer", html(("Requirements", ["Build RAG pipelines"]), ("Preferred", ["Pinecone", "Kubernetes"])))
    assert not ({"Pinecone", "Kubernetes"} & set(a["alignment"]["core_gaps"]))
    assert {"Pinecone", "Kubernetes"} <= set(a["alignment"]["preferred_only"])


# ------------------------------------------------------------------ experience (23-24)

@pytest.mark.parametrize("line,lo,hi", [("3-5 years of experience in Python", 3, 5), ("5+ years of experience", 5, None),
                                        ("Minimum 4 years of relevant experience", 4, None),
                                        ("5 years of experience building APIs", 5, None)])
def test_experience_extraction(line, lo, hi):
    a = analyse("AI Engineer", html(("Requirements", [line])))
    e = a["experience"]
    assert (e["min_years"], e["max_years"]) == (lo, hi) and e["status"] == "STATED"
    assert e["evidence"] and e["placement"] == "CORE"


def test_experience_largest_stated_minimum_wins():
    a = analyse("AI Engineer", html(("Requirements", ["2+ years of experience with LLMs", "6+ years of overall experience"])))
    assert a["experience"]["min_years"] == 6


def test_no_experience_stated():
    a = analyse("Senior AI Engineer", html(("About Us", ["Founded 20 years ago, we have 15 years in business"]),
                                           ("Requirements", ["Build RAG pipelines"])))
    assert a["experience"]["status"] == "NOT_STATED" and a["experience"]["min_years"] is None


# ------------------------------------------------------------------ evidence (26)

def test_evidence_snippets_are_verbatim_substrings(tmp_path):
    recs = [rec(1, desc_html=RAG_CORE), rec(2, desc_html=EVAL_JD), rec(3, desc_html=ML_JD)]
    s = S.survey(write(tmp_path, recs), with_jobops=False)
    for j in s["jobs"]:
        corpus = " ".join(b["text"] for b in j["placed"])
        for t, v in j["terms"].items():
            for evs in v["all"].values():
                for e in evs:
                    assert e["snippet"].strip("…") in corpus, (t, e["snippet"])
                    assert e["matched"] in e["snippet"]
    S.write_outputs(s, tmp_path / "o")
    rows = list(csv.DictReader(open(tmp_path / "o" / "jobs.csv", encoding="utf-8")))
    assert all(r["evidence_snippets"] and r["evidence_snippets"] != "evidence_unavailable" for r in rows)


def test_outputs_have_no_score_or_ranking(tmp_path):
    s = S.survey(write(tmp_path, [rec(1, desc_html=RAG_CORE), rec(2, desc_html=ML_JD)]), with_jobops=False)
    S.write_outputs(s, tmp_path / "o")
    for name in ("jobs.csv", "capabilities.csv", "gaps.csv", "experience.csv", "archetypes.csv"):
        header = (tmp_path / "o" / name).read_text(encoding="utf-8").splitlines()[0].lower()
        assert not any(w in header for w in ("score", "rank", "fit_", "percent")), (name, header)
    assert "score" not in json.dumps(S.metrics(s)).lower()
    summary = (tmp_path / "o" / "summary.md").read_text(encoding="utf-8")
    assert "does not modify JobOps eligibility, relevance, lane, queue, compensation" in summary
    assert "you should apply" not in summary.lower()


def test_outputs_are_deterministic(tmp_path):
    p = write(tmp_path, [rec(1, desc_html=RAG_CORE), rec(2, desc_html=EVAL_JD), rec(3, desc_html=ML_JD)])
    for name in ("a", "b"):
        S.write_outputs(S.survey(p, with_jobops=False), tmp_path / name)
    for f in ("jobs.csv", "capabilities.csv", "gaps.csv", "experience.csv", "archetypes.csv", "metrics.json", "summary.md"):
        assert (tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes(), f


def test_jobops_context_is_attached_but_never_filters(tmp_path):
    recs = [rec(1, desc_html=RAG_CORE), rec(2, desc_html=ML_JD, location="Mumbai, Maharashtra, India",
                                             workplaceType="On-site")]
    s = S.survey(write(tmp_path, recs), with_jobops=True)
    assert len(s["jobs"]) == 2 and s["jobops_check"]["one_to_one"]
    assert all(j["ctx"]["lane"] for j in s["jobs"])
    assert s["jobops_check"]["policy_sha256"] == SHA26


# ------------------------------------------------------------------ integrity (27)

SHA26 = "de527c5d1dceb400913ec42e5aa527f19cd809e5054fcef5c61337d7fb890455"


def test_no_jobops_policy_modification(tmp_path):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "policy").glob("*.json"))}
    assert before["jobops-policy-0.2.6.json"] == SHA26
    S.survey(write(tmp_path, [rec(1, desc_html=RAG_CORE)]), with_jobops=True)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "policy").glob("*.json"))}
    assert before == after


def test_tool_imports_no_network_or_llm_module():
    import ast
    forbidden = {"socket", "ssl", "http", "urllib", "requests", "httpx", "aiohttp", "openai", "anthropic", "subprocess"}
    tree = ast.parse((ROOT / "tools" / "jd_skill_survey.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
            [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else [])
        for n in names:
            assert n.split(".")[0] not in forbidden, n


def test_profile_levels_follow_the_documented_profile():
    assert S.candidate_level("RAG", PROFILE) == "CORE"
    assert S.candidate_level("LangGraph", PROFILE) == "WORKING"
    assert S.candidate_level("Ragas", PROFILE) == "WORKING" and S.candidate_level("DeepEval", PROFILE) == "WORKING"
    assert S.candidate_level("Gradient boosting family", PROFILE) == "LIMITED"
    assert S.candidate_level("Kubernetes", PROFILE) == "NOT_ESTABLISHED"
    assert S.candidate_level("OpenAI / GPT", PROFILE) == "CORE"  # normalised to the LLM APIs family


def test_degree_line_is_incidental_not_a_capability_requirement():
    a = analyse("AI Engineer", html(("Requirements", ["Build RAG pipelines",
                                                      "Master's degree in Statistical Modeling or Machine Learning"])))
    assert a["terms"]["Statistical modeling"]["placement"] == "INCIDENTAL"
    assert "Statistical modeling" not in a["alignment"]["core_gaps"]
    assert not a["ml"]["ML_REQUIRED"]


def test_generic_ml_wording_is_never_a_core_gap():
    a = analyse("AI Engineer", html(("Requirements", ["Build RAG pipelines", "Experience with AI/ML and machine learning",
                                                      "Strong NLP background"])))
    assert {"Machine learning (generic)", "NLP (generic)"} <= set(a["alignment"]["generic_ml_mentions"])
    assert not ({"Machine learning (generic)", "NLP (generic)"} & set(a["alignment"]["core_gaps"]))
    assert a["alignment"]["primary_capability_alignment"] == "DIRECT"
