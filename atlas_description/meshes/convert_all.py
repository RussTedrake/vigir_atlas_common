import os
import subprocess

# Define the directory containing the .dae files
dae_directory = "."  # Change this to your directory path

# Iterate over all files in the directory
for filename in os.listdir(dae_directory):
    if filename.endswith(".dae"):
        # Get the base name without the extension
        base_name = os.path.splitext(filename)[0]

        # Define the full path to the input .dae file
        dae_path = os.path.join(dae_directory, filename)

        # Define the output base name for the .obj file
        obj_base_name = os.path.join(dae_directory, base_name)

        print(f"Converting {dae_path}")

        # Run the dae2obj conversion script
        subprocess.run(["python3", "dae2obj.py", dae_path, obj_base_name])

        # Run the obj2gltf command
        obj_path = obj_base_name + ".obj"
        subprocess.run(["obj2gltf", "-s", "-i", obj_path])

print("Conversion completed for all .dae files.")
