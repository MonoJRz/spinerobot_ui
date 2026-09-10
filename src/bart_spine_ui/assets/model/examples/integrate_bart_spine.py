"""Minimal example for replacing the current procedural 3D screw/tulip actors."""

from bart_spine_implant_models import assembly_actors


def add_implant_to_renderer(renderer, plan, rod_plan=None):
    slot_direction = None
    if rod_plan is not None:
        slot_direction = rod_plan.tulip_slot_directions_lps.get(plan.level)

    screw_actor, tulip_actor = assembly_actors(
        plan,
        rod_slot_direction_lps=slot_direction,
    )

    renderer.AddActor(screw_actor)
    renderer.AddActor(tulip_actor)
    return screw_actor, tulip_actor
