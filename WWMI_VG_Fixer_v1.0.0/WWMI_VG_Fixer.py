# -*- coding: utf-8 -*-

bl_info = {
    "name": "WWMI VG Fixer",
    "author": "LatanH2",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > WWMI VG Fixer",
    "description": "Fix vertex groups for WWMI reverse meshes using metadata.json",
    "category": "Mesh",
}

import bpy
import json
import os
import re


# ------------------------------------------------------------------------
# Utility: remove zero-weight vertex groups
# ------------------------------------------------------------------------

def remove_zero_weight_vgroups(obj):
    vg_to_delete = []

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
            vg_to_delete.append(vg)

    for vg in vg_to_delete:
        print(f" >> Removing Zero-Weight VG: {vg.name}")
        obj.vertex_groups.remove(vg)


# ------------------------------------------------------------------------
# Operator 1: Auto Fix Vertex Groups
# ------------------------------------------------------------------------

class WWMI_OT_auto_fix_vgs(bpy.types.Operator):
    bl_idname = "wwmi.auto_fix_vgs"
    bl_label = "Auto Fix Vertex Groups"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        metadata_path = scene.wwmi_vg_metadata_path
        metadata_path = bpy.path.abspath(metadata_path)
        remove_zero = scene.wwmi_vg_remove_zero

        if not metadata_path:
            self.report({"ERROR"}, "Metadata JSON path is not set.")
            return {"CANCELLED"}

        if not os.path.isfile(metadata_path):
            self.report({"ERROR"}, f"File not found: {metadata_path}")
            return {"CANCELLED"}

        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to read metadata JSON: {e}")
            return {"CANCELLED"}

        components = metadata.get("components")
        if not components:
            self.report({"ERROR"}, "Invalid metadata: 'components' field missing.")
            return {"CANCELLED"}

        try:
            merged_max_vg = max(
                v for comp in components for v in comp["vg_map"].values()
            )
        except Exception as e:
            self.report({"ERROR"}, f"Failed to compute max VG: {e}")
            return {"CANCELLED"}

        threshold = merged_max_vg - 256

        print("\n=== WWMI VG Fixer: Auto Fix Begin ===")
        print(f"Metadata: {metadata_path}")
        print(f"Merged Max VG: {merged_max_vg}")
        print(f"Threshold (max-256): {threshold}")
        print(f"Remove zero-weight VG: {remove_zero}")

        comp_name_pattern = re.compile(r"Component\s*(\d+)")

        processed_objects = 0

        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue

            m = comp_name_pattern.search(obj.name)
            if not m:
                print(f"[{obj.name}] Component ID not found in name, skipped.")
                continue

            comp_id = int(m.group(1))
            if comp_id >= len(components):
                print(f"[{obj.name}] Component ID {comp_id} out of range, skipped.")
                continue

            comp = components[comp_id]
            vg_map = comp.get("vg_map", {})
            if not vg_map:
                print(f"[{obj.name}] No vg_map for component {comp_id}, skipped.")
                continue

            exception_vgs = set(vg_map.values())
            component_max_vg = max(exception_vgs)

            print(f"\n[{obj.name}] Component {comp_id} / Component Max VG={component_max_vg}")

            for vg in obj.vertex_groups:
                original_name = vg.name

                try:
                    vg_num = int(original_name)
                except ValueError:
                    print(f" - '{original_name}': not numeric, skipped.")
                    continue

                if vg_num > threshold:
                    print(f" - {original_name} kept (above threshold).")
                    continue

                if vg_num in exception_vgs:
                    if component_max_vg >= 256:
                        if not original_name.startswith("Check"):
                            new_name = f"Check{original_name}"
                            vg.name = new_name
                            print(f" - {original_name} → {new_name} (exception / Check).")
                        else:
                            print(f" - {original_name} already has Check, kept.")
                    else:
                        print(f" - {original_name} kept (exception, CompMaxVG<256).")
                    continue

                new_name = str(vg_num + 256)
                vg.name = new_name
                print(f" - {original_name} → {new_name} (+256).")

            if remove_zero:
                print(f" >> Zero-Weight VGs Cleanup for {obj.name}")
                remove_zero_weight_vgroups(obj)

            processed_objects += 1

        print("\n=== WWMI VG Fixer: Auto Fix Done ===")
        self.report({"INFO"}, f"Auto fixed vertex groups on {processed_objects} mesh object(s).")
        return {"FINISHED"}


# ------------------------------------------------------------------------
# Operator 2: Remove "Check" prefix
# ------------------------------------------------------------------------

class WWMI_OT_remove_check_prefix(bpy.types.Operator):
    """Remove 'Check' prefix from vertex group names like 'Check123' -> '123'."""
    bl_idname = "wwmi.remove_check_prefix"
    bl_label = "Remove \"Check\" Prefix"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        pattern = re.compile(r"^Check(\d+)$")
        processed_objects = 0

        print("\n=== WWMI VG Fixer: Remove 'Check' Prefix Begin ===")

        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue

            print(f"\n[{obj.name}] Removing Check prefixes...")
            changed = False

            for vg in obj.vertex_groups:
                match = pattern.match(vg.name)
                if match:
                    new_name = match.group(1)
                    print(f" - {vg.name} → {new_name}")
                    vg.name = new_name
                    changed = True
                else:
                    print(f" - {vg.name} kept")

            if changed:
                processed_objects += 1

        print("\n=== WWMI VG Fixer: Remove 'Check' Prefix Done ===")
        self.report({"INFO"}, f"Removed 'Check' prefix on {processed_objects} mesh object(s).")
        return {"FINISHED"}


# ------------------------------------------------------------------------
# Panel
# ------------------------------------------------------------------------

class VIEW3D_PT_wwmi_vg_fixer(bpy.types.Panel):
    bl_label = "WWMI VG Fixer"
    bl_idname = "VIEW3D_PT_wwmi_vg_fixer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "WWMI VG Fixer"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        col.label(text="Metadata JSON:")
        col.prop(scene, "wwmi_vg_metadata_path", text="")

        layout.separator()

        layout.prop(scene, "wwmi_vg_remove_zero",
                    text="Remove Zero-Weight Vertex Groups")

        layout.separator()

        col = layout.column(align=True)
        col.operator("wwmi.auto_fix_vgs",
                     text="Auto Fix Vertex Groups",
                     icon="MOD_VERTEX_WEIGHT")
        col.operator("wwmi.remove_check_prefix",
                     text="Remove \"Check\" Prefix",
                     icon="BACK")


# ------------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------------

classes = (
    WWMI_OT_auto_fix_vgs,
    WWMI_OT_remove_check_prefix,
    VIEW3D_PT_wwmi_vg_fixer,
)


def register():
    from bpy.props import StringProperty, BoolProperty

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.wwmi_vg_metadata_path = StringProperty(
        name="Metadata JSON",
        description="Path to metadata.json exported from WWMI reverse",
        subtype="FILE_PATH",
    )

    bpy.types.Scene.wwmi_vg_remove_zero = BoolProperty(
        name="Remove Zero-Weight Vertex Groups",
        description="If enabled, remove vertex groups with no weights after auto fixing",
        default=True,
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.wwmi_vg_metadata_path
    del bpy.types.Scene.wwmi_vg_remove_zero


if __name__ == "__main__":
    register()
