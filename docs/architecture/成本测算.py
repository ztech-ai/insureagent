#!/usr/bin/env python3
"""按照《容量与成本估算》的假设，计算每月模型费用与语音负载。

金额为规划计算，不是服务商报价。基础设施预算通过命令行显式传入。
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, ROUND_HALF_UP


D = Decimal
MILLION = D("1000000")


def decimal_arg(value: str) -> Decimal:
    try:
        number = D(value)
    except Exception as exc:
        raise argparse.ArgumentTypeError("请输入数字") from exc
    if not number.is_finite() or number < 0:
        raise argparse.ArgumentTypeError("请输入非负有限数字")
    return number


def money(value: Decimal) -> str:
    return str(value.quantize(D("0.01"), rounding=ROUND_HALF_UP))


def count(value: Decimal) -> str:
    return str(value.quantize(D("0.01"), rounding=ROUND_HALF_UP))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=["baseline", "allowance"], default="baseline",
                        help="baseline 为平均使用；allowance 为 30 天周期全部使用满额")
    parser.add_argument("--paid", type=decimal_arg, default=D("50000"), help="付费用户数")
    parser.add_argument("--free", type=decimal_arg, default=D("100000"), help="免费用户数")
    parser.add_argument("--paid-dau", type=decimal_arg, default=D("0.35"))
    parser.add_argument("--free-dau", type=decimal_arg, default=D("0.10"))
    parser.add_argument("--paid-records", type=decimal_arg, default=D("8"), help="付费日活每日语音数")
    parser.add_argument("--free-records", type=decimal_arg, default=D("3"), help="免费日活每日语音数")
    parser.add_argument("--days", type=decimal_arg, default=D("30"), help="语音录制统计天数；建议和问答仍按整月次数计算")
    parser.add_argument("--seconds", type=decimal_arg, default=D("90"), help="平均录音秒数")
    parser.add_argument("--insights", type=decimal_arg, default=D("100"), help="每付费用户每月建议次数")
    parser.add_argument("--paid-questions", type=decimal_arg, default=D("30"))
    parser.add_argument("--free-questions", type=decimal_arg, default=D("10"))
    parser.add_argument("--asr-price", type=decimal_arg, default=D("0.00024"), help="每秒 ASR 单价")
    parser.add_argument("--flash-input-price", type=decimal_arg, default=D("0.15"))
    parser.add_argument("--flash-output-price", type=decimal_arg, default=D("1.5"))
    parser.add_argument("--plus-input-price", type=decimal_arg, default=D("0.8"))
    parser.add_argument("--plus-output-price", type=decimal_arg, default=D("2"))
    parser.add_argument("--embedding-price", type=decimal_arg, default=D("0.5"))
    parser.add_argument("--buffer", type=decimal_arg, default=D("0.10"), help="模型预算浮动比例")
    parser.add_argument("--infra-min", type=decimal_arg, help="每月基础设施最低预算假设")
    parser.add_argument("--infra-max", type=decimal_arg, help="每月基础设施最高预算假设")
    args = parser.parse_args()
    if args.paid % 1 or args.free % 1:
        parser.error("用户数必须是非负整数")
    if args.days <= 0 or args.seconds <= 0:
        parser.error("统计天数和录音秒数必须大于零")
    if args.scenario == "allowance" and args.days != 30:
        parser.error("allowance 固定为一个 30 天规划周期")
    if args.paid_dau > 1 or args.free_dau > 1:
        parser.error("日活比例不能大于 1")
    if (args.infra_min is None) != (args.infra_max is None):
        parser.error("基础设施范围需要同时提供 --infra-min 和 --infra-max")
    if args.infra_min is not None and args.infra_min > args.infra_max:
        parser.error("基础设施最低预算不能大于最高预算")

    daily_records = (
        args.paid * args.paid_dau * args.paid_records
        + args.free * args.free_dau * args.free_records
    )
    voice_records = daily_records * args.days
    records = voice_records
    questions = args.paid * args.paid_questions + args.free * args.free_questions
    insights = args.paid * args.insights
    audio_seconds = voice_records * args.seconds
    if args.scenario == "allowance":
        # Voice extraction is included in the total extraction allowance.
        audio_seconds = (args.paid * D("300") + args.free * D("60")) * D("60")
        voice_records = audio_seconds / args.seconds
        daily_records = voice_records / args.days
        records = args.paid * D("3000") + args.free * D("500")
        if voice_records > records:
            parser.error("该平均录音时长使语音条数超过提取额度；请调整情景")
        questions = args.paid * D("300") + args.free * D("30")
        insights = args.paid * D("200")
    costs = {
        "语音识别": audio_seconds * args.asr_price,
        "记录提取": records * (
            D("1500") * args.flash_input_price + D("300") * args.flash_output_price
        ) / MILLION,
        "深度建议": insights * (
            D("3000") * args.plus_input_price + D("500") * args.plus_output_price
        ) / MILLION,
        "记录向量": records * D("800") * args.embedding_price / MILLION,
        "问答模型": questions * (
            D("2000") * args.flash_input_price + D("350") * args.flash_output_price
        ) / MILLION,
        "问答向量": questions * D("100") * args.embedding_price / MILLION,
    }
    model_total = sum(costs.values(), D(0))
    buffered = model_total * (D(1) + args.buffer)
    # 70% of daily recordings in 10 hours, with a 3x peak over that average.
    peak_per_minute = daily_records * D("0.70") / D("600") * D("3")
    result = {
        "情景": args.scenario,
        "每日语音记录条数": count(daily_records),
        "每月语音记录条数": count(voice_records),
        "每月提取记录条数含语音": count(records),
        "每月语音分钟": count(audio_seconds / D("60")),
        "高峰每分钟录音请求": count(peak_per_minute),
        "每月建议次数": count(insights),
        "每月问答次数": count(questions),
        "每月模型费用元": {key: money(value) for key, value in costs.items()},
        "每月模型小计元": money(model_total),
        "含浮动模型预算元": money(buffered),
    }
    if args.infra_min is not None:
        result["含基础设施总预算元"] = {
            "下限": money(buffered + args.infra_min),
            "上限": money(buffered + args.infra_max),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
