RUBRIC_BLOCK = """
RUBRIC BASLANGIC

CLARITY:
- 1.0 = Soru net, tek anlamli, kolay anlasilir.
- 0.7 = Genel olarak anlasilir, bir miktar belirsizlik var.
- 0.4 = Coklu yoruma acik veya karmasik.
- 0.0 = Anlamsiz ya da parse edilemez.

SPECIFICITY:
- 1.0 = Somut, dar kapsamli, olculebilir.
- 0.7 = Makul derecede spesifik.
- 0.4 = Fazla genel.
- 0.0 = Belirsiz/uygulanamaz.

IS_OFF_TOPIC:
- true  = Soru sistem kapsamiyla ilgisiz.
- false = Soru kapsam dahilinde.

COMPLETENESS:
- 1.0 = Sorudaki tum talepler eksiksiz karsilanmis.
- 0.7 = Buyuk kismi karsilanmis, az sayida eksik var.
- 0.4 = Kismi cevap var, kritik eksikler var.
- 0.0 = Cevap ilgisiz/bos.

COHERENCE:
- 1.0 = Akici, mantikli, celiskisiz.
- 0.7 = Genelde tutarli, kucuk kopukluklar var.
- 0.4 = Belirgin kopukluk/celiski var.
- 0.0 = Tutarsiz/anlamsiz.

HELPFULNESS:
- 1.0 = Kullanici hedefini dogrudan cozer, uygulanabilir.
- 0.7 = Faydali ama eksik/yuzysel.
- 0.4 = Kismen faydali.
- 0.0 = Faydasiz/alakasiz.

IS_DEFLECTION:
- true  = "bilmiyorum", "yardimci olamam" gibi savusturma var ve bilgi yok.
- false = Soruyu cevaplama niyeti ve icerik var.

HALLUCINATION / CLAIM ANALIZI:
- supported: Baglam claim'i destekliyor.
- contradiction: Baglamla celisiyor.
- missing_info: Baglamda claim'i dogrulayacak bilgi yok.
- fabricated: Baglamda hic olmayan detay uydurulmus.

RUBRIC BITIS
""".strip()


STAGE_1_SYSTEM_PROMPT = """
Sen bir RAG cevap kalitesi degerlendirme uzmanisin.
Asagidaki rubric'e kesinlikle bagli kalarak degerlendir.
Her metrik icin kisa ama acik muhakeme yaz.
Skor verirken anchor degerleri (1.0 / 0.7 / 0.4 / 0.0) referans al.
Claim analizinde her onemli factual iddiayi kontrol et.
""".strip()

# ── Stage 2 strict JSON schema (OpenAI Structured Outputs) ──────────────
STAGE_2_JSON_SCHEMA = {
    "name": "evaluation_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "clarity":                {"type": "number"},
            "specificity":            {"type": "number"},
            "is_off_topic":           {"type": "boolean"},
            "completeness":           {"type": "number"},
            "coherence":              {"type": "number"},
            "helpfulness":            {"type": "number"},
            "is_deflection":          {"type": "boolean"},
            "overall_score":          {"type": "number"},
            "evaluation_confidence":  {"type": "number"},
            "reasoning_summary":      {"type": "string"},
            "disagreement_claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "context_quote":      {"type": "string"},
                        "context_quote_type": {"type": "string", "enum": ["instruction", "factual claim"]},
                        "answer_quote":       {"type": "string"},
                        "reasoning":          {"type": "string"},
                        "disagreement_type":  {"type": "string", "enum": ["agreement", "unsupported claim", "confirmed contradiction"]}
                    },
                    "required": ["context_quote", "context_quote_type", "answer_quote", "reasoning", "disagreement_type"],
                    "additionalProperties": False
                }
            }
        },
        "required": [
            "clarity", "specificity", "is_off_topic", "completeness",
            "coherence", "helpfulness", "is_deflection", "overall_score",
            "evaluation_confidence", "reasoning_summary", "disagreement_claims"
        ],
        "additionalProperties": False
    }
}

_EXAMPLE_JSON = """{
  "clarity": 0.7,
  "specificity": 0.7,
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
Sen bir JSON donusturucu yardimcisisin.
Verilen muhakeme metnini asagidaki ornek formatta tek bir gecerli JSON objesi olarak don.
Sadece JSON don, baska hicbir sey yazma.

Float degerler 0.0 ile 1.0 arasinda olmali.
Boolean degerler true/false olmali.
disagreement_claims bos array [] olabilir veya obje iceren array olabilir.

ORNEK CIKTI:
{_EXAMPLE_JSON}
""".strip()

STAGE_2_REPAIR_SYSTEM_PROMPT = f"""
Sen bir JSON duzeltme yardimcisisin.
Verilen hatali/eksik JSON ciktisini asagidaki formata uygun, tek bir gecerli JSON objesine donustur.
Sadece JSON don, baska hicbir sey yazma.

Kurallar:
- Float alanlar 0.0-1.0 araliginda olsun.
- Boolean alanlar true/false olsun.
- Eksik alanlari orijinal muhakemeden cikararak doldur.
- disagreement_claims her zaman array olsun (bos olabilir).

BEKLENEN FORMAT:
{_EXAMPLE_JSON}
""".strip()


def build_stage_1_user_prompt(question: str, answer: str, contexts: list[str]) -> str:
    context_block = "\n".join([f"- {item}" for item in contexts]) if contexts else "- (bos)"
    return (
        f"{RUBRIC_BLOCK}\n\n"
        "Soru:\n"
        f"{question}\n\n"
        "Cevap:\n"
        f"{answer}\n\n"
        "Baglamlar:\n"
        f"{context_block}\n\n"
        "Her metrik icin muhakeme yaz, bir skor oner ve desteklenmeyen claimleri belirt."
    )


def build_stage_2_user_prompt(stage_1_reasoning: str) -> str:
    return (
        "Asagidaki muhakemeyi parse et ve yalnizca JSON don.\n"
        "Baska hicbir aciklama, markdown veya ek metin yazma.\n\n"
        "MUHAKEME:\n"
        f"{stage_1_reasoning}"
    )


def build_stage_2_repair_user_prompt(
    stage_2_output: str,
    stage_1_reasoning: str,
    validation_errors: str | None = None,
) -> str:
    error_block = ""
    if validation_errors:
        error_block = f"\nDOGRULAMA HATALARI:\n{validation_errors}\n"
    return (
        "Asagida ilk donusum denemesi ve orijinal muhakeme var.\n"
        "Bu donusum denemesi hatali. Duzelt ve tek bir gecerli JSON objesi don.\n"
        "Baska hicbir aciklama, markdown veya ek metin yazma.\n"
        f"{error_block}\n"
        "ILK DENEME CIKTISI:\n"
        f"{stage_2_output}\n\n"
        "ORIJINAL MUHAKEME:\n"
        f"{stage_1_reasoning}"
    )
