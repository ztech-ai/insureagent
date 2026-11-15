"""Deterministic local baseline for synthetic Alpha evaluation, not an LLM substitute."""

import re


def redact(text: str) -> str:
    text = re.sub(r"(?<![0-9])[0-9]{17}[0-9Xx](?![0-9])", "[证件已隐藏]", text)
    text = re.sub(r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])", "[电话已隐藏]", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱已隐藏]", text)
    # Spelled digits and broader semantic PII require a validated DLP model before external calls.
    return text


def extract(text: str) -> dict:
    names = list(
        dict.fromkeys(re.findall(r"(?:客户|姓名[：:])([\u4e00-\u9fff]{2,4})(?=[，,。\s]|$)", text))
    )
    facts = []
    for match in re.finditer(r"[^。！？\n]+", text):
        sentence = match.group().strip()
        if any(
            word in sentence for word in ("保障", "保险", "预算", "家庭", "孩子", "联系", "养老")
        ):
            facts.append(
                {
                    "field": "contact_note",
                    "value": redact(sentence),
                    "evidence": sentence,
                    "start": match.start() + len(match.group()) - len(match.group().lstrip()),
                    "end": match.end() - len(match.group()) + len(match.group().rstrip()),
                }
            )
    return {
        "person_names": names,
        "redacted_text": redact(text),
        "candidates": facts[:100],
        "processor": "local-rules-v1",
        "requires_review": True,
    }
