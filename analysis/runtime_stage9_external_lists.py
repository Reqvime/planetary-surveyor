"""Read-only dump of the current planet's selected external object lists."""

from __future__ import annotations

import ctypes

import discovery_probe as probe
import nmspy.data.exported_types as nmse


def main() -> dict[str, object]:
    module_base = probe._nms_module_base()
    addresses, error = probe._resolve_game_addresses(module_base)
    if addresses is None:
        raise RuntimeError(error)
    application_data = probe._read_u64(addresses.application_data_pointer)
    if not application_data:
        raise RuntimeError("application_data_unreadable")
    fauna = probe._read_current_planet_fauna_catalog(application_data)
    if fauna.error:
        raise RuntimeError(fauna.error)
    planet = ctypes.cast(
        fauna.planet_pointer + probe._PLANET_DATA_OFFSET,
        ctypes.POINTER(nmse.cGcPlanetData),
    ).contents
    generation = planet.GenerationData
    indices = [int(value) for value in generation.ExternalObjectListIndices]
    lists: list[dict[str, object]] = []
    for list_index, options in enumerate(generation.ExternalObjectLists):
        values = [str(value).replace("\\", "/").upper() for value in options.Options]
        selected = indices[list_index] if list_index < len(indices) else None
        selected_value = (
            values[selected]
            if selected is not None and 0 <= selected < len(values)
            else None
        )
        lists.append(
            {
                "list_index": list_index,
                "name": str(options.Name),
                "selected_index": selected,
                "selected_value": selected_value,
                "option_count": len(values),
                "options": values,
                "resource_hint": str(options.ResourceHint),
                "order": int(options.Order),
                "probability": float(options.Probability),
                "tile_type": str(options.TileType),
                "suppress_spawn": bool(options.SuppressSpawn),
            }
        )
    return {
        "universe_address": fauna.universe_address,
        "indices": indices,
        "lists": lists,
    }


if __name__ == "__main__":
    main()
