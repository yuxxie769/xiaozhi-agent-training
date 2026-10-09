"""Minimal preset library reconstructed from saved evaluation conversations."""

import copy
import json
from pathlib import Path


class PresetError(ValueError):
    pass


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Library:
    """Expose the subset of the simulator Library API used by seed generation."""

    def __init__(self, conversations_path):
        path = Path(conversations_path)
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list) or not rows:
            raise PresetError("家居 conversations 必须是非空数组")
        self._presets = {}
        for row in rows:
            try:
                config = row["context"]["preset_config"]
                name = config["preset"]
            except (KeyError, TypeError) as exc:
                raise PresetError("家居轨迹缺少 context.preset_config") from exc
            if name in self._presets and _canonical(self._presets[name]) != _canonical(config):
                raise PresetError(f"同一 preset 存在不一致定义：{name}")
            self._presets[name] = copy.deepcopy(config)
        self._special = {
            name
            for name, config in self._presets.items()
            if any(key in config for key in ("initial", "rules", "turns"))
        }

    def resolve(self, preset):
        if not isinstance(preset, str) or preset not in self._presets:
            raise PresetError(f"未知 preset：{preset}")
        return copy.deepcopy(self._presets[preset])

    def list_presets(self, *, include_special=False):
        return [
            {
                "preset": name,
                "description": config.get("description", ""),
                "device_count": len(config["devices"]),
                "candidates": list(config.get("candidates", [])),
            }
            for name, config in self._presets.items()
            if include_special or name not in self._special
        ]

    def list_special_presets(self):
        return [
            item
            for item in self.list_presets(include_special=True)
            if item["preset"] in self._special
        ]

    def get_devices(self, preset, *, candidates_only=False, controllable_only=False):
        config = self.resolve(preset)
        initial = {
            **config.get("initial", {}).get("states", {}),
            **config.get("turns", {}).get("1", {}).get("states", {}),
        }
        ids = config.get("candidates", []) if candidates_only else config["devices"]
        devices = config["devices"]
        return [
            {
                "entity_id": entity_id,
                **devices[entity_id],
                "state": initial.get(entity_id, devices[entity_id]["state"]),
            }
            for entity_id in ids
            if not controllable_only or devices[entity_id]["controllable"]
        ]

    def validate_entities(self, preset, entity_ids):
        devices = self.resolve(preset)["devices"]
        if not isinstance(entity_ids, (list, tuple)):
            raise PresetError("设备引用必须是列表")
        for entity_id in entity_ids:
            if entity_id is not None and entity_id not in devices:
                raise PresetError(f"设备不属于 {preset}：{entity_id}")
