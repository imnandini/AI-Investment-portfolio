from app.schemas.research import Answer, Evidence


def grounded_answer(evidence: list[Evidence]) -> Answer:
    # Evidence is displayed as quotations, never interpreted as instructions or tool calls.
    # There is no generative model configured. This intentionally makes no inferred claims.
    if not evidence:
        return Answer(status="insufficient_evidence", answer="Insufficient evidence in your uploaded documents for this question.", evidence=[],
            limitations=["Upload a relevant text PDF or narrow the question. Company evidence comes from your document library; portfolio context uses saved holdings."], activities=["Searched your document library", "No supporting passages found"])
    excerpts = [f"[{i}] {item.title}, page {item.page}:\n{item.text}" for i, item in enumerate(evidence, 1)]
    return Answer(status="supported", answer="Relevant source passages:\n\n" + "\n\n".join(excerpts), evidence=evidence,
        limitations=["Extractive results quote uploaded documents. They are not independently verified or synthesized conclusions.",
            "Sources may refer to different periods or contain conflicting claims. Check the cited pages before comparing figures."],
        activities=["Searched your document library", "Ranked matching passages", "Attached document and page citations"])
