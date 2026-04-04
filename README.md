# TriplyAM — AM Tools and Lattices

**TriplyAM** is a free, open-source desktop application for generating TPMS and Voronoi lattice infill structures for additive manufacturing. Import any STL or 3MF part, choose a lattice type and parameters, and export a print-ready 3MF in seconds.

![TriplyAM Screenshot](docs/screenshot.png)
<!-- Add a screenshot of the app here -->

---

## Features

- **4 TPMS lattice types** — Gyroid, Schwarz P, Schwarz D, Schoen I-WP
- **2 Voronoi modes** — Voronoi (Random) for organic structure, Voronoi (Structure) with Lloyd relaxation for uniform cells
- **Shell-on or lattice-only** — generate with a solid outer wall or fill the full volume
- **Independent wall thickness** — control wall and infill separately
- **3MF export** — with embedded metadata, license, and generator info
- **STEP export** — via cadquery (falls back to faceted STEP if unavailable)
- **Export debug log** — one-click log export from the Export tab for diagnosis
- **Crash logging** — automatically written to `~/.triply-crash.log` and `~/Downloads/triplyam-crash.log`
- **GPL v3 licensed** — free to use, modify, and distribute under the same license

---

## Platforms

| Platform | Download |
|---|---|
| Linux | AppImage — no installation required |
| Windows | `Triply-Setup.exe` installer |

[**Download the latest release →**](https://github.com/Orville4th/TriplyAM/releases)

---

## Quick Start

1. Download and run the AppImage (Linux) or installer (Windows)
2. Import a part via **File → Import** or drag and drop an STL/3MF
3. Select the part in the Parts tree
4. Go to the **Modify** tab, choose a lattice type and set parameters
5. Click **Generate Lattice**
6. Go to the **Export** tab and export as 3MF

---

## Parameters

| Parameter | Applies to | Description |
|---|---|---|
| Outer wall | Both | Wall thickness in mm. Set to 0 for lattice-only mode |
| Cell size | TPMS | Unit cell size in mm |
| Lattice infill % | TPMS | Target solid volume fraction (20% = ~20% solid, 80% void) |
| Strut diameter | Voronoi | Strut diameter in mm |
| Seed count | Voronoi | Number of Voronoi seed points |
| Resolution | TPMS | Voxel resolution override (Auto recommended) |
| Smoothing passes | Both | Mesh smoothing iterations (2 recommended) |

---

## Building from Source

```bash
git clone https://github.com/Orville4th/TriplyAM.git
cd TriplyAM
pip install -r requirements.txt
python src/main.py
```

### Requirements

- Python 3.11+
- PyQt6
- numpy
- numpy-stl
- scikit-image
- scipy
- manifold3d
- meshlib
- pyvista
- PyOpenGL

---

## License

TriplyAM is licensed under the **GNU General Public License v3 (GPL v3)**.

You are free to use, modify, and distribute this software. Any modified version you distribute must also be licensed under GPL v3 and include the full source code.

See the [LICENSE](LICENSE) file or [gnu.org/licenses/gpl-3.0](https://www.gnu.org/licenses/gpl-3.0.html) for full terms.

---

## Third-Party Libraries

TriplyAM is built on the following open-source libraries. Their licenses are listed below:

| Library | License | Link |
|---|---|---|
| PyQt6 | GPL v3 | https://riverbankcomputing.com/software/pyqt |
| manifold3d | Apache 2.0 | https://github.com/elalish/manifold |
| MeshLib | Apache 2.0 | https://github.com/MeshInspector/MeshLib |
| NumPy | BSD 3-Clause | https://numpy.org |
| SciPy | BSD 3-Clause | https://scipy.org |
| scikit-image | BSD 3-Clause | https://scikit-image.org |
| PyVista | MIT | https://pyvista.org |
| PyOpenGL | BSD | http://pyopengl.sourceforge.net |
| numpy-stl | BSD | https://github.com/WoLpH/numpy-stl |

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## Contact

**Orville Wright IV**
[orville@titan3d.xyz](mailto:orville@titan3d.xyz)
[titan3d.xyz](https://www.titan3d.xyz)

---

## Related Projects

- [MakerPrice](https://play.google.com/store/apps/details?id=com.mrwright.makerprice) — pricing app for makers (Android, iOS, Web)
- [3dprint.com Articles](https://3dprint.com/author/orville-wright-iv/) — published AM articles
