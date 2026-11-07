from functools import lru_cache


@lru_cache(maxsize=1)
def _model(path):
    from sentence_transformers import CrossEncoder
    return CrossEncoder(path, local_files_only=True, trust_remote_code=False)


def rerank(query, evidence, model_path=""):
    if not model_path or not evidence:
        return evidence
    scores = _model(model_path).predict([(query, item.text) for item in evidence])
    return [item for _, item in sorted(zip(scores, evidence), key=lambda pair: -float(pair[0]))]
