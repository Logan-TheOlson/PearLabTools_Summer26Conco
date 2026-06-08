# Pear Tools

Pear Tools converts measurement files exported by the **Quantum Design VersaLab** (`.DAT`)
into tidy `.CSV` files ready to plot in **Origin 2021**. Every conversion is shown as a live
preview, and the resulting CSV can be dragged straight into an Origin workbook.

Under the hood each module reads the VersaLab header (sample mass + the `[Data]` section) and
converts the raw `Moment (emu)` into mass-normalized `Magnetization (A·m²/kg)`.

## Modules

| Module | VersaLab measurement | Preview |
| --- | --- | --- |
| **Hysteresis** | VSM hysteresis loops | Magnetization vs Field (T) — original & paramagnetic-corrected |
| **Low Temp. 1 Tesla** | Low-temperature sweep (1 T) | Magnetization vs Temperature (K) |
| **Zero Field Cooling** | ZFC / FC measurement | ZFC & FC Magnetization vs Temperature (K) |
| **Room Temp. SIRM** | Room-temperature SIRM | Magnetization vs Temperature (K) |

The **Hysteresis** module additionally lets you enter the temperatures (K) at which to extract
loops (comma-separated), optionally remove the paramagnetic contribution, and reports the
saturation magnetization (Ms), remanent magnetization (Mr), and coercive field (Hc).

## Output

Converted files are written to an **`output/` folder next to the input `.DAT`**, named
`<input-name>_converted.csv`. The app shows the saved path in the status bar and offers the
CSV as a draggable chip you can drop directly onto an Origin 2021 workbook.

## Requirements

- Windows 10 / 11
- Python 3.12
- Dependencies listed in [`requirements.txt`](requirements.txt)

## Run from source

```powershell
# from the project root
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Tkinter ships with Python, so no extra install is needed for the GUI itself.

## Usage

1. Pick a module from the sidebar.
2. **Drag a `.DAT` onto the input field**, or click **Browse**.
3. *(Hysteresis only)* enter the temperature bands and choose whether to remove the
   paramagnetic contribution.
4. Click **Convert & Save**.
5. The status bar reports the row count and saved location. Drag the **CSV** chip into an
   open Origin 2021 workbook.

## Build a standalone `.exe`

```powershell
.\.venv\Scripts\Activate.ps1
pyinstaller --onefile --windowed --name "Pear Tools" --icon=icon.ico --add-data "icon.ico;." main.py
```

The executable is written to `dist\Pear Tools.exe`. Drag-and-drop support (`tkinterdnd2`) is
bundled automatically via `pyinstaller-hooks-contrib`. PyInstaller also generates a
`Pear Tools.spec` you can commit if you want a reproducible recipe. The `build/` and `dist/`
folders are generated output and are git-ignored.

## Project layout

```
main.py                  App shell: window chrome, sidebar, module switching
modules/
  theme.py               Color palette (single source of truth)
  base_gui.py            Shared module UI + conversion workflow
  dat_reader.py          Shared VersaLab .DAT parsing + unit conversion
  drag_file.py           Draggable output-CSV chip
  Hysteresis/            VSM hysteresis        (gui.py + processing.py)
  LT_1T/                 Low Temp. 1 Tesla     (gui.py + processing.py)
  ZFC/                   Zero Field Cooling    (gui.py + processing.py)
  RTSIRM/                Room Temp. SIRM       (gui.py + processing.py)
icon.ico                 Application icon
```
