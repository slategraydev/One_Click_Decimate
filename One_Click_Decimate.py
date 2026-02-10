# ============================================================
#  One Click Decimate
#  Author: Slategray / Randall Rosas
#  Version: 2.0.1 | Release Date: 2026-02-10
# ============================================================


import bmesh
import bpy
from mathutils import bvhtree

bl_info = {
    "name": "One Click Decimate",
    "author": "Slategray",
    "version": (2, 0, 1),
    "blender": (5, 0, 1),
    "location": "View3D > Sidebar > Tool",
    "description": "One click decimation tool that intelligently preserves mesh data.",
    "category": "Object",
}


def debug_print(msg):
    print(f"[OneClickDecimate 2.0.1] {msg}")


# ============================================================
#  MESH DATA TRANSFER
# ============================================================


def transfer_mesh_data(source, target):
    """
    Transfers mesh data (vertex positions, groups, shape keys) from source to target.
    Essential for decimation where the simplified mesh needs to retain all original data.
    """
    debug_print("Starting mesh data transfer...")

    src_bm = bmesh.new()
    src_bm.from_mesh(source.data)
    bmesh.ops.triangulate(src_bm, faces=src_bm.faces)
    src_bm.verts.ensure_lookup_table()
    src_bm.faces.ensure_lookup_table()
    src_tree = bvhtree.BVHTree.FromBMesh(src_bm)

    vert_map = {}
    target_to_world = target.matrix_world
    world_to_source = source.matrix_world.inverted()

    # Snap target vertices to source surface
    for v in target.data.vertices:
        world_pos = target_to_world @ v.co
        local_pos = world_to_source @ world_pos
        co, normal, f_idx, dist = src_tree.find_nearest(local_pos)
        if f_idx is not None:
            face = src_bm.faces[f_idx]
            nearest_v = min(face.verts, key=lambda sv: (sv.co - local_pos).length)
            v.co = nearest_v.co
            vert_map[v.index] = nearest_v.index

    target.data.update()

    target.vertex_groups.clear()
    for src_group in source.vertex_groups:
        target_group = target.vertex_groups.new(name=src_group.name)
        for t_idx, s_idx in vert_map.items():
            try:
                weight = src_group.weight(s_idx)
                if weight > 0.0:
                    target_group.add([t_idx], weight, "REPLACE")
            except (ValueError, TypeError, AttributeError, RuntimeError):
                pass

    if source.data.shape_keys:
        debug_print(f"Syncing {len(source.data.shape_keys.key_blocks)} Shape Keys...")
        target.update_tag()
        bpy.context.view_layer.update()

        src_keys = source.data.shape_keys
        ref_sk_src = src_keys.reference_key

        if not target.data.shape_keys:
            target.shape_key_add(name=ref_sk_src.name)
        target_ref_sk = target.data.shape_keys.reference_key
        target_ref_sk.name = ref_sk_src.name

        # Map source key names to target key blocks for quick lookup
        key_block_map = {ref_sk_src.name: target_ref_sk}

        for sk_src in src_keys.key_blocks:
            if sk_src == ref_sk_src:
                continue
            new_sk = target.shape_key_add(name=sk_src.name)
            key_block_map[sk_src.name] = new_sk

            for t_idx, s_idx in vert_map.items():
                new_sk.data[t_idx].co = sk_src.data[s_idx].co.copy()

            new_sk.value = sk_src.value
            new_sk.slider_min = sk_src.slider_min
            new_sk.slider_max = sk_src.slider_max
            new_sk.mute = sk_src.mute
            new_sk.interpolation = sk_src.interpolation
            new_sk.vertex_group = sk_src.vertex_group

            if sk_src.relative_key and sk_src.relative_key.name in key_block_map:
                new_sk.relative_key = key_block_map[sk_src.relative_key.name]

        target.active_shape_key_index = source.active_shape_key_index

    src_bm.free()


# ============================================================
#  ONE CLICK DECIMATE
# ============================================================


class OBJECT_OT_one_click_decimate(bpy.types.Operator):
    bl_idname = "object.one_click_decimate"
    bl_label = "Run Master Decimate"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """
        Performs mesh decimation while preserving shape keys, vertex groups, and mesh data.
        Essential for reducing polygon count without losing critical mesh attributes.
        """
        source_obj = context.active_object
        if not source_obj or source_obj.type != "MESH":
            self.report({"ERROR"}, "Select a Mesh.")
            return {"CANCELLED"}

        ratio = context.scene.one_click_decimate_ratio
        orig_matrix = source_obj.matrix_world.copy()

        # Store parenting info to restore it later
        orig_parent = source_obj.parent
        orig_parent_type = source_obj.parent_type
        orig_parent_bone = source_obj.parent_bone
        orig_matrix_parent_inverse = source_obj.matrix_parent_inverse.copy()

        bpy.ops.object.select_all(action="DESELECT")
        source_obj.select_set(True)
        bpy.ops.object.duplicate(linked=False)
        working_obj = context.active_object

        debug_print("Baking parent transforms into duplicate...")
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # Create perimeter lock to protect UV seams and boundaries
        view_layer = bpy.context.view_layer
        view_layer.objects.active = working_obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.seams_from_islands()
        bpy.ops.object.mode_set(mode="OBJECT")

        vgroup = working_obj.vertex_groups.new(name="LOCK")
        bm = bmesh.new()
        bm.from_mesh(working_obj.data)

        # Collect vertices on UV seams and mesh boundaries
        seam_verts = {
            v for v in bm.verts if any(e.seam or e.is_boundary for e in v.link_edges)
        }

        # Collect neighbors of seam vertices for additional protection
        buffer_verts = set()
        for v in seam_verts:
            for edge in v.link_edges:
                buffer_verts.add(edge.other_vert(v))

        total_lock = seam_verts.union(buffer_verts)
        vgroup.add([v.index for v in total_lock], 1.0, "REPLACE")
        bm.free()

        if working_obj.data.shape_keys:
            bpy.ops.object.shape_key_remove(all=True)

        debug_print(f"Decimating mesh to {ratio * 100}% of original face count...")
        mod = working_obj.modifiers.new(name="Decimate", type="DECIMATE")
        mod.ratio = ratio
        mod.vertex_group = "LOCK"
        mod.invert_vertex_group = True
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)

        transfer_mesh_data(source_obj, working_obj)

        # Restore parenting
        if orig_parent:
            working_obj.parent = orig_parent
            working_obj.parent_type = orig_parent_type
            working_obj.parent_bone = orig_parent_bone
            working_obj.matrix_parent_inverse = orig_matrix_parent_inverse

        working_obj.matrix_world = orig_matrix
        working_obj.name = source_obj.name + "_Decimated"
        source_obj.hide_set(True)
        view_layer.update()

        self.report({"INFO"}, "Mesh decimation complete with full data restoration.")
        return {"FINISHED"}


# ============================================================
#  UI PANEL
# ============================================================


class VIEW3D_PT_one_click_decimate(bpy.types.Panel):
    bl_label = "One Click Decimate"
    bl_idname = "VIEW3D_PT_one_click_decimate"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        box = layout.box()

        selected_meshes = [
            obj for obj in context.selected_objects if obj.type == "MESH"
        ]

        split = layout.split(factor=0.5)
        col_left = split.column()
        col_right = split.column()
        box_left = col_left.box()
        box_right = col_right.box()
        box_right.alignment = "RIGHT"

        if selected_meshes:
            obj = selected_meshes[0]
            box.label(text=obj.name, icon="OUTLINER_OB_MESH")
            triangles = sum(len(p.vertices) - 2 for p in obj.data.polygons)
            target_triangles = int(triangles * context.scene.one_click_decimate_ratio)
            box_left.label(text="Triangles", icon="MESH_DATA")
            box_right.label(text=f"{target_triangles}  /  {triangles}")
        else:
            box.label(text="No Object", icon="OBJECT_DATAMODE")
            box_left.label(text="N/A", icon="MESH_DATA")
            box_right.label(text="N/A")

        layout.prop(
            context.scene, "one_click_decimate_ratio", text="Ratio", slider=True
        )
        layout.operator(
            "object.one_click_decimate",
            text="Decimate",
            icon="MOD_DECIM",
        )


def register():
    classes = [OBJECT_OT_one_click_decimate, VIEW3D_PT_one_click_decimate]
    for cls in classes:
        bpy.utils.register_class(cls)

    if not hasattr(bpy.types.Scene, "one_click_decimate_ratio"):
        bpy.types.Scene.one_click_decimate_ratio = bpy.props.FloatProperty(
            name="Ratio",
            default=0.5,
            min=0.01,
            max=1.0,
            update=lambda self, context: context.region.tag_redraw(),
        )


def unregister():
    classes = [OBJECT_OT_one_click_decimate, VIEW3D_PT_one_click_decimate]
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
