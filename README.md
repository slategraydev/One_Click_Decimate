# One Click Decimate for Blender

A professional one-click Blender script for mesh reduction and retopology that preserves shape keys, UVs, vertex groups, materials, and other essential mesh data.

## Description

This is a powerful Blender Add-on that reduces the polygon count of models while maintaining all important data.

**Version 2.0.0: Complete Rewrite**
This version is a bit more aggressive in its decimation process and UV preservation. It should have significant improvements for most meshes, but may "eat" away at them if the decimation ratio is too low.

## Key Features

-   **Native Decimation**: Uses Blender's robust Triangle Reduction algorithm.
-   **Two-Ring Perimeter Protection**: Automatically detects UV seams and boundaries, then protects both seam vertices and their neighbors to preserve mesh quality.
-   **Shape Key Preservation**: Advanced algorithm that transfers all shape keys with their vertex positions and relative key hierarchy intact.
-   **Full Data Transfer**: Intelligently transfers Vertex Groups, UVs, and all mesh attributes from source to decimated mesh.
-   **Real-Time Preview**: See target triangle count update instantly as you adjust the ratio slider.
-   **Visual Feedback**: UI displays current triangle count and target count in an intuitive format.

## Installation

1.  Download the `One_Click_Decimate.py` file.
2.  In Blender, go to `Edit > Preferences > Add-ons`.
3.  Click **Install from Disk...** and select `One_Click_Decimate.py`.
4.  Enable the addon **"One Click Decimate"**.

## How to Use

1.  Select your mesh in the 3D View.
2.  Open the Sidebar (press `N`).
3.  Go to the **Tool** tab.
4.  Find the **One Click Decimate** panel.
5.  The panel displays the selected object name and current triangle count.
6.  **Adjust Ratio**: Use the slider to set your target. The display shows "target / total" triangles (e.g., "2500 / 5000" for 50%).
7.  Click **Decimate** to process.

## License

AGPL-3.0 License.
