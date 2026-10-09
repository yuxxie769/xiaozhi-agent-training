"""Qwen3.5 text/tool formatting and assistant-only labels (no model required)."""
import json
import re

BLOCK = re.compile(r"<\|im_start\|>(system|user|assistant)\n(.*?)<\|im_end\|>", re.S)
EMPTY_THINK = "<think>\n\n</think>\n\n"
CONTROL_MARKERS = ("<|im_start|>", "<|im_end|>", "<|endoftext|>")


class FormatError(ValueError):
    pass


def assert_safe_strings(value):
    if isinstance(value, str):
        if any(marker in value for marker in CONTROL_MARKERS):
            raise FormatError("raw_chat_control_marker")
    elif isinstance(value, dict):
        for key, item in value.items():
            assert_safe_strings(key)
            assert_safe_strings(item)
    elif isinstance(value, list):
        for item in value:
            assert_safe_strings(item)


def prepare_example(tokenizer, row, *, enable_thinking=False, max_length=None):
    """Render the official template unchanged; mask context, headers and empty think prefix.

    Returns (training_features, audit). Padding remains a separate step.
    Nonempty reasoning is deliberately unsupported by this text-only SFT adapter.
    """
    if not row.get("tools"):
        raise FormatError("missing_tools")
    assert_safe_strings(row)
    for message in row["messages"]:
        if message.get("reasoning_content") or (message.get("role") == "assistant" and
                any(tag in (message.get("content") or "") for tag in ("<think>", "</think>"))):
            raise FormatError("reasoning_data_requires_separate_policy")
    rendered = tokenizer.apply_chat_template(row["messages"], tools=row["tools"],
        tokenize=False, add_generation_prompt=False, enable_thinking=enable_thinking)
    blocks = list(BLOCK.finditer(rendered))
    if not blocks or "".join(match.group(0) + "\n" for match in blocks) != rendered:
        raise FormatError("unexpected_chat_template_structure")
    system = blocks[0]
    if system.group(1) != "system":
        raise FormatError("missing_rendered_system")
    tools_match = re.search(r"<tools>\n(.*?)\n</tools>", system.group(2), re.S)
    if not tools_match or [json.loads(line) for line in tools_match.group(1).splitlines()] != row["tools"]:
        raise FormatError("rendered_tools_mismatch")
    source_assistants = [m for m in row["messages"] if m["role"] == "assistant"]
    assistant_blocks = [m for m in blocks if m.group(1) == "assistant"]
    if len(source_assistants) != len(assistant_blocks):
        raise FormatError("assistant_count_mismatch")
    spans = []
    calls = 0
    for source, block in zip(source_assistants, assistant_blocks):
        start, end = block.start(2), block.end()
        body = block.group(2)
        if body.startswith(EMPTY_THINK):
            start += len(EMPTY_THINK)
            body = body[len(EMPTY_THINK):]
        source_calls = source.get("tool_calls") or []
        if re.findall(r"<function=([^>]+)>", body) != [c["function"]["name"] for c in source_calls]:
            raise FormatError("tool_call_names_mismatch")
        encoded_calls = re.findall(r"<tool_call>\n<function=([^>]+)>\n(.*?)</function>\n</tool_call>", body, re.S)
        if len(encoded_calls) != len(source_calls):
            raise FormatError("tool_call_count_mismatch")
        for call, (_, encoded_arguments) in zip(source_calls, encoded_calls):
            arguments = call["function"]["arguments"]
            pairs = re.findall(r"<parameter=([^>]+)>\n(.*?)\n</parameter>", encoded_arguments, re.S)
            if len(pairs) != len(arguments) or set(k for k, _ in pairs) != set(arguments):
                raise FormatError("tool_argument_names_mismatch")
            for key, value in pairs:
                original = arguments[key]
                decoded = json.loads(value) if isinstance(original, (dict, list)) else value
                if decoded != (original if isinstance(original, (dict, list, str)) else str(original)):
                    raise FormatError("tool_argument_value_mismatch")
        content = (source.get("content") or "").strip()
        if content and not body.startswith(content):
            raise FormatError("assistant_content_mismatch")
        spans.append((start, end))  # Includes end-of-message EOS, excludes role header.
        calls += len(source_calls)
    encoded = tokenizer(rendered, add_special_tokens=False, return_offsets_mapping=True, truncation=False)
    ids, offsets = encoded["input_ids"], encoded["offset_mapping"]
    if max_length is not None and len(ids) > max_length:
        raise FormatError(f"overlength:{len(ids)}>{max_length}; truncation is forbidden")
    labels = [-100] * len(ids)
    span_index = 0
    supervised_by_message = [0] * len(spans)
    for index, (left, right) in enumerate(offsets):
        while span_index < len(spans) and left >= spans[span_index][1]:
            span_index += 1
        if span_index == len(spans):
            break
        start, end = spans[span_index]
        if right <= start:
            continue
        if left < start or right > end or left == right:
            raise FormatError("token_crosses_loss_boundary")
        labels[index] = ids[index]
        supervised_by_message[span_index] += 1
    if not supervised_by_message or not all(supervised_by_message):
        raise FormatError("empty_assistant_labels")
    call_id = tokenizer.convert_tokens_to_ids("<tool_call>")
    if sum(label == call_id for label in labels) != calls:
        raise FormatError("tool_calls_not_fully_supervised")
    features = {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels}
    audit = {"tokens": len(ids), "supervised_tokens": sum(x != -100 for x in labels),
             "assistant_messages": len(spans), "tool_calls": calls,
             "supervised_by_message": supervised_by_message,
             "assistant_spans": spans, "rendered": rendered}
    return features, audit


def pad_examples(examples, pad_token_id):
    """Right padding for the future trainer collator; all padding labels stay -100."""
    if not examples or pad_token_id is None:
        raise FormatError("missing_batch_or_pad_token")
    width = max(len(row["input_ids"]) for row in examples)
    result = {key: [] for key in ("input_ids", "attention_mask", "labels")}
    for row in examples:
        size = len(row["input_ids"])
        if len(row["labels"]) != size or len(row["attention_mask"]) != size:
            raise FormatError("feature_length_mismatch")
        pad = width - size
        result["input_ids"].append(row["input_ids"] + [pad_token_id] * pad)
        result["attention_mask"].append(row["attention_mask"] + [0] * pad)
        result["labels"].append(row["labels"] + [-100] * pad)
    return result
