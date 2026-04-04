TriplyAM — AM Tools and Lattices
TriplyAM is a free, open-source desktop application for generating TPMS and Voronoi lattice infill structures for additive manufacturing. Import any STL or 3MF part, choose a lattice type and parameters, and export a print-ready 3MF in seconds.
Features
4 TPMS lattice types — Gyroid, Schwarz P, Schwarz D, Schoen I-WP
2 Voronoi modes — Voronoi (Random) for organic structure, Voronoi (Structure) with Lloyd relaxation for uniform cells
Shell-on or lattice-only — generate with a solid outer wall or fill the full volume
Independent wall thickness — control wall and infill separately
3MF export — with embedded metadata, license, and generator info
STEP export — via cadquery (falls back to faceted STEP if unavailable)
Export debug log — one-click log export from the Export tab for diagnosis
Crash logging — automatically written to ~/.triply-crash.log and ~/Downloads/triplyam-crash.log
GPL v3 licensed — free to use, modify, and distribute under the same license
Platforms
Linux - AppImage — no installation required
Windows - Triply-Setup.exe installer
Quick Start
Download and run the AppImage (Linux) or installer (Windows)
Import a part via File → Import or drag and drop an STL/3MF
Select the part in the Parts tree
Go to the Modify tab, choose a lattice type and set parameters
Click Generate Lattice
Go to the Export tab and export as 3MF
Building from Source
git clone https://github.com/Orville4th/TriplyAM.git
cd TriplyAM
pip install -r requirements.txt
python src/main.py
Requirements
Python 3.11+
PyQt6
numpy
numpy-stl
scikit-image
scipy
manifold3d
meshlib
pyvista
PyOpenGL
License
TriplyAM is licensed under the GNU General Public License v3 (GPL v3).
You are free to use, modify, and distribute this software. Any modified version you distribute must also be licensed under GPL v3 and include the full source code.
See the LICENSE file or gnu.org/licenses/gpl-3.0 for full terms.

Third-Party Libraries
TriplyAM is built on the following open-source libraries. Their licenses are listed below:
PyQt6 - GPL v3 - https://riverbankcomputing.com/software/pyqt
manifold3d - Apache 2.0 - https://github.com/elalish/manifold
MeshLib - Apache 2.0 - https://github.com/MeshInspector/MeshLib
NumPy - BSD 3-Clause - https://numpy.org
SciPy - BSD 3-Clause - https://scipy.org
scikit-image - BSD 3-Clause - https://scikit-image.org
PyVista - MIT - https://pyvista.org
PyOpenGL - BSD - http://pyopengl.sourceforge.net
numpy-stl - BSD - https://github.com/WoLpH/numpy-stl

Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.
