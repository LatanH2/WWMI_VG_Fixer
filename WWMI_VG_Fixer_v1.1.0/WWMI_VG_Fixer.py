# -*- coding: utf-8 -*-
bl_info = {
    "name": "WWMI VG Fixer",
    "author": "LatanH2",
    "version": (1, 2, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > WWMI VG Fixer",
    "description": "Fix vertex groups for WWMI reverse meshes using metadata.json",
    "category": "Mesh",
}

import bpy
import re
import os
import json


# ------------------------------------------
# Zero-weight group removal
# ------------------------------------------

def remove_zero_weight_vgroups(obj):
    to_delete = []
    for vg in obj.vertex_groups:
        used = False
        for v in obj.data.vertices:
            for g in v.groups:
                if g.group == vg.index:
                    used = True
                    break
            if used:
                break
        if not used:
            to_delete.append(vg)

    for vg in to_delete:
        print(f" >> Removing Zero-Weight VG: {vg.name}")
        obj.vertex_groups.remove(vg)


# ------------------------------------------
# Operator: Auto Fix
# ------------------------------------------

class WWMI_OT_auto_fix_vgs(bpy.types.Operator):
    bl_idname = "wwmi.auto_fix_vgs"
    bl_label = "Auto Fix Vertex Groups"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):

        scene = context.scene
        metadata_path = bpy.path.abspath(scene.wwmi_vg_metadata_path)
        remove_zero = scene.wwmi_vg_remove_zero

        if not metadata_path or not os.path.isfile(metadata_path):
            self.report({"ERROR"}, f"File not found: {metadata_path}")
            return {"CANCELLED"}

        print("\n=== WWMI VG Fixer: Auto Fix Begin ===")
        print(f"Metadata: {metadata_path}")

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        components = metadata.get("components")
        if not components:
            self.report({"ERROR"}, "Invalid metadata: no 'components'")
            return {"CANCELLED"}

        merged_max_vg = max(v for comp in components for v in comp["vg_map"].values())
        threshold = merged_max_vg - 256
        print(f"Merged Max VG: {merged_max_vg}  -> threshold {threshold}")

        # Global exceptions: component ID >= 3
        global_exception_vgs = set()
        for comp_id, comp in enumerate(components):
            if comp_id >= 3:
                global_exception_vgs |= set(comp["vg_map"].values())
        print(f"Global shared exceptions: {len(global_exception_vgs)} items")

        comp_name_regex = re.compile(r"Component\s*(\d+)")
        processed_count = 0

        for obj in context.selected_objects:
            if obj.type != "MESH": continue

            match = comp_name_regex.search(obj.name)
            if not match:
                print(f"[{obj.name}] No Component ID")
                continue

            comp_id = int(match.group(1))
            if comp_id >= len(components):
                print(f"[{obj.name}] CompID out of range")
                continue

            local_vg_map = set(components[comp_id]["vg_map"].values())
            component_max_vg = max(local_vg_map)

            print(f"\n[{obj.name}] CompID={comp_id} MaxVG={component_max_vg}")

            for vg in obj.vertex_groups:
                original_name = vg.name
                try: vg_num = int(original_name)
                except ValueError:
                    print(f" - {original_name}: skip text")
                    continue

                # Out of remap range = keep
                if vg_num > threshold:
                    print(f" - {original_name} keep (>threshold)")
                    continue

                if vg_num in global_exception_vgs or vg_num in local_vg_map:

                    if component_max_vg >= 256:
                        if not original_name.startswith("Check"):
                            new_name = f"Check{original_name}"
                            vg.name = new_name
                            print(f" - {original_name} → {new_name} (exception)")
                        else:
                            print(f" - {original_name} keep (Check exists)")
                    else:
                        print(f" - {original_name} keep (exception no Check)")
                    continue

                # Standard +256 remap
                new_name = str(vg_num + 256)
                vg.name = new_name
                print(f" - {original_name} → {new_name} (+256)")

            if remove_zero:
                remove_zero_weight_vgroups(obj)

            processed_count += 1

        print("\n=== Auto Fix Complete ===")
        self.report({"INFO"}, f"Processed {processed_count} objects")
        return {"FINISHED"}


# ------------------------------------------
# Operator: Remove "Check" Prefix
# ------------------------------------------

class WWMI_OT_remove_check_prefix(bpy.types.Operator):
    bl_idname = "wwmi.remove_check_prefix"
    bl_label = "Remove 'Check' Prefix"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):

        regex = re.compile(r"^Check(\d+)$")
        processed = 0

        for obj in context.selected_objects:
            if obj.type != "MESH": continue

            changed = False
            for vg in obj.vertex_groups:
                m = regex.match(vg.name)
                if m:
                    new_name = m.group(1)
                    vg.name = new_name
                    changed = True

            if changed:
                processed += 1

        self.report({"INFO"}, f"Updated {processed} objects")
        return {"FINISHED"}


# ------------------------------------------
# UI Panel
# ------------------------------------------

class VIEW3D_PT_wwmi_vg_fixer(bpy.types.Panel):
    bl_label = "WWMI VG Fixer"
    bl_idname = "VIEW3D_PT_wwmi_vg_fixer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "WWMI VG Fixer"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "wwmi_vg_metadata_path", text="Metadata JSON")
        layout.prop(scene, "wwmi_vg_remove_zero", text="Remove Zero-Weight VGs")
        layout.separator()
        layout.operator("wwmi.auto_fix_vgs", icon="MOD_VERTEX_WEIGHT")
        layout.operator("wwmi.remove_check_prefix", icon="BACK")


# ------------------------------------------
# Register
# ------------------------------------------

classes = (
    WWMI_OT_auto_fix_vgs,
    WWMI_OT_remove_check_prefix,
    VIEW3D_PT_wwmi_vg_fixer,
)


def register():
    from bpy.props import StringProperty, BoolProperty
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.wwmi_vg_metadata_path = StringProperty(
        name="Metadata JSON",
        subtype="FILE_PATH",
    )
    bpy.types.Scene.wwmi_vg_remove_zero = BoolProperty(
        name="Remove Zero-Weight VGs",
        default=True,
    )


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

    del bpy.types.Scene.wwmi_vg_metadata_path
    del bpy.types.Scene.wwmi_vg_remove_zero


if __name__ == "__main__":
    register()
