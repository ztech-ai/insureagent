"""Deterministic local baseline for synthetic Alpha evaluation, not an LLM substitute."""

import re


def redact(text: str) -> str:
    text = re.sub(r"(?<![0-9])[0-9]{17}[0-9Xx](?![0-9])", "[证件已隐藏]", text)
    text = re.sub(r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])", "[电话已隐藏]", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱已隐藏]", text)
    # Spelled digits and broader semantic PII require a validated DLP model before external calls.
    return text


# Conservative baseline: unknown/rare family names remain for manual entry.
# Do not turn generic phrases such as 客户数据 / 客户资料 into identity candidates.
FAMILY_NAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐"
    "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平"
    "黄和穆萧尹姚邵汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董"
    "梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡"
    "凌霍万卢莫房裘缪干解应宗丁宣邓单杭洪包左石崔龚程嵇邢裴陆荣翁荀"
    "羊惠甄曲封芮储靳段富巫乌焦巴牧山谷车侯全秋宫宁仇祖武符刘景詹龙"
    "叶幸司黎薄白蒲从鄂索赖卓蔺屠蒙池乔阴胥苍闻党翟谭贡劳姬申扶堵冉"
    "宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎连习艾鱼"
    "容向古易廖耿满匡文寇广禄阙东欧利师巩聂晁勾敖融冷辛简饶曾沙养"
)


def extract(text: str) -> dict:
    names = list(
        dict.fromkeys(re.findall(r"(?:客户|姓名[：:])([\u4e00-\u9fff]{2,4})(?=[，,。\s]|$)", text))
    )
    names = [name for name in names if name[0] in FAMILY_NAMES]
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
