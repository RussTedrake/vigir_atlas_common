import xml.etree.ElementTree as ET
import os
import numpy as np


def apply_transformation(vertices, matrix):
    """Apply a transformation matrix to a list of vertices."""
    transformed_vertices = []
    for v in vertices:
        # Convert to homogeneous coordinates
        v_homogeneous = np.array([v[0], v[1], v[2], 1.0])
        # Apply transformation
        v_transformed = matrix @ v_homogeneous
        # Convert back to 3D coordinates
        transformed_vertices.append(v_transformed[:3])
    return transformed_vertices


def get_combined_transformation(node, root, ns):
    """Recursively get the combined transformation matrix for a node."""
    transformation_matrix = np.identity(4)

    # Get this node's transformation
    for matrix_elem in node.findall("collada:matrix", ns):
        matrix_values = list(map(float, matrix_elem.text.split()))
        matrix = np.array(matrix_values).reshape((4, 4))
        transformation_matrix = transformation_matrix @ matrix

    # Find parent by searching the tree
    for potential_parent in root.findall(".//collada:node", ns):
        if node in potential_parent:
            parent_transform = get_combined_transformation(potential_parent, root, ns)
            return transformation_matrix @ parent_transform

    return transformation_matrix


def convert_dae_to_obj(input_path, output_path):
    # Parse DAE
    ET.register_namespace("", "http://www.collada.org/2005/11/COLLADASchema")
    tree = ET.parse(input_path)
    root = tree.getroot()
    ns = {"collada": "http://www.collada.org/2005/11/COLLADASchema"}

    # Get geometry data
    geometry = root.find(".//collada:geometry", ns)
    mesh = geometry.find(".//collada:mesh", ns)

    # Find the node containing the geometry
    geometry_id = geometry.get("id")
    instance_geometry = root.find(
        f".//collada:instance_geometry[@url='#{geometry_id}']", ns
    )
    if instance_geometry is None:
        raise ValueError(
            "Could not find instance_geometry for the geometry in the DAE file."
        )

    # Find the node containing the geometry - DIRECT PARENT of instance_geometry
    node = None
    for potential_node in root.findall(".//collada:node", ns):
        if instance_geometry in potential_node:  # Direct child check
            node = potential_node
            break

    # Get transformation matrix
    if node is None:
        transformation_matrix = np.identity(4)
    else:
        transformation_matrix = get_combined_transformation(node, root, ns)

    # Process vertices
    vertices = []
    vertex_source = mesh.find(".//collada:vertices", ns)
    vertex_data = vertex_source.find(".//collada:input[@semantic='POSITION']", ns)
    vertex_array = mesh.find(
        f".//collada:source[@id='{vertex_data.get('source')[1:]}']//collada:float_array",
        ns,
    )
    vertex_values = list(map(float, vertex_array.text.split()))

    # Convert vertices to homogeneous coordinates and transform them
    for i in range(0, len(vertex_values), 3):
        vertex = np.array(
            [vertex_values[i], vertex_values[i + 1], vertex_values[i + 2], 1.0]
        )
        # Apply transformation
        transformed = transformation_matrix @ vertex
        # Convert back to 3D coordinates (divide by w if needed)
        if transformed[3] != 0:
            transformed = transformed[:3] / transformed[3]
        else:
            transformed = transformed[:3]
        vertices.append(transformed)

    # Extract normals
    normals_src = None
    for source in mesh.findall(".//collada:source", ns):
        if source.get("id").endswith("-Normal0"):
            normals_src = source
            break

    if normals_src is None:
        raise ValueError("Could not find normals source in the DAE file.")

    float_array_elem = normals_src.find(".//collada:float_array", ns)
    if float_array_elem is None:
        raise ValueError("Could not find float_array for normals in the DAE file.")

    normals = [float(x) for x in float_array_elem.text.split()]
    normals = [normals[i : i + 3] for i in range(0, len(normals), 3)]

    # Extract UVs
    uvs_src = None
    for source in mesh.findall(".//collada:source", ns):
        if source.get("id").endswith("-UV0"):
            uvs_src = source
            break

    if uvs_src is None:
        raise ValueError("Could not find UVs source in the DAE file.")

    float_array_elem = uvs_src.find(".//collada:float_array", ns)
    if float_array_elem is None:
        raise ValueError("Could not find float_array for UVs in the DAE file.")

    uvs = [float(x) for x in float_array_elem.text.split()]
    uvs = [uvs[i : i + 2] for i in range(0, len(uvs), 2)]

    # Extract triangles
    triangles = mesh.find(".//collada:triangles", ns)
    if triangles is None:
        raise ValueError("Could not find triangles in the DAE file.")

    indices_elem = triangles.find(".//collada:p", ns)
    if indices_elem is None:
        raise ValueError("Could not find indices for triangles in the DAE file.")

    indices = [int(x) for x in indices_elem.text.split()]

    # Get material info
    material_id = triangles.get("material")
    material_effect = None
    material_image = None

    # Find material and its texture
    for material in root.findall(".//collada:material", ns):
        if material.get("id") == material_id:
            effect_url = material.find(".//collada:instance_effect", ns).get("url")[
                1:
            ]  # Remove '#'
            for effect in root.findall(".//collada:effect", ns):
                if effect.get("id") == effect_url:
                    texture = effect.find(".//collada:diffuse//collada:texture", ns)
                    if texture is not None:
                        texture_id = texture.get("texture")
                        for image in root.findall(".//collada:image", ns):
                            if image.get("id") == texture_id:
                                material_image = image.find(
                                    ".//collada:init_from", ns
                                ).text

    # Write OBJ file
    with open(output_path + ".obj", "w") as f:
        # Write header
        f.write(f"# Converted from {os.path.basename(input_path)}\n")
        f.write(f"mtllib {os.path.basename(output_path)}.mtl\n\n")

        # Write vertices
        for v in vertices:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

        # Write texture coordinates
        for vt in uvs:
            f.write(f"vt {vt[0]} {vt[1]}\n")

        # Write normals
        for vn in normals:
            f.write(f"vn {vn[0]} {vn[1]} {vn[2]}\n")

        # Write face indices (DAE uses 0-based indices, OBJ uses 1-based)
        f.write(f"\nusemtl {material_id}\n")
        for i in range(
            0, len(indices), 9
        ):  # 9 because each vertex has position, normal, and uv
            v1 = indices[i] + 1
            v2 = indices[i + 3] + 1
            v3 = indices[i + 6] + 1
            vt1 = indices[i + 2] + 1
            vt2 = indices[i + 5] + 1
            vt3 = indices[i + 8] + 1
            vn1 = indices[i + 1] + 1
            vn2 = indices[i + 4] + 1
            vn3 = indices[i + 7] + 1
            f.write(f"f {v1}/{vt1}/{vn1} {v2}/{vt2}/{vn2} {v3}/{vt3}/{vn3}\n")

    # Write MTL file
    with open(output_path + ".mtl", "w") as f:
        f.write(f"newmtl {material_id}\n")
        f.write("Ka 1.000000 1.000000 1.000000\n")
        f.write("Kd 1.000000 1.000000 1.000000\n")
        f.write("Ks 0.000000 0.000000 0.000000\n")
        f.write("Ns 2.000000\n")
        if material_image:
            f.write(f"map_Kd {os.path.basename(material_image)}\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python script.py input.dae output_base_name")
        print("Example: python script.py model.dae model")
        sys.exit(1)
    convert_dae_to_obj(sys.argv[1], sys.argv[2])
