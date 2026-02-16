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

STAGE_2_SYSTEM_PROMPT = """
Verilen muhakeme metnini yalnizca gecerli JSON olarak donustur.
JSON alanlari:
clarity, specificity, is_off_topic, completeness, coherence, helpfulness,
is_deflection, overall_score, evaluation_confidence, reasoning_summary,
disagreement_claims.
Alan tipleri:
- clarity/specificity/completeness/coherence/helpfulness/overall_score/evaluation_confidence: 0.0-1.0 float
- is_off_topic/is_deflection: boolean
- reasoning_summary: string
- disagreement_claims: array
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
        "Asagidaki muhakemeyi parse et ve yalnizca JSON don:\n\n"
        f"{stage_1_reasoning}"
    )
