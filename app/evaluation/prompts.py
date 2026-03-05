from app.config import settings
from app.evaluation.prompt_utils import truncate_contexts, truncate_text

RUBRIC_BLOCK = """
RUBRIC START

CLARITY (of the ANSWER):
- 1.0 = Answer is clear, well-structured, easy to understand, no contradictions.
- 0.7 = Generally understandable, minor ambiguity or slight redundancy.
- 0.4 = Convoluted, hard to follow, contains contradictory statements, or uses excessive hedging.
- 0.0 = Nonsensical, unparseable, or riddled with contradictions.

IS_OFF_TOPIC:
- true  = The ANSWER does not address the question at all; it discusses an entirely unrelated topic.
- false = The ANSWER makes a genuine attempt to address the question, even if partially or incorrectly.

COHERENCE:
- 1.0 = Fluent, logical, no contradictions.
- 0.7 = Generally coherent, minor disconnects.
- 0.4 = Notable disconnects or contradictions.
- 0.0 = Incoherent / nonsensical.

HELPFULNESS:
- 1.0 = Directly solves the user's goal, actionable.
- 0.7 = Helpful but incomplete or superficial.
- 0.4 = Partially helpful.
- 0.0 = Useless / irrelevant.

IS_DEFLECTION:
- true  = Contains deflection ("I don't know", "I can't help") with no substantive information.
- false = Genuine attempt to answer with content.

RUBRIC END
""".strip()


STAGE_1_SYSTEM_PROMPT = """
You are an expert RAG answer quality evaluator.
Strictly follow the rubric below when scoring.
For each metric, write brief but clear reasoning.
Use the anchor values (1.0 / 0.7 / 0.4 / 0.0) as reference points when scoring.
Do NOT perform claim-level fact-checking — that is handled by a separate analytical pipeline.
Focus only on the rubric dimensions listed.
""".strip()

# ── Stage 2 strict JSON schema (OpenAI Structured Outputs) ──────────────
STAGE_2_JSON_SCHEMA = {
    "name": "evaluation_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "clarity": {"type": "number"},
            "is_off_topic": {"type": "boolean"},
            "completeness": {"type": "number"},
            "coherence": {"type": "number"},
            "helpfulness": {"type": "number"},
            "is_deflection": {"type": "boolean"},
            "overall_score": {"type": "number"},
            "evaluation_confidence": {"type": "number"},
            "reasoning_summary": {"type": "string"},
            "disagreement_claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "context_quote": {"type": "string"},
                        "context_quote_type": {
                            "type": "string",
                            "enum": ["instruction", "factual claim"],
                        },
                        "answer_quote": {"type": "string"},
                        "reasoning": {"type": "string"},
                        "disagreement_type": {
                            "type": "string",
                            "enum": [
                                "agreement",
                                "unsupported claim",
                                "confirmed contradiction",
                            ],
                        },
                    },
                    "required": [
                        "context_quote",
                        "context_quote_type",
                        "answer_quote",
                        "reasoning",
                        "disagreement_type",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "clarity",
            "is_off_topic",
            "completeness",
            "coherence",
            "helpfulness",
            "is_deflection",
            "overall_score",
            "evaluation_confidence",
            "reasoning_summary",
            "disagreement_claims",
        ],
        "additionalProperties": False,
    },
}

_EXAMPLE_JSON = """{
  "clarity": 0.7,
  "is_off_topic": false,
  "completeness": 0.4,
  "coherence": 0.7,
  "helpfulness": 0.4,
  "is_deflection": false,
  "overall_score": 0.55,
  "evaluation_confidence": 0.8,
  "reasoning_summary": "Cevap kismen dogru; completeness eksik, bir fabricated claim var.",
  "disagreement_claims": [
    {
      "context_quote": "Paris is the capital of France.",
      "context_quote_type": "factual claim",
      "answer_quote": "Berlin is the capital of France.",
      "reasoning": "Cevap Berlin diyor ama baglam Paris diyor.",
      "disagreement_type": "confirmed contradiction"
    }
  ]
}"""

STAGE_2_SYSTEM_PROMPT = f"""
You are a JSON converter assistant.
Convert the given reasoning text into a single valid JSON object in the format shown below.
Output ONLY JSON, nothing else.

Float values must be between 0.0 and 1.0.
Boolean values must be true/false.
disagreement_claims can be an empty array [] or contain objects.

EXAMPLE OUTPUT:
{_EXAMPLE_JSON}
""".strip()

STAGE_2_REPAIR_SYSTEM_PROMPT = f"""
You are a JSON repair assistant.
Convert the given malformed/incomplete JSON output into a single valid JSON object matching the format below.
Output ONLY JSON, nothing else.

Rules:
- Float fields must be in [0.0, 1.0].
- Boolean fields must be true/false.
- Fill in missing fields by extracting from the original reasoning.
- disagreement_claims must always be an array (may be empty).

EXPECTED FORMAT:
{_EXAMPLE_JSON}
""".strip()


def build_stage_1_user_prompt(question: str, answer: str, contexts: list[str]) -> str:
    question = truncate_text(question, settings.max_question_chars, label="question")
    answer = truncate_text(answer, settings.max_answer_chars, label="answer")
    contexts = truncate_contexts(
        contexts,
        max_total_chars=settings.max_context_total_chars,
        max_single_chars=settings.max_single_context_chars,
    )
    context_block = (
        "\n".join([f"[{i}] {c}" for i, c in enumerate(contexts)])
        if contexts
        else "(empty)"
    )
    return (
        f"{RUBRIC_BLOCK}\n\n"
        "Question:\n"
        f"{question}\n\n"
        "Answer:\n"
        f"{answer}\n\n"
        "Contexts:\n"
        f"{context_block}\n\n"
        "For each rubric metric, write brief reasoning and propose a score."
    )


def build_stage_2_user_prompt(stage_1_reasoning: str) -> str:
    return (
        "Parse the reasoning below and return ONLY JSON.\n"
        "Do not write any explanation, markdown, or extra text.\n\n"
        "REASONING:\n"
        f"{stage_1_reasoning}"
    )


def build_stage_2_repair_user_prompt(
    stage_2_output: str,
    stage_1_reasoning: str,
    validation_errors: str | None = None,
) -> str:
    error_block = ""
    if validation_errors:
        error_block = f"\nVALIDATION ERRORS:\n{validation_errors}\n"
    return (
        "Below is the first conversion attempt and the original reasoning.\n"
        "The conversion attempt is invalid. Fix it and return a single valid JSON object.\n"
        "Do not write any explanation, markdown, or extra text.\n"
        f"{error_block}\n"
        "FIRST ATTEMPT OUTPUT:\n"
        f"{stage_2_output}\n\n"
        "ORIGINAL REASONING:\n"
        f"{stage_1_reasoning}"
    )


# ── RAG Metrics: Hallucination (Dedicated Rubric Judge) ───────────────

HALLUCINATION_STAGE_1_SYSTEM_PROMPT = """
You are a hallucination detection evaluator.

Task:
1. Extract atomic factual claims from the ANSWER.
2. For each claim, compare against CONTEXT PASSAGES.
3. Label each claim with one disagreement_type:
   - "agreement"                -> context supports the claim.
   - "unsupported claim"        -> context does not provide evidence either way.
   - "confirmed contradiction"  -> context explicitly conflicts with the claim.

Borderline / paraphrase guidance:
- If the answer paraphrases, summarises, or reasonably infers a fact FROM the context,
  label it "agreement". Exact wording is NOT required.
  Example: context says "typical use cases include session caching, pub/sub, leaderboards"
           answer says "Redis is mostly used as a cache" → "agreement" (summary of context).
- Reserve "unsupported claim" for statements the context truly says NOTHING about.
- Reserve "confirmed contradiction" ONLY when the context explicitly states the opposite.

Rules:
- Use short direct quotes from both answer and context when possible.
- If no matching context evidence exists, set context_quote to "" and context_quote_type to "factual claim".
- context_quote_type must be either "instruction" or "factual claim".
- Keep reasoning concise (1-2 sentences per item).
- Output plain text reasoning only; do not output JSON.
""".strip()

HALLUCINATION_STAGE_2_JSON_SCHEMA = {
    "name": "hallucination_rubric_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "disagreement_claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "context_quote": {"type": "string"},
                        "context_quote_type": {
                            "type": "string",
                            "enum": ["instruction", "factual claim"],
                        },
                        "answer_quote": {"type": "string"},
                        "reasoning": {"type": "string"},
                        "disagreement_type": {
                            "type": "string",
                            "enum": [
                                "agreement",
                                "unsupported claim",
                                "confirmed contradiction",
                            ],
                        },
                    },
                    "required": [
                        "context_quote",
                        "context_quote_type",
                        "answer_quote",
                        "reasoning",
                        "disagreement_type",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["disagreement_claims"],
        "additionalProperties": False,
    },
}

HALLUCINATION_STAGE_2_SYSTEM_PROMPT = """
You convert evaluator reasoning into strict JSON.
Return ONLY a single JSON object with one key: disagreement_claims.
Use this structure for each item:
- context_quote: string
- context_quote_type: "instruction" | "factual claim"
- answer_quote: string
- reasoning: string
- disagreement_type: "agreement" | "unsupported claim" | "confirmed contradiction"

If no claims are found, return {"disagreement_claims": []}.
""".strip()


def build_hallucination_stage_1_user_prompt(answer: str, contexts: list[str]) -> str:
    answer = truncate_text(answer, settings.max_answer_chars, label="answer")
    contexts = truncate_contexts(
        contexts,
        max_total_chars=settings.max_context_total_chars,
        max_single_chars=settings.max_single_context_chars,
    )
    context_block = (
        "\n".join([f"[{i}] {c}" for i, c in enumerate(contexts)])
        if contexts
        else "(empty)"
    )
    return (
        "ANSWER:\n"
        f"{answer}\n\n"
        "CONTEXT PASSAGES:\n"
        f"{context_block}\n\n"
        "Extract and evaluate factual claims with disagreement_type labels."
    )


def build_hallucination_stage_2_user_prompt(stage_1_reasoning: str) -> str:
    return (
        "Convert the following hallucination-evaluation reasoning into strict JSON.\n"
        "Output ONLY JSON.\n\n"
        "REASONING:\n"
        f"{stage_1_reasoning}"
    )


# ── RAG Metrics: Citation Check ─────────────────────────────────────────

CITATION_CHECK_SYSTEM_PROMPT = """
You are a citation verification expert. Your task: verify source citations in the given answer against the provided context passages.

Context passages are numbered starting from [0]. Common citation formats: [1], [2], [Source 1], (see context 1), etc.

For each citation found in the answer:
1. Determine which context passage index (0-based) the citation claims to reference.
2. Check if that context index actually exists in the provided passages.
3. If the index exists, verify whether that passage contains the information being cited.

Verdict rules:
- "correct": Citation references a valid context index AND that passage supports the cited claim.
- "incorrect": Citation references a non-existent context index (e.g., [Source 99] when only 3 contexts exist), OR the referenced passage does not contain the cited information.

IMPORTANT: A citation like [Source 99] or [15] is INCORRECT if there are fewer than 100 or 16 context passages, respectively. Always check that the referenced index is within bounds.

If no citations exist, return an empty array.
Output ONLY JSON, nothing else.
""".strip()

CITATION_CHECK_JSON_SCHEMA = {
    "name": "citation_check_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "citation_text": {"type": "string"},
                        "referenced_context_index": {"type": "number"},
                        "verdict": {
                            "type": "string",
                            "enum": ["correct", "incorrect"],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": [
                        "citation_text",
                        "referenced_context_index",
                        "verdict",
                        "reason",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["citations"],
        "additionalProperties": False,
    },
}


def build_citation_check_user_prompt(answer: str, contexts: list[str]) -> str:
    answer = truncate_text(answer, settings.max_answer_chars, label="answer")
    contexts = truncate_contexts(
        contexts,
        max_total_chars=settings.max_context_total_chars,
        max_single_chars=settings.max_single_context_chars,
    )
    context_block = (
        "\n".join([f"[{i}] {c}" for i, c in enumerate(contexts)])
        if contexts
        else "(empty)"
    )
    return (
        "ANSWER:\n"
        f"{answer}\n\n"
        f"CONTEXT PASSAGES ({len(contexts)} total, indexed 0 to {len(contexts) - 1}):\n"
        f"{context_block}\n\n"
        "Find and verify all source citations in the answer.\n"
        "Any citation referencing an index outside 0-{max_idx} is INCORRECT.\n"
        "If no citations exist, return an empty array. Output ONLY JSON."
    ).replace("{max_idx}", str(len(contexts) - 1))


# ── RAG Metrics: Answer Relevancy (RAGAS Reverse-Question Method) ────────

ANSWER_RELEVANCY_SYSTEM_PROMPT = """
You are an answer relevancy evaluation expert. Your task:
1. Decompose the given answer into individual statements (atomic factual or informational claims).
2. For each statement, determine whether it is RELEVANT to the user's question.

Rules:
- Extract ALL distinct statements from the answer. A statement is a single piece of information or claim.
- A statement is "relevant" if it directly addresses, partially addresses, or provides useful context for the question.
- A statement is "not_relevant" if it is off-topic, tangential, or does not help answer the question.
- Filler phrases like "Sure, here is the answer" are not_relevant.
- Provide a brief reason for each classification.
- Output ONLY JSON, nothing else.

Example:
Question: "What is the capital of France?"
Answer: "The capital of France is Paris. Paris has a population of about 2.1 million. The Eiffel Tower was built in 1889. Italy is known for pizza."

Output:
{
  "statements": [
    {"statement": "The capital of France is Paris", "relevant": true, "reason": "Directly answers the question"},
    {"statement": "Paris has a population of about 2.1 million", "relevant": true, "reason": "Provides relevant context about the capital city"},
    {"statement": "The Eiffel Tower was built in 1889", "relevant": true, "reason": "Provides context about a landmark in the capital"},
    {"statement": "Italy is known for pizza", "relevant": false, "reason": "Completely off-topic, unrelated to the question"}
  ]
}
""".strip()

ANSWER_RELEVANCY_JSON_SCHEMA = {
    "name": "answer_relevancy_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "statements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "statement": {"type": "string"},
                        "relevant": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                    "required": ["statement", "relevant", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["statements"],
        "additionalProperties": False,
    },
}


def build_answer_relevancy_user_prompt(question: str, answer: str) -> str:
    question = truncate_text(question, settings.max_question_chars, label="question")
    answer = truncate_text(answer, settings.max_answer_chars, label="answer")
    return (
        "QUESTION:\n"
        f"{question}\n\n"
        "ANSWER:\n"
        f"{answer}\n\n"
        "Decompose the answer into statements and classify each as relevant or not_relevant to the question.\n"
        "Output ONLY JSON."
    )


# ── RAG Metrics: Completeness (Key-Point Extraction + Verification) ──────

COMPLETENESS_SYSTEM_PROMPT = """
You are a completeness evaluation expert. Your task:
1. Extract the key information requirements (key points) from the question and contexts.
2. For each key point, determine whether the answer adequately covers it.

Rules:
- Extract EXACTLY the number of key points specified in the user prompt. No more, no less.
- Each key point should be a distinct, verifiable information requirement.
- A key point is "covered" if the answer addresses it with relevant, substantive information.
- A key point is "not_covered" if the answer ignores it or provides no relevant information.
- A key point is "partially_covered" if the answer touches on it but lacks important details.
- Output ONLY JSON, nothing else.
""".strip()

COMPLETENESS_JSON_SCHEMA = {
    "name": "completeness_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "key_points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "point": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["covered", "partially_covered", "not_covered"],
                        },
                        "evidence": {"type": "string"},
                    },
                    "required": ["point", "status", "evidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["key_points"],
        "additionalProperties": False,
    },
}


def _key_point_count(question: str) -> int:
    """Deterministic key point count based on question word count.

    Fixes consistency issue: the LLM no longer decides how many key
    points to extract, so the denominator stays stable across runs.
    """
    word_count = len(question.split())
    if word_count <= 15:
        return 3
    elif word_count <= 40:
        return 4
    else:
        return 5


def build_completeness_user_prompt(
    question: str, answer: str, contexts: list[str]
) -> str:
    question = truncate_text(question, settings.max_question_chars, label="question")
    answer = truncate_text(answer, settings.max_answer_chars, label="answer")
    contexts = truncate_contexts(
        contexts,
        max_total_chars=settings.max_context_total_chars,
        max_single_chars=settings.max_single_context_chars,
    )
    context_block = (
        "\n".join([f"[{i}] {c}" for i, c in enumerate(contexts)])
        if contexts
        else "(empty)"
    )
    n = _key_point_count(question)
    return (
        "QUESTION:\n"
        f"{question}\n\n"
        "ANSWER:\n"
        f"{answer}\n\n"
        "CONTEXT PASSAGES:\n"
        f"{context_block}\n\n"
        f"Extract EXACTLY {n} key points from the question and verify which ones the answer covers.\n"
        "Output ONLY JSON."
    )


# ── RAG Metrics: Context Precision ──────────────────────────────────────

CONTEXT_PRECISION_SYSTEM_PROMPT = """
You are a context relevance evaluation expert. Your task: evaluate whether each provided context passage is useful for answering the given question.

Rules:
- For each context passage, determine if it contains information that helps answer the question.
- A context is "relevant" if it directly provides, partially provides, or gives useful background for answering the question.
- A context is "not_relevant" if it is off-topic, contains no useful information for the question, or is entirely unrelated.
- Provide a brief reason for each classification.
- Output ONLY JSON, nothing else.

Example:
Question: "What is the capital of France?"
Contexts:
[0] "France is a country in Western Europe. Its capital and largest city is Paris."
[1] "The Sahara Desert is the largest hot desert in the world."

Output:
{
  "contexts": [
    {"index": 0, "relevant": true, "reason": "Directly states the capital of France is Paris"},
    {"index": 1, "relevant": false, "reason": "About the Sahara Desert, unrelated to the question"}
  ]
}
""".strip()

CONTEXT_PRECISION_JSON_SCHEMA = {
    "name": "context_precision_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "contexts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "number"},
                        "relevant": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                    "required": ["index", "relevant", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["contexts"],
        "additionalProperties": False,
    },
}


def build_context_precision_user_prompt(question: str, contexts: list[str]) -> str:
    question = truncate_text(question, settings.max_question_chars, label="question")
    contexts = truncate_contexts(
        contexts,
        max_total_chars=settings.max_context_total_chars,
        max_single_chars=settings.max_single_context_chars,
    )
    context_block = (
        "\n".join([f"[{i}] {c}" for i, c in enumerate(contexts)])
        if contexts
        else "(empty)"
    )
    return (
        "QUESTION:\n"
        f"{question}\n\n"
        f"CONTEXT PASSAGES ({len(contexts)} total):\n"
        f"{context_block}\n\n"
        "For each context passage, determine if it is relevant to answering the question.\n"
        "Output ONLY JSON."
    )


# ── RAG Metrics: Context Recall ─────────────────────────────────────────

CONTEXT_RECALL_SYSTEM_PROMPT = """
You are a context recall evaluation expert. Your task: determine how well the provided context passages cover the information needed to answer the question.

You will receive EITHER a ground truth answer OR just the question. Your job differs based on what is provided:

**If ground truth is provided:**
1. Decompose the ground truth answer into individual factual statements.
2. For each statement, check if any context passage contains this information.

**If only a question is provided (no ground truth):**
1. Identify the key information needs required to fully answer the question (2-6 needs).
2. For each need, check if any context passage provides this information.

Verdicts:
- "found": The information is present in at least one context passage.
- "not_found": None of the context passages contain this information.

Provide a brief reason for each verdict.
Output ONLY JSON, nothing else.
""".strip()

CONTEXT_RECALL_JSON_SCHEMA = {
    "name": "context_recall_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "statement": {"type": "string"},
                        "verdict": {
                            "type": "string",
                            "enum": ["found", "not_found"],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["statement", "verdict", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
}


def build_context_recall_user_prompt(
    question: str,
    contexts: list[str],
    ground_truth: str | None = None,
) -> str:
    question = truncate_text(question, settings.max_question_chars, label="question")
    contexts = truncate_contexts(
        contexts,
        max_total_chars=settings.max_context_total_chars,
        max_single_chars=settings.max_single_context_chars,
    )
    if ground_truth:
        ground_truth = truncate_text(
            ground_truth, settings.max_ground_truth_chars, label="ground_truth"
        )
    context_block = (
        "\n".join([f"[{i}] {c}" for i, c in enumerate(contexts)])
        if contexts
        else "(empty)"
    )

    if ground_truth:
        return (
            "GROUND TRUTH ANSWER:\n"
            f"{ground_truth}\n\n"
            f"CONTEXT PASSAGES ({len(contexts)} total):\n"
            f"{context_block}\n\n"
            "Decompose the ground truth into factual statements and check if each is found in the contexts.\n"
            "Output ONLY JSON."
        )
    else:
        return (
            "QUESTION:\n"
            f"{question}\n\n"
            f"CONTEXT PASSAGES ({len(contexts)} total):\n"
            f"{context_block}\n\n"
            "Identify the key information needs to answer the question and check if each is found in the contexts.\n"
            "Output ONLY JSON."
        )
