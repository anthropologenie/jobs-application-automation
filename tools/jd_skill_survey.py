"""
P11 — Real-JD role-capability survey (offline, deterministic, descriptive).

    python3 tools/jd_skill_survey.py --input exports/linkedin-2026-10-01.json \
        --out runs/skill_survey_2026-10-02 [--date 2026-10-01] [--no-jobops] [--decisions-db runs/state/jobops-p9.sqlite]

What it does
  * Reads a downloaded export (JSON list / container, JSONL or CSV) with the existing jobops.normalize readers.
  * Deduplicates to one record per job (LinkedIn id, else /jobs/view/<n>, else URL without query, else
    company|title|location) and keeps the richest description of each job.
  * Splits each JD into blocks (HTML <p>/<li>/<h*> when available, else lines), classifies section headings
    conservatively, and gives every block an evidence placement: CORE / PREFERRED / INCIDENTAL / UNKNOWN_PLACEMENT.
  * Matches a fixed lexicon of capability terms (clusters C1-C7, plus X0 = non-AI stack, outside C1-C7) and keeps
    the verbatim block each match came from. Title matches are kept separately (TITLE_ONLY never counts as CORE).
  * Derives per-cluster intensity, Traditional-ML levels, one primary archetype, experience requirements and a
    descriptive comparison with the candidate profile in tools/jd_survey_candidate_profile.json.
  * Optionally (default on) runs the unchanged JobOps engine on the same file in a TEMPORARY state directory to
    attach the existing lane / relevance / P10 tier as context. JobOps outputs are never written or changed, and
    the survey never filters on them.

What it is not
  No score, no ranking, no fit percentage, no recommendation, no change to any JobOps decision or policy.
  A keyword match is evidence that the JD asks for something, not evidence of the candidate's expertise.
  No network, no LLM, standard library only.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import statistics
import sys
import tempfile
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobops import normalize  # noqa: E402

PROFILE_PATH = Path(__file__).resolve().parent / "jd_survey_candidate_profile.json"

CLUSTERS = {
    "C1": "LLM application engineering",
    "C2": "RAG / retrieval",
    "C3": "Agentic AI",
    "C4": "AI evaluation / reliability",
    "C5": "AI backend / platform engineering",
    "C6": "AI-SDLC / engineering automation",
    "C7": "Traditional ML / data science",
}
X0 = "X0"  # non-AI engineering stack: reported, never part of C1-C7, intensity or archetype
PLACEMENTS = ("CORE", "PREFERRED", "UNKNOWN_PLACEMENT", "INCIDENTAL")  # priority order for a job's term placement
INTENSITIES = ("HIGH", "MODERATE", "LOW", "UNKNOWN", "NONE")
RANK = {"HIGH": 3, "MODERATE": 2, "LOW": 1, "UNKNOWN": 0, "NONE": 0}
ARCHETYPES = (
    "LLM / RAG / Agentic — PRIMARY",
    "LLM Evaluation / AI Reliability — PRIMARY",
    "LLM Application + Backend — PRIMARY",
    "Hybrid LLM + Traditional ML",
    "Traditional ML — PRIMARY",
    "AI-SDLC / Engineering Automation — PRIMARY",
    "AI Backend / Platform — PRIMARY",
    "Generic AI / Data / Other",
    "AI keyword only / insufficient evidence",
)
ALIGNMENTS = ("DIRECT", "ADJACENT", "PARTIAL", "LIMITED", "INSUFFICIENT_EVIDENCE")
CANDIDATE_LEVELS = ("CORE", "WORKING", "SUPPORTING", "LIMITED", "NOT_ESTABLISHED")
ML_LEVELS = ("NONE", "ML_MENTION", "ML_PREFERRED", "ML_REQUIRED", "ML_SUBSTANTIVE", "ML_DOMINANT")


# =================================================================================================== lexicon
# (canonical term, cluster, regex, profile key or None (= the term itself), tags)
# Regexes are case-insensitive; (?-i:...) marks case-sensitive acronyms. Tags:
#   ml_strong  - concrete traditional-ML work (counts toward ML_REQUIRED / SUBSTANTIVE / DOMINANT)
#   ml_weak    - generic ML wording (ML_MENTION only; never makes a role ML-heavy on its own)
#   ai_sdlc    - AI-specific C6 term (needed for the AI-SDLC archetype; plain test automation is not enough)
#   ai_platform- AI-specific C5 term (MLOps, model serving, Bedrock ...)

LEXICON: List[Tuple[str, str, str, Optional[str], Tuple[str, ...]]] = [
    # ---- C1 LLM application engineering
    ("OpenAI / GPT", "C1", r"\bopen ?ai\b(?! *agents)|\bchat ?gpt\b|\bgpt[- ]?\d(\.\d)?[a-z]?\b|(?-i:\bGPT\b)", "LLM APIs", ()),
    ("Anthropic / Claude", "C1", r"\banthropic\b|\bclaude\b", "LLM APIs", ()),
    ("Gemini", "C1", r"\bgemini\b", "LLM APIs", ()),
    ("DeepSeek", "C1", r"\bdeep ?seek\b", "LLM APIs", ()),
    ("Llama / Mistral (open models)", "C1", r"\bllama(?! ?index)(?:[- ]?\d)?\b|\bmistral\b", "LLM APIs", ()),
    ("LLMs (generic)", "C1", r"\bllms?\b|\blarge language models?\b", "LLM APIs", ()),
    ("Generative AI", "C1", r"\bgen ?ai\b|\bgenerative ai\b|\bgenerative models?\b", "Generative AI", ()),
    ("Prompt engineering", "C1",
     r"\bprompt (engineering|design|tuning|templates?|optimi[sz]ation|management|chaining|strateg(y|ies))\b"
     r"|\bprompting\b|\bprompts\b", "Prompt engineering", ()),
    ("Structured output", "C1", r"\bstructured (outputs?|generation)\b|\bjson mode\b", "Structured output", ()),
    ("Tool / function calling", "C1", r"\b(function|tool)[- ]calling\b", "Tool / function calling", ()),
    ("Context management", "C1", r"\bcontext (windows?|management|engineering)\b", "Context management", ()),
    ("Fine-tuning", "C1", r"\bfine[- ]?tun(e|ed|ing)\b", None, ()),
    ("LoRA / PEFT", "C1", r"\b(q?lora|peft)\b", None, ()),
    ("RLHF", "C1", r"\brlhf\b", None, ()),
    ("Hugging Face", "C1", r"\bhugging ?face\b", None, ()),
    # ---- C2 RAG / retrieval
    ("RAG", "C2", r"(?-i:\bRAGs?\b)|\bretrieval[- ]augmented\b|\bretrieval augmented\b", "RAG", ()),
    ("Embeddings", "C2", r"\bembeddings\b|\b(vector|text|semantic) embeddings?\b|\bembedding (models?|vectors?|generation|space|pipelines?)\b",
     "Embeddings", ()),
    ("Vector DB", "C2", r"\bvector (databases?|dbs?|stores?|indexes|index|search engines?)\b|\bpgvector\b", "Vector DB", ()),
    ("Pinecone", "C2", r"\bpinecone\b", None, ()),
    ("Weaviate", "C2", r"\bweaviate\b", None, ()),
    ("Milvus", "C2", r"\bmilvus\b", None, ()),
    ("Qdrant", "C2", r"\bqdrant\b", None, ()),
    ("Chroma", "C2", r"\bchroma(db)?\b", "Chroma", ()),
    ("FAISS", "C2", r"\bfaiss\b", "FAISS", ()),
    ("OpenSearch / Elasticsearch", "C2", r"\bopen ?search\b|\belastic ?search\b", None, ()),
    ("Vector / semantic search", "C2", r"\b(vector|semantic|similarity|neural) search\b", "Vector / semantic search", ()),
    ("BM25", "C2", r"\bbm-?25\b", "BM25", ()),
    ("Hybrid search", "C2", r"\bhybrid (search|retrieval)\b", "Hybrid search", ()),
    ("Reranking", "C2", r"\bre-?rank(ing|ers?)?\b", "Reranking", ()),
    ("RRF", "C2", r"(?-i:\bRRF\b)|\breciprocal rank fusion\b", "RRF", ()),
    ("Retrieval systems", "C2", r"\binformation retrieval\b|\bretrieval (systems?|pipelines?|strateg(y|ies)|quality)\b|\bchunking\b",
     "RAG", ()),
    ("Knowledge graphs / Graph RAG", "C2", r"\bknowledge graphs?\b|\bgraph ?rag\b|\bneo4j\b", None, ()),
    # ---- C3 Agentic AI
    ("AI agents / agentic", "C3",
     r"\bagentic\b|\b(ai|llm|autonomous|intelligent|conversational|gen ?ai|software|voice) agents?\b"
     r"|\bagents? (frameworks?|workflows?|systems?|architectures?|development|based|design)\b|\bbuild(ing)? agents\b",
     "AI agents / agentic", ()),
    ("Multi-agent", "C3", r"\bmulti[- ]?agents?\b", "Multi-agent", ()),
    ("LangChain", "C3", r"\blang ?chain\b", "LangChain", ()),
    ("LangGraph", "C3", r"\blang ?graph\b", "LangGraph", ()),
    ("CrewAI", "C3", r"\bcrew ?ai\b", "CrewAI", ()),
    ("AutoGen", "C3", r"\bautogen\b", None, ()),
    ("LlamaIndex", "C3", r"\bllama ?index\b", None, ()),
    ("Semantic Kernel", "C3", r"\bsemantic kernel\b", None, ()),
    ("MCP", "C3", r"(?-i:\bMCP\b)|\bmodel[- ]context[- ]protocol\b", "MCP", ()),
    ("Agent orchestration", "C3", r"\b(agent|agentic|llm|multi-agent) (orchestration|planning)\b|\borchestrat\w+ (of )?(ai |llm )?agents\b",
     "Agent orchestration", ()),
    ("Tool use (agents)", "C3", r"\btool[- ]use\b|\btool integrations?\b", "Tool / function calling", ()),
    # ---- C4 AI evaluation / reliability
    ("LLM / model evaluation", "C4",
     r"\b(llm|ai|model|genai|gen ai|rag|agent|agentic) eval(uation)?s?\b|\bevals\b|\bevaluation (frameworks?|metrics|methodolog(y|ies))\b",
     "LLM evaluation", ()),
    ("Evaluation pipeline / harness", "C4", r"\bevaluation (harness(es)?|pipelines?|suites?)\b", "Evaluation pipeline / harness", ()),
    ("Ragas", "C4", r"\bragas\b", "Ragas", ()),
    ("DeepEval", "C4", r"\bdeep ?eval\b", "DeepEval", ()),
    ("Promptfoo", "C4", r"\bpromptfoo\b", None, ()),
    ("LLM-as-judge", "C4", r"\bllm[- ]as[- ](a[- ])?judges?\b", "LLM-as-judge", ()),
    ("Evaluation datasets", "C4", r"\b(evaluation|golden|eval|test) (data ?sets?)\b|\bgolden (data|sets?)\b", "Evaluation datasets", ()),
    ("Benchmarks", "C4",
     r"\bbenchmark(s|ing)? (models?|llms?|ai|agents?|performance|quality|frameworks?|suites?|datasets?|results)\b"
     r"|\b(model|llm|ai|agent|eval(uation)?) benchmark(s|ing)?\b|\bbenchmark(ing)? frameworks?\b", "Benchmarks", ()),
    ("Grounding / hallucination", "C4",
     r"\bhallucinations?\b|\bgrounded(ness)?\b|\bgrounding\b|\bfaithfulness\b|\banswer relevan(cy|ce)\b|\bcontext (precision|recall)\b",
     "Grounding / hallucination", ()),
    ("LLM observability / tracing", "C4",
     r"\b(llm|ai|model|agent|genai)[- ](observability|monitoring|tracing)\b|\blangsmith\b|\blangfuse\b|\barize( phoenix)?\b",
     None, ()),
    ("Guardrails", "C4", r"\bguardrails?\b", "Guardrails", ()),
    ("Responsible AI / AI safety", "C4", r"\bresponsible ai\b|\bai safety\b|\bai governance\b|\bai ethics\b", None, ()),
    ("AI quality / reliability", "C4", r"\b(ai|llm|model|genai) (quality|reliability|testing)\b|\bquality of (ai|llm)\b",
     "AI quality / reliability", ()),
    # ---- C5 AI backend / platform
    ("Python", "C5", r"\bpython\b", "Python", ()),
    ("FastAPI", "C5", r"\bfast ?api\b", "FastAPI", ()),
    ("Flask", "C5", r"\bflask\b", None, ()),
    ("Django", "C5", r"\bdjango\b", None, ()),
    ("Pydantic", "C5", r"\bpydantic\b", "Pydantic", ()),
    ("REST / APIs", "C5", r"(?-i:\bREST(ful)?\b)|\brestful\b|\bapis?\b", "REST / APIs", ()),
    ("Async programming", "C5", r"\basync(io)?\b|\basynchronous programming\b", None, ()),
    ("SQL", "C5", r"(?-i:\bSQL\b)|\bpostgres(ql)?\b|\bmysql\b", "SQL", ()),
    ("Docker", "C5", r"\bdocker\b|\bcontaineri[sz]\w*\b", "Docker", ()),
    ("Kubernetes", "C5", r"\bkubernetes\b|(?-i:\bk8s\b|\bEKS\b|\bAKS\b|\bGKE\b)", None, ()),
    ("CI/CD", "C5", r"\bci ?/ ?cd\b|\bcontinuous (integration|delivery|deployment)\b|\bgithub actions\b|\bjenkins\b", "CI/CD", ()),
    ("Git / GitHub", "C5", r"\bgit\b|\bgithub\b(?! actions)|\bgitlab\b|\bbitbucket\b", "Git / GitHub", ()),
    ("AWS", "C5", r"(?-i:\bAWS\b)|\bamazon web services\b", "AWS", ()),
    ("AWS Bedrock", "C5", r"\bbedrock\b", "AWS Bedrock", ("ai_platform",)),
    ("SageMaker", "C5", r"\bsage ?maker\b", None, ("ai_platform",)),
    ("Azure", "C5", r"\bazure\b(?! open ?ai)", None, ()),
    ("Azure OpenAI", "C5", r"\bazure open ?ai\b", None, ("ai_platform",)),
    ("GCP", "C5", r"(?-i:\bGCP\b)|\bgoogle cloud\b", None, ()),
    ("Vertex AI", "C5", r"\bvertex( ai)?\b", None, ("ai_platform",)),
    ("Databricks", "C5", r"\bdatabricks\b", "Databricks", ()),
    ("MLOps / LLMOps", "C5", r"\bmlops\b|\bllmops\b|\baiops\b", None, ("ai_platform",)),
    ("Model serving / deployment", "C5",
     r"\bmodel (serving|deployment|inference)\b|\b(deploy|deploying|serve|serving) (llms?|ml models?|models)\b"
     r"|\binference (servers?|endpoints?|optimi[sz]ation)\b|\bvllm\b|\btriton\b", None, ("ai_platform",)),
    ("Microservices", "C5", r"\bmicro-?services?\b", None, ()),
    ("Backend architecture", "C5", r"\bback-?end (architecture|systems?|services?|development|engineering)\b", None, ()),
    ("Observability / monitoring (general)", "C5",
     r"\bobservability\b|\bopen ?telemetry\b|\bprometheus\b|\bgrafana\b|\bdatadog\b"
     r"|\bmonitoring (tools?|systems?|stacks?|dashboards?|and (alerting|logging|observability))\b|\b(logging|alerting),? and monitoring\b",
     None, ()),
    # ---- C6 AI-SDLC / engineering automation
    ("AI coding / code generation", "C6",
     r"\bcode generation\b|\bai coding\b|\bcoding (agents?|assistants?|copilots?)\b|\bgithub copilot\b"
     r"|\bai[- ](assisted|powered) (coding|development|software development)\b", None, ("ai_sdlc",)),
    ("Developer productivity", "C6", r"\bdeveloper (productivity|experience)\b", None, ("ai_sdlc",)),
    ("Code intelligence", "C6", r"\bcode (intelligence|understanding)\b|\brepository[- ](grounded|aware|level)\b", None, ("ai_sdlc",)),
    ("AI-powered testing", "C6", r"\b(ai|llm|genai|gen ai)[- ](powered|driven|based|assisted) (testing|test automation|qa|quality)\b",
     "AI-powered testing", ("ai_sdlc",)),
    ("Test generation (AI)", "C6", r"\btest (case )?generation\b", "Test generation (AI)", ("ai_sdlc",)),
    ("Root-cause analysis", "C6", r"\broot[- ]cause analysis\b|(?-i:\bRCA\b)|\bfailure analysis\b|\bdefect triage\b",
     "Root-cause analysis", ("ai_sdlc",)),
    ("SDLC automation", "C6", r"\bsdlc automation\b|\bai[- ]sdlc\b|\bengineering agents?\b|\bai (across|in) the sdlc\b",
     None, ("ai_sdlc",)),
    ("Test automation", "C6", r"\btest automation\b|\bautomated testing\b|\bautomation testing\b|\bautomated tests\b",
     "Test automation", ()),
    ("Quality engineering", "C6", r"\bquality engineering\b|\bqa engineering\b", "Quality engineering", ()),
    ("SDET", "C6", r"(?-i:\bSDET\b)", "SDET", ()),
    ("pytest", "C6", r"\bpytest\b", "pytest", ()),
    # ---- C7 Traditional ML / data science
    ("scikit-learn", "C7", r"\bscikit[- ]?learn\b|\bsklearn\b", "scikit-learn", ("ml_strong",)),
    ("Gradient boosting family", "C7", r"\bxgboost\b|\blightgbm\b|\bcatboost\b|\bgradient[- ]boost(ing|ed)?\b",
     "Gradient boosting family", ("ml_strong",)),
    ("PyTorch", "C7", r"\bpy ?torch\b", None, ("ml_strong",)),
    ("TensorFlow / Keras", "C7", r"\btensor ?flow\b|\bkeras\b", None, ("ml_strong",)),
    ("Feature engineering", "C7", r"\bfeature engineering\b", "Feature engineering", ("ml_strong",)),
    ("Model training", "C7",
     r"\b(model|ml) training\b|\btrain(ing)? (ml |machine learning |deep learning |predictive |custom )?models\b"
     r"|\b(ml|machine learning) model development\b|\bmodel building\b", "Model training", ("ml_strong",)),
    ("Hyperparameter tuning", "C7", r"\bhyper-?parameter\w*\b|\bmodel tuning\b", "Hyperparameter tuning", ("ml_strong",)),
    ("Classical ML tasks", "C7",
     r"\b(classification|regression|clustering|forecasting|predictive) (models?|algorithms?|tasks?|problems?|modell?ing)\b"
     r"|\b(logistic|linear) regression\b|\btime[- ]series\b|\banomaly detection\b|\bsupervised (and unsupervised )?learning\b"
     r"|\bunsupervised learning\b", "Classical ML tasks", ("ml_strong",)),
    ("Recommendation systems", "C7", r"\brecommend(ation|er) (systems?|engines?|models?)\b", None, ("ml_strong",)),
    ("Computer vision / OCR", "C7", r"\bcomputer vision\b|\bobject detection\b|\bimage (classification|recognition|segmentation)\b"
     r"|\bopencv\b|\byolo\b|(?-i:\bOCR\b)", None, ("ml_strong",)),
    ("BERT / classical NLP models", "C7", r"(?-i:\bBERT\b)|\bspacy\b|\bnltk\b|\bnamed entity recognition\b|\bsentiment analysis\b",
     None, ("ml_strong",)),
    ("Statistical modeling", "C7", r"\bstatistical (modell?ing|analysis|models?|methods?|learning)\b", "Statistical modeling",
     ("ml_strong",)),
    ("A/B testing / experimentation", "C7",
     r"\ba/b test(ing|s)?\b|\bab testing\b|\bexperimentation (frameworks?|platforms?|design)\b|\b(online|controlled) experiments?\b",
     None, ("ml_strong",)),
    ("ML pipelines", "C7", r"\b(ml|machine learning) pipelines?\b", None, ("ml_strong",)),
    ("Machine learning (generic)", "C7", r"\bmachine learning\b|(?-i:\bML\b)|\bai/ml\b", "Traditional ML (generic)", ("ml_weak",)),
    ("Deep learning (generic)", "C7", r"\bdeep learning\b|\bneural networks?\b", None, ("ml_weak",)),
    ("NLP (generic)", "C7", r"(?-i:\bNLP\b)|\bnatural language processing\b", None, ("ml_weak",)),
    ("Data science (generic)", "C7", r"\bdata scien(ce|tists?)\b", None, ("ml_weak",)),
    ("Pandas / NumPy", "C7", r"\bpandas\b|\bnumpy\b", "Pandas / NumPy", ("ml_weak",)),
    # ---- X0 non-AI engineering stack (outside C1-C7; for top-technology and gap reporting only)
    ("Java", X0, r"\bjava\b(?!script)", None, ()),
    (".NET / C#", X0, r"\.net\b|\bc#", None, ()),
    ("JavaScript / TypeScript", X0, r"\bjavascript\b|\btypescript\b", None, ()),
    ("Node.js", X0, r"\bnode(\.js|js)?\b(?= |,|\.|;|/|\))", None, ()),
    ("React / Angular / Vue", X0, r"\breact(\.js|js)?\b|\bangular\b|\bvue(\.js)?\b|\bnext\.js\b", None, ()),
    ("Go", X0, r"\bgolang\b", None, ()),
    ("Spark", X0, r"\b(py)?spark\b", None, ()),
    ("Kafka", X0, r"\bkafka\b", None, ()),
    ("Airflow", X0, r"\bairflow\b", None, ()),
    ("Snowflake", X0, r"\bsnowflake\b", "Snowflake", ()),
    ("Terraform", X0, r"\bterraform\b", None, ()),
    ("NoSQL / MongoDB / Redis", X0, r"\bnosql\b|\bmongo(db)?\b|\bredis\b", None, ()),
]
_COMPILED = [(t, c, re.compile(p, re.I), k or t, tags) for t, c, p, k, tags in LEXICON]
TERM_CLUSTER = {t: c for t, c, *_ in LEXICON}
TERM_TAGS = {t: tags for t, _, _, _, tags in LEXICON}
TERM_PROFILE_KEY = {t: (k or t) for t, _, _, k, _ in LEXICON}


def find_terms(text: str) -> List[Tuple[str, str, int, int]]:
    """(term, matched text, start, end) for every lexicon term found in text (first match per term)."""
    out = []
    for term, _, rx, _, _ in _COMPILED:
        m = rx.search(text)
        if m:
            out.append((term, m.group(0), m.start(), m.end()))
    return out


# ============================================================================================ JD block parsing

class _Blocks(HTMLParser):
    """Splits LinkedIn-style description HTML into blocks; records whether a block is fully bold and any bold lead."""
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "ul", "ol", "br", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: List[Dict[str, Any]] = []
        self._buf: List[Tuple[str, bool]] = []
        self._bold = 0
        self._tag = "p"

    def _flush(self):
        text = "".join(t for t, _ in self._buf)
        norm = " ".join(text.split())
        if norm:
            bold = " ".join("".join(t for t, b in self._buf if b).split())
            lead = ""
            for t, b in self._buf:  # bold text before the first non-bold, non-space chunk
                if b:
                    lead += t
                elif t.strip():
                    break
            self.blocks.append({"text": norm, "tag": self._tag, "all_bold": bold == norm,
                                "bold_lead": " ".join(lead.split())})
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK:
            self._flush()
            if tag != "br":
                self._tag = tag
        if tag in ("strong", "b"):
            self._bold += 1

    def handle_endtag(self, tag):
        if tag in ("strong", "b"):
            self._bold = max(0, self._bold - 1)
        if tag in self.BLOCK:
            self._flush()
            self._tag = "p"

    def handle_data(self, data):
        self._buf.append((data, self._bold > 0))

    def close(self):
        super().close()
        self._flush()


_BULLET = re.compile(r"^\s*([-•*▪●◦·]|\d+[.)])\s+")


def text_blocks(text: str) -> List[Dict[str, Any]]:
    out = []
    for line in (text or "").splitlines():
        norm = " ".join(line.split())
        if not norm:
            continue
        is_item = bool(_BULLET.match(line))
        out.append({"text": _BULLET.sub("", norm) if is_item else norm, "tag": "li" if is_item else "p",
                    "all_bold": False, "bold_lead": ""})
    return out


_SENT = re.compile(r"(?<=[.!?•])\s+(?=[A-Z0-9•])")


def _split_degenerate(blocks: List[Dict[str, Any]], source: str) -> Tuple[List[Dict[str, Any]], str]:
    """A JD that arrives as < 3 blocks (no markup, no line breaks) is split into sentences so that one cue
    cannot decide the placement of the whole JD."""
    if len(blocks) >= 3:
        return blocks, source
    out = []
    for b in blocks:
        for sent in _SENT.split(b["text"]):
            if sent.strip():
                out.append({"text": sent.strip(), "tag": "p", "all_bold": False, "bold_lead": ""})
    return out, source + "+sentences"


def jd_blocks(html: Optional[str], text: Optional[str]) -> Tuple[List[Dict[str, Any]], str]:
    return _split_degenerate(*_jd_blocks(html, text))


def _jd_blocks(html: Optional[str], text: Optional[str]) -> Tuple[List[Dict[str, Any]], str]:
    if html and html.strip():
        p = _Blocks()
        p.feed(html)
        p.close()
        tb = text_blocks(text or "")
        if p.blocks and not (len(p.blocks) < 3 and len(tb) > len(p.blocks)):
            return p.blocks, "html"
        if tb:
            return tb, "text"
        return p.blocks, "html"
    return text_blocks(text or ""), "text"


# ---- section headings: conservative keyword classes. Order matters: PREFERRED, ROLE, INCIDENTAL, CORE, STACK.
_SEC_PREFERRED = re.compile(r"\b(preferred|nice[- ]to[- ]have|good[- ]to[- ]have|bonus|desirable|desired|added advantage|"
                            r"advantageous|plus points?|pluses|optional|secondary skills|would be (great|nice)|"
                            r"brownie points)\b|\ba plus\b")
_SEC_ROLE = re.compile(r"^(job |role |position )?(summary|overview|description|purpose|introduction)$|\babout (the|this) "
                       r"(role|job|position|opportunity)\b|^(the )?(role|opportunity|position)$|\brole (summary|overview)\b|"
                       r"\bjob (summary|overview|description)\b|\bposition (summary|overview)\b")
_SEC_INCIDENTAL = re.compile(r"^about\b|\bwho we are\b|\bcompany (overview|description|profile)\b|\bour (company|mission|story|"
                             r"values|culture|team)\b|\bbenefits?\b|\bperks\b|\bwhat we offer\b|\bwhy (join|work|you'?ll love)\b|"
                             r"\bequal (employment )?opportunit|\beeo\b|\bdiversity\b|\bcompensation\b|\bsalary\b|"
                             r"\bhow to apply\b|\b(application|hiring|interview|selection) process\b|^(work )?location\b|"
                             r"\bworking hours\b|\bshift\b|^job type\b|^employment type\b|\bnotice period\b|\bculture\b|"
                             r"\blife at\b|\bwe offer\b|\bwhat'?s in it for you\b|\bjoining\b")
_SEC_CORE = re.compile(r"responsibilit|\bwhat you('ll| will) (do|build|work on|own)\b|\byour (role|responsibilities|impact|day)\b|"
                       r"\bkey (duties|deliverables|accountabilities|result areas)\b|\bduties\b|\bday[- ]to[- ]day\b|"
                       r"\brequirements?\b|\brequired\b|\bqualifications?\b|\bmust[- ]haves?\b|\bmandatory\b|"
                       r"\bwhat you (bring|need|have|'ll need|will need)\b|\bwho you are\b|\bwhat we('re| are) looking for\b|"
                       r"\bskills?\b|\bexperience\b|\byou (have|will|bring)\b|\bminimum\b|\bbasic qualifications\b|"
                       r"\bcompetenc(y|ies)\b|\bexpertise\b|\bideal candidate\b|\beligibility\b|\bwhat you'll be doing\b|"
                       r"\bthe work\b|\bscope\b|\bkey areas\b|\bcandidate profile\b|\bprofile\b")
_SEC_STACK = re.compile(r"\b(tech(nology)? stack|our stack|tools|technologies|tech we use|tooling|environment)\b")


def section_class(heading: str) -> str:
    h = re.sub(r"[^a-z0-9/+&' -]", " ", heading.lower()).strip()
    h = " ".join(h.split())
    if _SEC_PREFERRED.search(h):
        return "PREFERRED"
    if _SEC_ROLE.search(h):
        return "ROLE"
    if _SEC_INCIDENTAL.search(h):
        return "INCIDENTAL"
    if _SEC_CORE.search(h):
        return "CORE"
    if _SEC_STACK.search(h):
        return "STACK"
    return "UNKNOWN"


# ---- line cues
_PREF_CUE = re.compile(r"\b(nice[- ]to[- ]have|good[- ]to[- ]have|preferred|preferably|bonus|desirable|desired|"
                       r"added advantage|an advantage|advantageous|would be (great|nice|a plus)|optional)\b|\b(is|are|as) a plus\b|"
                       r"\ba plus\b|\bplus\s*[.)]?\s*$", re.I)
_REQ_CUE = re.compile(r"\b(must[- ]have|must|required|requirement|mandatory|essential|"
                      r"strong (experience|knowledge|proficiency|understanding|background|expertise|skills?)|"
                      r"hands[- ]on (experience|expertise|knowledge)|proficien(t|cy)|expertise (in|with)|expert in|"
                      r"\d+\s*\+?\s*(years?|yrs)|responsible for|you will|you'll|will be (responsible|working)|"
                      r"experience (with|in|building|designing|developing|deploying)|knowledge of|understanding of|"
                      r"looking for (a|an|someone)\b.*\b(with|who|to))\b", re.I)
_RESP_VERB = re.compile(r"^(design|develop|build|implement|architect|deploy|create|own|lead|integrate|maintain|optimi[sz]e|"
                        r"write|drive|establish|engineer|ship|deliver|define|automate|evaluate|fine-tune|train|collaborate|"
                        r"partner|work with|contribute|research|prototype|productioni[sz]e|scale|monitor|set up)\b", re.I)
_INCID_CUE = re.compile(r"^(we are|we're|our (company|mission|team|clients?|platform|products?|customers?)|founded|"
                        r"headquartered|join (us|our)|at [A-Z][\w&.]*,? we|[A-Z][\w&.]* is (a|an|the) )", re.I)
_DEGREE = re.compile(r"\b(bachelor'?s?|master'?s?|degree|b\.? ?tech|m\.? ?tech|ph\.? ?d|graduate|graduation|"
                     r"post[- ]?graduate|mca|bca)\b|(?-i:\bB\.E\b|\bBE\b|\bM\.S\b|\bMS\b|\bM\.E\b)", re.I)
_LABEL = re.compile(r"^([A-Za-z][A-Za-z /&'()-]{1,45}):\s+(\S.*)$")


def _is_heading(b: Dict[str, Any], source: str) -> bool:
    t = b["text"]
    if b["tag"].startswith("h"):
        return True
    if b["tag"] == "li":
        return False
    if source == "html" and b["all_bold"] and len(t) <= 80 and not t.endswith("."):
        return not _LABEL.match(t)  # "Job Role: Full Stack AI Developer" is a label line, not a heading
    if len(t) <= 60 and t.endswith(":"):
        return True
    if source == "text" and len(t) <= 50 and not t.endswith(".") and section_class(t) not in ("UNKNOWN", "STACK"):
        return True
    return False


def place_blocks(blocks: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    """Give each non-heading block a placement. A heading sets the section until the next heading only."""
    section, heading = "PREAMBLE", ""
    out = []
    for i, b in enumerate(blocks):
        if _is_heading(b, source):
            section, heading = section_class(b["text"].rstrip(":")), b["text"]
            continue
        text, sec, how = b["text"], section, f"section:{section}"
        lab = _LABEL.match(text)
        if lab and len(lab.group(1)) <= 45:
            lsec = section_class(lab.group(1))
            if lsec != "UNKNOWN":  # inline label overrides for this block only ("Required Skills: Python, RAG")
                sec, how = lsec, f"label:{lsec}"
        if _DEGREE.search(text) and len(text) <= 300 and re.search(r"\b(in|of)\b", text):
            # A field of study ("B.Tech in CS, Statistics, Data Science") is not a capability requirement.
            out.append({"i": i, "text": text, "placement": "INCIDENTAL", "section": sec, "heading": heading,
                        "how": how + "+degree_line"})
            continue
        if sec == "CORE":
            placement = "PREFERRED" if _PREF_CUE.search(text) else "CORE"
            how += "+pref_cue" if placement == "PREFERRED" else ""
        elif sec == "PREFERRED":
            placement = "PREFERRED"
        elif sec == "INCIDENTAL":
            placement = "INCIDENTAL"
        else:  # ROLE / STACK / UNKNOWN / PREAMBLE: only explicit line cues decide
            if _PREF_CUE.search(text):
                placement, how = "PREFERRED", how + "+pref_cue"
            elif _REQ_CUE.search(text) or (b["tag"] == "li" and _RESP_VERB.match(text)) or (
                    sec == "ROLE" and _RESP_VERB.match(text)):
                placement, how = "CORE", how + "+req_cue"
            elif _INCID_CUE.match(text):
                placement, how = "INCIDENTAL", how + "+company_cue"
            else:
                placement = "UNKNOWN_PLACEMENT"
        out.append({"i": i, "text": text, "placement": placement, "section": sec, "heading": heading, "how": how})
    return out


# ================================================================================================ experience

_EXP_PATTERNS = [
    re.compile(r"(?P<min>\d{1,2}(?:\.\d)?)\s*(?:-|–|—|to)\s*(?P<max>\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", re.I),
    re.compile(r"(?P<min>\d{1,2}(?:\.\d)?)\s*\+\s*(?:years?|yrs?)", re.I),
    re.compile(r"(?:minimum|min\.?|at least|over|more than)\s*(?:of\s*)?(?P<min>\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", re.I),
    re.compile(r"(?P<min>\d{1,2}(?:\.\d)?)\s*(?:years?|yrs?)\b", re.I),
]
_EXP_CONTEXT = re.compile(r"experience|exp\b|expertise|background|working|industry|professional|hands[- ]on|relevant", re.I)
_EXP_NEG = re.compile(r"(company|business|founded|years? (old|ago|in business)|warranty|history|track record of \d)", re.I)


def extract_experience(placed: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Explicitly stated year requirements. The job's figure is the phrase with the largest stated minimum."""
    found = []
    for b in placed:
        if b["placement"] == "INCIDENTAL":
            continue
        text = b["text"]
        taken = []
        for rx in _EXP_PATTERNS:
            for m in rx.finditer(text):
                if any(s <= m.start() < e for s, e in taken):
                    continue
                window = text[max(0, m.start() - 60): m.end() + 60]
                if not _EXP_CONTEXT.search(window) or _EXP_NEG.search(window):
                    continue
                lo = float(m.group("min"))
                hi = float(m.group("max")) if "max" in m.groupdict() and m.group("max") else None
                if lo > 30 or (hi is not None and (hi > 40 or hi < lo)):
                    continue
                taken.append((m.start(), m.end()))
                found.append({"min": lo, "max": hi, "phrase": m.group(0), "evidence": snippet(text, m.start(), m.end()),
                              "placement": b["placement"]})
    if not found:
        return {"min_years": None, "max_years": None, "phrases": [], "status": "NOT_STATED"}
    best = sorted(found, key=lambda f: (-f["min"], f["max"] is None, -(f["max"] or 0)))[0]
    return {"min_years": best["min"], "max_years": best["max"], "phrases": found, "status": "STATED",
            "exact_phrase": best["phrase"], "evidence": best["evidence"], "placement": best["placement"]}


def exp_bucket(v: Optional[float]) -> str:
    if v is None:
        return "not stated"
    return "0-3" if v <= 3 else ("4-5" if v <= 5 else "6+")


# ================================================================================================= snippets

def snippet(text: str, start: int, end: int, width: int = 170) -> str:
    """Verbatim slice of `text` around [start, end); '…' marks a cut. Never paraphrases."""
    if len(text) <= width:
        return text
    pad = max(0, (width - (end - start)) // 2)
    s, e = max(0, start - pad), min(len(text), end + pad)
    return ("…" if s > 0 else "") + text[s:e] + ("…" if e < len(text) else "")


# ================================================================================================= dedupe

_VIEW_ID = re.compile(r"/jobs/view/(?:[^/?#]*?-)?(\d{6,})")


def identity_key(rec: Dict[str, Any]) -> Tuple[str, str]:
    """(key, method). LinkedIn id > /jobs/view/<n> in a URL > URL without query > company|title|location."""
    ext = (rec.get("external_id") or "").strip()
    if ext:
        return f"id:{ext}", "id"
    for url in (rec.get("job_url"), rec.get("apply_url")):
        if url:
            m = _VIEW_ID.search(url)
            if m:
                return f"id:{m.group(1)}", "link_view_id"
    for url in (rec.get("job_url"), rec.get("apply_url")):
        if url:
            return "url:" + url.split("?", 1)[0].split("#", 1)[0].rstrip("/").lower(), "link"
    parts = [" ".join((rec.get(k) or "").lower().split()) for k in ("company", "title", "location")]
    return "ctl:" + "|".join(parts), "company_title_location"


def _desc_html(raw: Dict[str, Any]) -> Optional[str]:
    for k in ("descriptionHtml", "description_html", "descriptionHTML", "jobDescriptionHtml"):
        if isinstance(raw.get(k), str) and raw[k].strip():
            return raw[k]
    return None


def load_population(path: Path) -> Dict[str, Any]:
    raws = normalize.read_export(path)
    recs = normalize.map_schema(raws, Path(path).name)
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    methods: Dict[str, str] = {}
    invalid = []
    for r in recs:
        if not (r.get("title") or "").strip():
            invalid.append({"index": r["index"], "problem": "no title"})
            continue
        key, how = identity_key(r)
        groups[key].append(r)
        methods.setdefault(key, how)
    jobs, variant_dupes = [], 0
    for key, members in groups.items():
        def richness(r):
            return (len(_desc_html(r["raw"]) or ""), len(r.get("description") or ""), -r["index"])
        rep = sorted(members, key=richness, reverse=True)[0]
        texts = {" ".join((m.get("description") or "").split()) for m in members}
        if len(texts) > 1:
            variant_dupes += 1
        jobs.append({"key": key, "method": methods[key], "rep": rep, "records": [m["index"] for m in members]})
    jobs.sort(key=lambda j: min(j["records"]))
    return {"raw_rows": len(raws), "records": recs, "jobs": jobs, "invalid": invalid,
            "duplicates": sum(len(j["records"]) - 1 for j in jobs), "description_variant_groups": variant_dupes,
            "key_methods": dict(Counter(j["method"] for j in jobs)), "input_sha256": normalize.file_sha256(Path(path))}


# ============================================================================================ candidate profile

def load_profile(path: Path = PROFILE_PATH) -> Dict[str, str]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    level = {}
    for k in doc["LIMITED"]:
        level[k] = "LIMITED"
    for k in doc["SUPPORTING"]:
        level[k] = "SUPPORTING"
    for k in doc["WORKING"]:
        level[k] = "WORKING"
    for k in doc["CORE"]:
        level[k] = "CORE"
    return level


def candidate_level(term: str, profile: Dict[str, str]) -> str:
    return profile.get(TERM_PROFILE_KEY.get(term, term), "NOT_ESTABLISHED")


# ================================================================================================== analysis

def analyse_job(title: str, html: Optional[str], text: Optional[str], profile: Dict[str, str]) -> Dict[str, Any]:
    blocks, source = jd_blocks(html, text)
    placed = place_blocks(blocks, source)
    # term -> {placement -> [evidence]}
    ev: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for b in placed:
        for term, matched, s, e in find_terms(b["text"]):
            ev[term][b["placement"]].append({"block": b["i"], "matched": matched, "snippet": snippet(b["text"], s, e),
                                             "heading": b["heading"], "how": b["how"]})
    title_terms = {t: m for t, m, _, _ in find_terms(title or "")}
    terms = {}
    for term, by in ev.items():
        primary = next(p for p in PLACEMENTS if by.get(p))
        terms[term] = {"cluster": TERM_CLUSTER[term], "placement": primary, "placements": sorted(by),
                       "evidence": by[primary][0], "all": {p: v for p, v in by.items()},
                       "in_title": term in title_terms, "candidate": candidate_level(term, profile)}
    title_only = sorted(t for t in title_terms if t not in terms)

    clusters = {}
    for c in CLUSTERS:
        ct = {t: v for t, v in terms.items() if v["cluster"] == c}
        counted = {t: v for t, v in ct.items() if not (c == "C7" and "ml_weak" in TERM_TAGS[t])}
        core = sorted(t for t, v in counted.items() if v["placement"] == "CORE")
        pref = sorted(t for t, v in counted.items() if v["placement"] == "PREFERRED")
        unk = sorted(t for t, v in counted.items() if v["placement"] == "UNKNOWN_PLACEMENT")
        core_blocks = {e["block"] for t in counted for e in counted[t]["all"].get("CORE", [])}
        weak_core = sorted(t for t, v in ct.items() if t not in counted and v["placement"] == "CORE")
        if len(core) >= 3 or len(core_blocks) >= 3:
            intensity = "HIGH"
        elif len(core) == 2 or len(core_blocks) == 2 or (len(core) == 1 and pref):
            intensity = "MODERATE"
        elif core or pref or weak_core:
            intensity = "LOW"
        elif unk or any(v["placement"] == "UNKNOWN_PLACEMENT" for v in ct.values()):
            intensity = "UNKNOWN"
        else:
            intensity = "NONE"
        clusters[c] = {"intensity": intensity, "core": core, "preferred": pref, "unknown": unk,
                       "core_blocks": len(core_blocks), "weak_core": weak_core,
                       "all_core": sorted(t for t, v in ct.items() if v["placement"] == "CORE"),
                       "all_preferred": sorted(t for t, v in ct.items() if v["placement"] == "PREFERRED")}

    ml = ml_levels(terms, clusters, title_terms)
    archetype, rule = primary_archetype(terms, clusters, ml)
    exp = extract_experience(placed)
    align = alignment(terms, archetype)
    return {"source": source, "blocks": len(blocks), "placed": placed, "terms": terms, "title_terms": title_terms,
            "title_only": title_only, "clusters": clusters, "ml": ml, "archetype": archetype, "archetype_rule": rule,
            "experience": exp, "alignment": align,
            "placement_counts": dict(Counter(b["placement"] for b in placed))}


def ml_levels(terms, clusters, title_terms) -> Dict[str, Any]:
    c7 = {t: v for t, v in terms.items() if v["cluster"] == "C7"}
    strong_core = sorted(t for t, v in c7.items() if "ml_strong" in TERM_TAGS[t] and v["placement"] == "CORE")
    strong_pref = sorted(t for t, v in c7.items() if "ml_strong" in TERM_TAGS[t] and v["placement"] == "PREFERRED")
    mention = bool(c7) or any(TERM_CLUSTER[t] == "C7" for t in title_terms)
    strong_core_blocks = {e["block"] for t in strong_core for e in c7[t]["all"].get("CORE", [])}
    # >= 2 concrete ML terms spread over >= 2 CORE blocks: one framework list ("PyTorch, TensorFlow") is not enough.
    substantive = len(strong_core) >= 2 and len(strong_core_blocks) >= 2
    llm_blocks = max(clusters[c]["core_blocks"] for c in ("C1", "C2", "C3", "C4"))
    dominant = substantive and clusters["C7"]["intensity"] == "HIGH" and clusters["C7"]["core_blocks"] > llm_blocks
    flags = {"ML_MENTION": mention, "ML_PREFERRED": bool(strong_pref) and not strong_core,
             "ML_REQUIRED": bool(strong_core), "ML_SUBSTANTIVE": substantive, "ML_DOMINANT": dominant}
    level = "NONE"
    for lv in ML_LEVELS[1:]:
        if flags[lv]:
            level = lv
    return {**flags, "level": level, "strong_core": strong_core, "strong_preferred": strong_pref,
            "strong_core_blocks": len(strong_core_blocks)}


def primary_archetype(terms, clusters, ml) -> Tuple[str, str]:
    r = {c: RANK[v["intensity"]] for c, v in clusters.items()}
    llm = max(r["C1"], r["C2"], r["C3"])
    has_core = any(v["placement"] == "CORE" and v["cluster"] != X0 for v in terms.values())
    ai_sdlc_core = any(v["placement"] == "CORE" and "ai_sdlc" in TERM_TAGS[t] for t, v in terms.items())
    ai_platform_core = any(v["placement"] == "CORE" and "ai_platform" in TERM_TAGS[t] for t, v in terms.items())
    if ml["ML_DOMINANT"] and llm <= 1:
        return ARCHETYPES[4], "R1 ML_DOMINANT and C1-C3 at most LOW"
    if ml["ML_SUBSTANTIVE"] and max(llm, r["C4"]) >= 2:
        return ARCHETYPES[3], "R2 ML_SUBSTANTIVE and C1-C4 at least MODERATE"
    if ml["ML_SUBSTANTIVE"] and r["C7"] >= 2:
        return ARCHETYPES[4], "R3 ML_SUBSTANTIVE, C7 at least MODERATE, C1-C4 at most LOW"
    blocks = {c: clusters[c]["core_blocks"] for c in clusters}
    llm_blocks = max(blocks["C1"], blocks["C2"], blocks["C3"])
    if r["C4"] >= 2 and blocks["C4"] >= max(2, llm_blocks):
        return ARCHETYPES[1], "R4 C4 at least MODERATE and in >=2 and at least as many CORE blocks as any of C1-C3"
    if ai_sdlc_core and r["C6"] >= 2 and blocks["C6"] >= max(2, llm_blocks):
        return ARCHETYPES[5], "R5 AI-specific C6 CORE term, C6 at least MODERATE and in >=2 and at least as many CORE blocks as C1-C3"
    if max(r["C2"], r["C3"]) >= 2:
        return ARCHETYPES[0], "R6 C2 or C3 at least MODERATE"
    if r["C1"] >= 2 and r["C5"] >= 2:
        return ARCHETYPES[2], "R7 C1 and C5 at least MODERATE"
    if r["C1"] >= 2:
        return ARCHETYPES[0], "R8 C1 at least MODERATE"
    if r["C5"] >= 2 and (ai_platform_core or max(r["C1"], r["C2"], r["C3"], r["C4"]) >= 1):
        return ARCHETYPES[6], "R9 C5 at least MODERATE with an AI-platform CORE term or some C1-C4 evidence"
    if has_core:
        return ARCHETYPES[7], "R10 some CORE evidence, no archetype rule met"
    return ARCHETYPES[8], "R11 no CORE evidence in C1-C7"


AI_CLUSTERS = ("C1", "C2", "C3", "C4", "C6")


def alignment(terms, archetype) -> Dict[str, Any]:
    core_req = {t: v for t, v in terms.items() if v["placement"] == "CORE"}
    by_level = defaultdict(list)
    for t, v in core_req.items():
        by_level[v["candidate"]].append(t)
    # Generic ML wording ("AI/ML", "machine learning", "NLP", "data science") is not a substantive requirement, so it
    # is reported as a generic mention and never as a CORE gap.
    generic = sorted(t for t in core_req if "ml_weak" in TERM_TAGS[t])
    core_gaps = sorted(t for t, v in core_req.items() if v["candidate"] not in ("CORE", "WORKING") and t not in generic)
    working_gaps = sorted(t for t, v in core_req.items() if v["candidate"] == "WORKING")
    preferred_only = sorted(t for t, v in terms.items() if v["placement"] == "PREFERRED" and v["candidate"] != "CORE")
    incidental_only = sorted(t for t, v in terms.items() if v["placement"] == "INCIDENTAL")
    hard = lambda ts: [t for t in ts if core_req[t]["candidate"] in ("LIMITED", "NOT_ESTABLISHED")]  # noqa: E731
    ai_core = [t for t, v in core_req.items() if v["cluster"] in AI_CLUSTERS]
    ai_present = [t for t in ai_core if core_req[t]["candidate"] == "CORE"]
    ai_working = [t for t in ai_core if core_req[t]["candidate"] == "WORKING"]
    ai_hard = hard(ai_core)
    stack_hard = hard([t for t, v in core_req.items() if v["cluster"] in ("C5", X0)])
    ml_hard = hard([t for t, v in core_req.items() if v["cluster"] == "C7" and t not in generic])
    if archetype == ARCHETYPES[8] or not core_req:
        a, why = "INSUFFICIENT_EVIDENCE", "no CORE requirement evidence"
    elif archetype == ARCHETYPES[4]:
        a, why = "LIMITED", "Traditional-ML-primary role"
    elif not ai_core:
        a, why = ("LIMITED", "no AI-cluster CORE requirement; stack / ML gaps") if (stack_hard or ml_hard) else (
            "INSUFFICIENT_EVIDENCE", "no AI-cluster CORE requirement")
    elif not ai_hard and not ml_hard and len(ai_working) <= 1 and len(stack_hard) <= 1:
        a, why = "DIRECT", "every AI-cluster CORE requirement is profile CORE/SUPPORTING (<=1 WORKING, <=1 stack gap)"
    elif not ai_hard and not ml_hard:
        a, why = "ADJACENT", "no hard AI gap; several WORKING-level or stack requirements"
    elif len(ai_present) > len(ai_hard) + len(ml_hard):
        a, why = "PARTIAL", "more AI-cluster CORE requirements present than hard gaps"
    else:
        a, why = "LIMITED", "hard gaps at least as many as present AI-cluster CORE requirements"
    return {"primary_capability_alignment": a, "rule": why,
            "candidate_core_present": sorted(by_level["CORE"]), "candidate_working_present": sorted(by_level["WORKING"]),
            "candidate_supporting_present": sorted(by_level["SUPPORTING"]), "candidate_limited": sorted(by_level["LIMITED"]),
            "candidate_not_established": sorted(by_level["NOT_ESTABLISHED"]),
            "core_gaps": core_gaps, "working_gaps": working_gaps, "preferred_only": preferred_only,
            "generic_ml_mentions": generic,
            "incidental_only": incidental_only}


# ================================================================================================ JobOps context

def jobops_context(input_path: Path, day: str, population: Dict[str, Any],
                   decisions_db: Optional[Path]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Runs the unchanged JobOps P10 pipeline in a throwaway state directory; returns context per survey key."""
    from jobops.sourcing import policy_version, run_source
    with tempfile.TemporaryDirectory(prefix="p11-jobops-") as tmp:
        res = run_source(Path(input_path), policy_version("0.2.6"), Path(tmp), day, None)
    by_rid = {j["job_id"]: j for j in res["run_jobs"]}
    rid_of_index = {m["index"]: m.get("requisition_id") for m in res["mapping"]}
    decided = _decisions(decisions_db)
    ctx, rid_sets = {}, {}
    for job in population["jobs"]:
        rids = sorted({rid_of_index.get(i) for i in job["records"]} - {None})
        rid_sets[job["key"]] = rids
        j = by_rid.get(rids[0]) if rids else None
        ctx[job["key"]] = {"requisition_id": ";".join(rids), "lane": j["lane"] if j else "",
                           "relevance": j["relevance"] if j else "", "tier": (j or {}).get("tier") or "",
                           "experience": (j or {}).get("experience") or "",
                           "decision": "; ".join(decided.get(r, "") for r in rids if decided.get(r)) or "none recorded"}
    all_rids = [r for rs in rid_sets.values() for r in rs]
    check = {"policy_version": res["policy_version"], "policy_sha256": res["policy_sha256"],
             "unique_requisitions": len({j["job_id"] for j in res["run_jobs"]}),
             "survey_jobs": len(population["jobs"]),
             "one_to_one": len(all_rids) == len(set(all_rids)) and all(len(r) == 1 for r in rid_sets.values()),
             "decisions_db": str(decisions_db) if decisions_db else None, "decisions_found": len(decided)}
    return ctx, check


def _decisions(db: Optional[Path]) -> Dict[str, str]:
    if not db:
        return {}
    conn = sqlite3.connect(f"file:{Path(db)}?mode=ro", uri=True)  # read-only
    try:
        rows = conn.execute("SELECT requisition_id, decision FROM review_decision ORDER BY rowid").fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        conn.close()
    return {r: d for r, d in rows}


# =================================================================================================== outputs

def _j(xs) -> str:
    return "; ".join(xs)


def survey(input_path: Path, day: str = "2026-10-01", with_jobops: bool = True,
           decisions_db: Optional[Path] = None, profile_path: Path = PROFILE_PATH) -> Dict[str, Any]:
    pop = load_population(Path(input_path))
    profile = load_profile(profile_path)
    ctx, check = (jobops_context(Path(input_path), day, pop, decisions_db) if with_jobops else ({}, None))
    jobs = []
    for job in pop["jobs"]:
        rec = job["rep"]
        a = analyse_job(rec.get("title") or "", _desc_html(rec["raw"]), rec.get("description"), profile)
        jobs.append({"key": job["key"], "job_id": job["key"].split(":", 1)[1] if job["key"].startswith("id:") else
                     "h" + hashlib.sha256(job["key"].encode()).hexdigest()[:12], "id_method": job["method"],
                     "records": job["records"], "title": rec.get("title"), "company": rec.get("company"),
                     "location": rec.get("location"),
                     "source": rec.get("source") or ("linkedin" if "linkedin.com" in (rec.get("job_url") or "") else ""),
                     "link": rec.get("job_url") or rec.get("apply_url") or "", "ctx": ctx.get(job["key"], {}), **a})
    return {"population": pop, "jobs": jobs, "jobops_check": check, "profile": profile, "input": str(input_path),
            "date": day}


JOB_COLUMNS = [
    "job_id", "jobops_requisition_id", "title", "company", "location", "source", "link", "existing_lane",
    "existing_relevance", "existing_tier", "primary_archetype", "archetype_rule",
    "c1_intensity", "c2_intensity", "c3_intensity", "c4_intensity", "c5_intensity", "c6_intensity", "c7_intensity",
    "c1_core_terms", "c1_preferred_terms", "c2_core_terms", "c2_preferred_terms", "c3_core_terms", "c3_preferred_terms",
    "c4_core_terms", "c4_preferred_terms", "c5_core_terms", "c5_preferred_terms", "c6_core_terms", "c6_preferred_terms",
    "c7_core_terms", "c7_preferred_terms", "x0_core_terms",
    "title_only_capabilities", "incidental_capabilities", "unknown_placement_capabilities", "ml_level",
    "min_years", "max_years", "experience_evidence",
    "candidate_core_present", "candidate_working_present", "candidate_supporting_present", "candidate_limited",
    "candidate_not_established", "primary_capability_alignment", "alignment_rule",
    "core_gaps", "working_gaps", "preferred_only_requirements", "evidence_snippets", "existing_jobops_decision",
    "jd_parse_source", "placement_counts", "duplicate_record_indexes",
]


def _fmt_years(v):
    return "" if v is None else (str(int(v)) if float(v).is_integer() else str(v))


def job_row(j: Dict[str, Any]) -> Dict[str, Any]:
    cl, al, ex, ctx = j["clusters"], j["alignment"], j["experience"], j["ctx"]
    row = {"job_id": j["job_id"], "jobops_requisition_id": ctx.get("requisition_id", ""), "title": j["title"],
           "company": j["company"], "location": j["location"], "source": j["source"], "link": j["link"],
           "existing_lane": ctx.get("lane", ""), "existing_relevance": ctx.get("relevance", ""),
           "existing_tier": ctx.get("tier", ""), "primary_archetype": j["archetype"], "archetype_rule": j["archetype_rule"]}
    for c in CLUSTERS:
        k = c.lower()
        row[f"{k}_intensity"] = cl[c]["intensity"]
        row[f"{k}_core_terms"] = _j(cl[c]["all_core"])
        row[f"{k}_preferred_terms"] = _j(cl[c]["all_preferred"])
    row["x0_core_terms"] = _j(sorted(t for t, v in j["terms"].items() if v["cluster"] == X0 and v["placement"] == "CORE"))
    row["title_only_capabilities"] = _j(j["title_only"])
    row["incidental_capabilities"] = _j(sorted(t for t, v in j["terms"].items() if v["placement"] == "INCIDENTAL"))
    row["unknown_placement_capabilities"] = _j(sorted(t for t, v in j["terms"].items()
                                                      if v["placement"] == "UNKNOWN_PLACEMENT"))
    row["ml_level"] = j["ml"]["level"]
    row["min_years"], row["max_years"] = _fmt_years(ex["min_years"]), _fmt_years(ex["max_years"])
    row["experience_evidence"] = f'"{ex["evidence"]}" ({ex["placement"]})' if ex["status"] == "STATED" else "NOT_STATED"
    for k in ("candidate_core_present", "candidate_working_present", "candidate_supporting_present", "candidate_limited",
              "candidate_not_established", "core_gaps", "working_gaps"):
        row[k] = _j(al[k])
    row["preferred_only_requirements"] = _j(al["preferred_only"])
    row["primary_capability_alignment"] = al["primary_capability_alignment"]
    row["alignment_rule"] = al["rule"]
    snips = []
    for c in CLUSTERS:
        cand = [t for t in cl[c]["all_core"]] or [t for t in cl[c]["all_preferred"]]
        if cand:
            t = cand[0]
            snips.append(f'{c} {t}: "{j["terms"][t]["evidence"]["snippet"]}"')
    row["evidence_snippets"] = " | ".join(snips) or "evidence_unavailable"
    row["existing_jobops_decision"] = ctx.get("decision", "not run")
    row["jd_parse_source"] = j["source"]
    row["placement_counts"] = json.dumps(j["placement_counts"], sort_keys=True)
    row["duplicate_record_indexes"] = " ".join(str(i) for i in j["records"])
    return row


def _csv(rows: List[List[Any]]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def capability_rows(jobs) -> List[List[Any]]:
    rows = [["job_id", "term", "cluster", "job_placement", "all_placements", "in_title", "candidate_level",
             "matched_text", "section_heading", "placement_rule", "evidence_snippet"]]
    for j in jobs:
        for t in sorted(j["terms"]):
            v = j["terms"][t]
            e = v["evidence"]
            rows.append([j["job_id"], t, v["cluster"], v["placement"], "|".join(v["placements"]), v["in_title"],
                         v["candidate"], e["matched"], e["heading"], e["how"], e["snippet"]])
        for t in j["title_only"]:
            rows.append([j["job_id"], t, TERM_CLUSTER[t], "TITLE_ONLY", "TITLE_ONLY", True,
                         "", j["title_terms"][t], "(title)", "title", j["title"]])
    return rows


def gap_rows(jobs, profile) -> List[List[Any]]:
    rows = [["job_id", "primary_archetype", "term", "cluster", "jd_placement", "candidate_level", "gap_class"]]
    for j in jobs:
        for t, v in sorted(j["terms"].items()):
            if v["placement"] == "CORE" and v["candidate"] == "CORE":
                continue
            cls = {"CORE": "GENERIC_ML_MENTION" if "ml_weak" in TERM_TAGS[t] else (
                       "CORE_GAP" if v["candidate"] != "WORKING" else "WORKING_GAP"),
                   "PREFERRED": "PREFERRED_ONLY", "INCIDENTAL": "INCIDENTAL_ONLY",
                   "UNKNOWN_PLACEMENT": "UNKNOWN_PLACEMENT"}[v["placement"]]
            if v["placement"] != "CORE" and v["candidate"] == "CORE":
                continue
            rows.append([j["job_id"], j["archetype"], t, v["cluster"], v["placement"], v["candidate"], cls])
    return rows


def experience_rows(jobs) -> List[List[Any]]:
    rows = [["job_id", "primary_archetype", "status", "min_years", "max_years", "exact_phrase", "evidence", "placement",
             "all_phrases"]]
    for j in jobs:
        e = j["experience"]
        rows.append([j["job_id"], j["archetype"], e["status"], _fmt_years(e["min_years"]), _fmt_years(e["max_years"]),
                     e.get("exact_phrase", ""), e.get("evidence", ""), e.get("placement", ""),
                     " || ".join(p["phrase"] for p in e["phrases"])])
    return rows


# --------------------------------------------------------------------------------------------- metrics

def metrics(s: Dict[str, Any]) -> Dict[str, Any]:
    jobs, pop = s["jobs"], s["population"]
    n = len(jobs)
    arche = Counter(j["archetype"] for j in jobs)
    cl_any, cl_core, cl_pref, cl_unk, cl_title = Counter(), Counter(), Counter(), Counter(), Counter()
    intensity = {c: Counter() for c in CLUSTERS}
    for j in jobs:
        for c in CLUSTERS:
            ct = [v for v in j["terms"].values() if v["cluster"] == c]
            places = {p for v in ct for p in v["placements"]}
            if places & {"CORE", "PREFERRED", "UNKNOWN_PLACEMENT"}:
                cl_any[c] += 1
            if "CORE" in places:
                cl_core[c] += 1
            if "PREFERRED" in places:
                cl_pref[c] += 1
            if "UNKNOWN_PLACEMENT" in places:
                cl_unk[c] += 1
            if any(TERM_CLUSTER[t] == c for t in j["title_terms"]):
                cl_title[c] += 1
            intensity[c][j["clusters"][c]["intensity"]] += 1
    term_counts = {}
    for t, c, *_ in LEXICON:
        rows = [j for j in jobs if t in j["terms"] or t in j["title_terms"]]
        if not rows:
            continue
        pl = Counter(j["terms"][t]["placement"] for j in rows if t in j["terms"])
        term_counts[t] = {"cluster": c, "postings": len(rows), "CORE": pl["CORE"], "PREFERRED": pl["PREFERRED"],
                          "UNKNOWN_PLACEMENT": pl["UNKNOWN_PLACEMENT"], "INCIDENTAL": pl["INCIDENTAL"],
                          "title_only": sum(1 for j in rows if t in j["title_only"]),
                          "title_any": sum(1 for j in rows if t in j["title_terms"]),
                          "candidate_level": candidate_level(t, s["profile"])}
    ml = {lv: sum(1 for j in jobs if j["ml"][lv]) for lv in ML_LEVELS[1:]}
    ml["ML_LEVEL_HIGHEST"] = dict(Counter(j["ml"]["level"] for j in jobs))
    ml["TRADITIONAL_ML_PRIMARY"] = arche[ARCHETYPES[4]]
    ml["HYBRID_LLM_ML"] = arche[ARCHETYPES[3]]

    def subst(j, c):
        if c == "C7":  # concrete ML only: generic "AI/ML" wording never forms an "LLM + Traditional ML" combination
            return j["ml"]["ML_REQUIRED"] or j["ml"]["ML_PREFERRED"]
        return j["clusters"][c]["intensity"] in ("HIGH", "MODERATE", "LOW")

    combos = {
        "RAG + Agentic": ("C2", "C3"), "RAG + Evaluation": ("C2", "C4"), "LLM + Backend": ("C1", "C5"),
        "Agentic + Backend": ("C3", "C5"), "LLM + Traditional ML": ("C1", "C7"), "RAG + Traditional ML": ("C2", "C7"),
        "Evaluation + Agentic": ("C4", "C3"), "Evaluation + AI-SDLC": ("C4", "C6"),
    }
    combo_counts = {k: sum(1 for j in jobs if subst(j, a) and subst(j, b)) for k, (a, b) in combos.items()}
    combo_counts["Evaluation + Reliability (C4 HIGH)"] = sum(1 for j in jobs if j["clusters"]["C4"]["intensity"] == "HIGH")
    combo_counts["RAG + Agentic + Evaluation"] = sum(1 for j in jobs if subst(j, "C2") and subst(j, "C3") and subst(j, "C4"))
    exp_by = {}
    for a in ARCHETYPES:
        mins = [j["experience"]["min_years"] for j in jobs if j["archetype"] == a and j["experience"]["min_years"] is not None]
        total = arche[a]
        exp_by[a] = {"postings": total, "stating_years": len(mins),
                     "median_min_years": statistics.median(mins) if mins else None,
                     "0-3": sum(1 for v in mins if v <= 3), "4-5": sum(1 for v in mins if 3 < v <= 5),
                     "6+": sum(1 for v in mins if v > 5)}
    all_mins = [j["experience"]["min_years"] for j in jobs if j["experience"]["min_years"] is not None]
    exp_by["ALL"] = {"postings": n, "stating_years": len(all_mins),
                     "median_min_years": statistics.median(all_mins) if all_mins else None,
                     "0-3": sum(1 for v in all_mins if v <= 3), "4-5": sum(1 for v in all_mins if 3 < v <= 5),
                     "6+": sum(1 for v in all_mins if v > 5)}
    align = Counter(j["alignment"]["primary_capability_alignment"] for j in jobs)
    level_req = {lv: Counter() for lv in CANDIDATE_LEVELS}
    for j in jobs:
        for t, v in j["terms"].items():
            if v["placement"] == "CORE":
                level_req[v["candidate"]][t] += 1
    gap_core = Counter(t for j in jobs for t in j["alignment"]["core_gaps"])
    gap_work = Counter(t for j in jobs for t in j["alignment"]["working_gaps"])
    sub_any = lambda c: sum(1 for j in jobs if j["clusters"][c]["intensity"] in ("HIGH", "MODERATE", "LOW"))  # noqa: E731
    return {
        "raw_jobs": pop["raw_rows"], "unique_jobs": n, "duplicates": pop["duplicates"],
        "invalid_records": len(pop["invalid"]), "description_variant_groups": pop["description_variant_groups"],
        "identity_methods": pop["key_methods"], "input_sha256": pop["input_sha256"],
        "archetype_counts": {a: arche[a] for a in ARCHETYPES},
        "cluster_any_counts": {c: cl_any[c] for c in CLUSTERS}, "cluster_core_counts": {c: cl_core[c] for c in CLUSTERS},
        "cluster_preferred_counts": {c: cl_pref[c] for c in CLUSTERS},
        "cluster_unknown_counts": {c: cl_unk[c] for c in CLUSTERS},
        "cluster_title_counts": {c: cl_title[c] for c in CLUSTERS},
        "cluster_substantive_requirement_counts": {c: sub_any(c) for c in CLUSTERS},
        "intensity_distribution": {c: {i: intensity[c][i] for i in INTENSITIES} for c in CLUSTERS},
        "term_counts": term_counts, "ml": ml,
        "ml_substantive_count": ml["ML_SUBSTANTIVE"], "ml_primary_count": ml["TRADITIONAL_ML_PRIMARY"],
        "llm_primary_count": sum(arche[a] for a in ARCHETYPES[:3]),
        "role_combinations": combo_counts, "experience_by_archetype": exp_by,
        "experience_counts": {b: sum(1 for j in jobs if exp_bucket(j["experience"]["min_years"]) == b)
                              for b in ("0-3", "4-5", "6+", "not stated")},
        "alignment_counts": {a: align[a] for a in ALIGNMENTS},
        "candidate_core_alignment_counts": dict(level_req["CORE"].most_common()),
        "candidate_working_alignment_counts": dict(level_req["WORKING"].most_common()),
        "candidate_supporting_alignment_counts": dict(level_req["SUPPORTING"].most_common()),
        "candidate_limited_alignment_counts": dict(level_req["LIMITED"].most_common()),
        "candidate_not_established_alignment_counts": dict(level_req["NOT_ESTABLISHED"].most_common()),
        "candidate_gap_counts": {"CORE_GAP": dict(gap_core.most_common()), "WORKING_GAP": dict(gap_work.most_common())},
        "placement_block_totals": dict(sum((Counter(j["placement_counts"]) for j in jobs), Counter())),
        "jd_parse_source": dict(Counter(j["source"] for j in jobs)),
        "jobops_check": s["jobops_check"],
        "jobops_lanes": dict(Counter(j["ctx"].get("lane", "") for j in jobs)) if s["jobops_check"] else None,
    }


# ----------------------------------------------------------------------------------------------- summary

def _pct(k, n):
    return f"{k / n:.0%}" if n else "n/a"


def render_summary(s: Dict[str, Any], m: Dict[str, Any]) -> str:
    n = m["unique_jobs"]
    L = []
    a = m["archetype_counts"]
    sub = m["cluster_substantive_requirement_counts"]
    L += [f"# P11 Role-Capability Survey — {Path(s['input']).name}", "",
          "> This survey is descriptive and does not modify JobOps eligibility, relevance, lane, queue, compensation,",
          "> employer, geography, or policy. Keyword presence is evidence that a JD *asks* for something; it is not",
          "> evidence of the candidate's expertise. No score, ranking or fit percentage is produced.", "",
          f"- Input SHA-256: `{m['input_sha256']}`",
          f"- JobOps context: policy {m['jobops_check']['policy_version'] if m['jobops_check'] else 'not run'}"
          + (f" (SHA `{m['jobops_check']['policy_sha256']}`), run in a temporary state; never filters the population"
             if m["jobops_check"] else ""), ""]
    # 1 executive summary
    ml = m["ml"]
    L += ["## 1. Executive summary", "",
          f"In this {n}-job sample (all unique jobs, every lane):",
          f"- **{_pct(sub['C2'], n)}** of roles carry RAG/retrieval as a CORE or PREFERRED requirement "
          f"({sub['C2']}), **{_pct(sub['C3'], n)}** agentic ({sub['C3']}), **{_pct(sub['C1'], n)}** LLM application "
          f"({sub['C1']}), **{_pct(sub['C4'], n)}** evaluation/reliability ({sub['C4']}).",
          f"- **{_pct(ml['TRADITIONAL_ML_PRIMARY'], n)}** are Traditional-ML-primary ({ml['TRADITIONAL_ML_PRIMARY']}); "
          f"{ml['HYBRID_LLM_ML']} are hybrid LLM + ML; {ml['ML_MENTION']} mention ML vocabulary at all "
          f"(mention ≠ requirement).",
          f"- Primary archetypes: " + "; ".join(f"{k} {v}" for k, v in sorted(a.items(), key=lambda kv: -kv[1]) if v) + ".",
          f"- Stated experience: {m['experience_by_archetype']['ALL']['stating_years']} of {n} postings state years; "
          f"median minimum {m['experience_by_archetype']['ALL']['median_min_years']}.",
          f"- Descriptive capability alignment (not a fit score): "
          + "; ".join(f"{k} {v}" for k, v in m["alignment_counts"].items()) + ".", ""]
    # 2 population
    L += ["## 2. Population", "",
          "| raw rows | unique jobs | duplicate records | invalid records | duplicate groups with differing JD text |",
          "|---:|---:|---:|---:|---:|",
          f"| {m['raw_jobs']} | {n} | {m['duplicates']} | {m['invalid_records']} | {m['description_variant_groups']} |", "",
          f"Identity: {json.dumps(m['identity_methods'])}. Representative record per job = the one with the longest "
          "description (HTML, then text), ties by first position. JD parsed from: "
          f"{json.dumps(m['jd_parse_source'])}.", ""]
    if m["jobops_check"]:
        jc = m["jobops_check"]
        L += [f"JobOps cross-check: engine unique requisitions {jc['unique_requisitions']}, survey jobs "
              f"{jc['survey_jobs']}, one-to-one mapping: {jc['one_to_one']}. Lanes (context only): "
              f"{json.dumps(m['jobops_lanes'], sort_keys=True)}. Human decisions found: {jc['decisions_found']}.", ""]
    # 3 archetypes
    L += ["## 3. Primary archetype distribution", "", "| archetype | jobs | share |", "|---|---:|---:|"]
    L += [f"| {k} | {v} | {_pct(v, n)} |" for k, v in a.items()] + [""]
    # 4 cluster demand
    L += ["## 4. Capability cluster demand (postings)", "",
          "| cluster | any substantive mention | CORE | PREFERRED | UNKNOWN_PLACEMENT | in title |",
          "|---|---:|---:|---:|---:|---:|"]
    L += [f"| {c} {CLUSTERS[c]} | {m['cluster_any_counts'][c]} | {m['cluster_core_counts'][c]} | "
          f"{m['cluster_preferred_counts'][c]} | {m['cluster_unknown_counts'][c]} | {m['cluster_title_counts'][c]} |"
          for c in CLUSTERS]
    L += ["", "A posting counts once per column; a cluster can be CORE and PREFERRED in the same posting. "
          "\"Any substantive mention\" = CORE, PREFERRED or UNKNOWN_PLACEMENT (title and incidental excluded).", ""]
    # 5 intensity
    L += ["## 5. Capability intensity distribution", "", "| cluster | " + " | ".join(INTENSITIES) + " |",
          "|---|" + "---:|" * len(INTENSITIES)]
    L += [f"| {c} {CLUSTERS[c]} | " + " | ".join(str(m["intensity_distribution"][c][i]) for i in INTENSITIES) + " |"
          for c in CLUSTERS] + [""]
    # 6 top technologies
    top = sorted(m["term_counts"].items(), key=lambda kv: (-kv[1]["postings"], kv[0]))[:45]
    L += ["## 6. Top requested technologies / concepts", "",
          "| term | cluster | postings | CORE | PREFERRED | UNKNOWN | INCIDENTAL | title-only | candidate level |",
          "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    L += [f"| {t} | {v['cluster']} | {v['postings']} | {v['CORE']} | {v['PREFERRED']} | {v['UNKNOWN_PLACEMENT']} | "
          f"{v['INCIDENTAL']} | {v['title_only']} | {v['candidate_level']} |" for t, v in top] + [""]
    # 7 traditional ML
    L += ["## 7. Traditional ML analysis", "",
          "| ML_MENTION | ML_PREFERRED | ML_REQUIRED | ML_SUBSTANTIVE | ML_DOMINANT | Traditional-ML primary | Hybrid LLM + ML |",
          "|---:|---:|---:|---:|---:|---:|---:|",
          f"| {ml['ML_MENTION']} | {ml['ML_PREFERRED']} | {ml['ML_REQUIRED']} | {ml['ML_SUBSTANTIVE']} | "
          f"{ml['ML_DOMINANT']} | {ml['TRADITIONAL_ML_PRIMARY']} | {ml['HYBRID_LLM_ML']} |", "",
          "Columns are cumulative flags (a posting can be several). ML_MENTION includes generic wording "
          "(\"machine learning\", \"AI/ML\", \"NLP\", \"data science\"), which never makes a role ML-heavy on its own. "
          "ML_REQUIRED = ≥1 concrete ML technique/tool in a CORE block; ML_SUBSTANTIVE = ≥2; ML_DOMINANT = "
          "ML_SUBSTANTIVE, C7 HIGH and more CORE blocks on ML than on any of C1–C4.", ""]
    hi = Counter(m["ml"]["ML_LEVEL_HIGHEST"])
    L += ["Highest level reached per posting: " + ", ".join(f"{k} {hi.get(k, 0)}" for k in ML_LEVELS) + ".", ""]
    # 8 LLM/RAG/agentic/eval
    L += ["## 8. LLM / RAG / Agentic / Evaluation prevalence", "", "| cluster | CORE or PREFERRED | HIGH | MODERATE | share (CORE/PREF) |",
          "|---|---:|---:|---:|---:|"]
    for c in ("C1", "C2", "C3", "C4"):
        d = m["intensity_distribution"][c]
        L.append(f"| {c} {CLUSTERS[c]} | {sub[c]} | {d['HIGH']} | {d['MODERATE']} | {_pct(sub[c], n)} |")
    L += [""]
    # 9 combos
    L += ["## 9. Role combinations (both clusters CORE or PREFERRED; C7 = a concrete ML technique, not generic wording)", "",
          "| combination | postings |", "|---|---:|"]
    L += [f"| {k} | {v} |" for k, v in m["role_combinations"].items()] + [""]
    # 10 experience
    L += ["## 10. Experience demand by archetype", "",
          "| archetype | postings | stating years | median min years | 0–3 | 4–5 | 6+ |", "|---|---:|---:|---:|---:|---:|---:|"]
    for k, v in m["experience_by_archetype"].items():
        if v["postings"]:
            L.append(f"| {k} | {v['postings']} | {v['stating_years']} | {v['median_min_years'] if v['median_min_years'] is not None else '—'} "
                     f"| {v['0-3']} | {v['4-5']} | {v['6+']} |")
    L += ["", "Years are only what the JD states (\"3+ years\", \"3-5 years\", \"minimum 4 years\"); never inferred "
          "from titles. A posting's figure is its largest stated minimum.", ""]
    # 11 alignment
    L += ["## 11. Candidate capability alignment (descriptive; not a fit score)", "",
          "| PRIMARY_CAPABILITY_ALIGNMENT | postings |", "|---|---:|"]
    L += [f"| {k} | {v} |" for k, v in m["alignment_counts"].items()]
    L += ["", "CORE requirements seen across postings, by candidate-profile level (distinct terms; posting counts):", ""]
    for lv, key in (("CORE", "candidate_core_alignment_counts"), ("WORKING", "candidate_working_alignment_counts"),
                    ("SUPPORTING", "candidate_supporting_alignment_counts"), ("LIMITED", "candidate_limited_alignment_counts")):
        items = list(m[key].items())[:12]
        L.append(f"- **{lv}:** " + (", ".join(f"{t} ({c})" for t, c in items) or "none"))
    L += [""]
    # 12-14 gaps
    cg = list(m["candidate_gap_counts"]["CORE_GAP"].items())
    L += ["## 12. Most common CORE gaps", "",
          "A CORE gap = a term in a CORE block of the JD whose candidate-profile level is not CORE or WORKING "
          "(SUPPORTING / LIMITED / NOT_ESTABLISHED). Preferred and incidental mentions are never gaps.", "",
          "| term | cluster | postings (CORE) | candidate level |", "|---|---|---:|---|"]
    L += [f"| {t} | {TERM_CLUSTER[t]} | {c} | {candidate_level(t, s['profile'])} |" for t, c in cg[:25]] + [""]
    wg = list(m["candidate_gap_counts"]["WORKING_GAP"].items())
    L += ["## 13. Most common WORKING / developing areas requested as CORE", "", "| term | postings (CORE) |", "|---|---:|"]
    L += [f"| {t} | {c} |" for t, c in wg] or ["| none | 0 |"]
    L += [""]
    ne = sorted(((t, v) for t, v in m["term_counts"].items() if v["candidate_level"] == "NOT_ESTABLISHED"),
                key=lambda kv: (-(kv[1]["CORE"] + kv[1]["PREFERRED"]), kv[0]))[:20]
    L += ["## 14. Frequently requested technologies not established in the profile", "",
          "| term | cluster | CORE | PREFERRED | total postings |", "|---|---|---:|---:|---:|"]
    L += [f"| {t} | {v['cluster']} | {v['CORE']} | {v['PREFERRED']} | {v['postings']} |" for t, v in ne] + [""]
    st = list(m["candidate_core_alignment_counts"].items())[:15]
    L += ["## 15. Candidate strengths the market repeatedly asks for (CORE in JD and CORE in profile)", "",
          "| term | postings (CORE) |", "|---|---:|"]
    L += [f"| {t} | {c} |" for t, c in st] + [""]
    # 16 conclusion
    L += ["## 16. Market composition (descriptive)", "",
          f"In this {n}-job sample, {_pct(sub['C2'], n)} of roles contain RAG/retrieval as a CORE or PREFERRED "
          f"requirement, {_pct(sub['C3'], n)} contain agentic AI, {_pct(sub['C1'], n)} LLM application engineering, "
          f"{_pct(sub['C4'], n)} evaluation/reliability and {_pct(sub['C5'], n)} backend/platform engineering; "
          f"{_pct(ml['TRADITIONAL_ML_PRIMARY'], n)} are Traditional-ML-primary and "
          f"{_pct(ml['HYBRID_LLM_ML'], n)} hybrid LLM + ML. {_pct(a[ARCHETYPES[8]] + a[ARCHETYPES[7]], n)} could not "
          "be given an AI archetype from substantive evidence (generic / keyword-only).", "",
          "This is a description of the sourced market, not a recommendation and not a JobOps input.", ""]
    return "\n".join(L).rstrip() + "\n"


def write_outputs(s: Dict[str, Any], out: Path) -> Dict[str, Any]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    m = metrics(s)
    rows = [job_row(j) for j in s["jobs"]]
    (out / "jobs.csv").write_text(_csv([JOB_COLUMNS] + [[r[c] for c in JOB_COLUMNS] for r in rows]), encoding="utf-8")
    (out / "capabilities.csv").write_text(_csv(capability_rows(s["jobs"])), encoding="utf-8")
    (out / "gaps.csv").write_text(_csv(gap_rows(s["jobs"], s["profile"])), encoding="utf-8")
    (out / "experience.csv").write_text(_csv(experience_rows(s["jobs"])), encoding="utf-8")
    arch = [["primary_archetype", "jobs", "share", "stating_years", "median_min_years", "0-3", "4-5", "6+"]]
    for a in ARCHETYPES:
        e = m["experience_by_archetype"][a]
        arch.append([a, m["archetype_counts"][a], _pct(m["archetype_counts"][a], m["unique_jobs"]), e["stating_years"],
                     e["median_min_years"] if e["median_min_years"] is not None else "", e["0-3"], e["4-5"], e["6+"]])
    (out / "archetypes.csv").write_text(_csv(arch), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(m, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "summary.md").write_text(render_summary(s, m), encoding="utf-8")
    return m


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--date", default="2026-10-01", help="date for the throwaway JobOps context run")
    ap.add_argument("--no-jobops", action="store_true", help="skip the JobOps context columns")
    ap.add_argument("--decisions-db", type=Path, default=None, help="read-only JobOps state for human decisions")
    ap.add_argument("--profile", type=Path, default=PROFILE_PATH)
    args = ap.parse_args(argv)
    if not args.input.is_file():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2
    s = survey(args.input, args.date, not args.no_jobops, args.decisions_db, args.profile)
    m = write_outputs(s, args.out)
    print(json.dumps({k: m[k] for k in ("raw_jobs", "unique_jobs", "duplicates", "archetype_counts",
                                        "ml_substantive_count", "ml_primary_count", "alignment_counts")},
                     indent=1, ensure_ascii=False))
    print(f"Summary: {args.out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
