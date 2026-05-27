"""Native desktop GUI wrapper for ZohoVideoRenamer.

Built on tkinter so it requires no extra dependencies — Python ships with it.
The GUI is intentionally minimal: pick two folders, pick output, optionally
configure AI naming, hit Start. Under the hood it calls the same CLI code path.

Launch via:
    zoho-video-renamer-gui
    python -m zoho_video_renamer.gui
"""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import Optional


from . import __version__
from . import naming, ui
from .matcher import (
    match_videos_to_stills, pick_canonical_still, scan_stills, scan_videos,
)
from .thumbnailer import (
    batch_extract_video_frames, batch_make_still_thumbs,
    check_ffmpeg, check_ffprobe, safe_id,
)


BG = "#1a1a1d"
PANEL = "#25252a"
PANEL2 = "#2e2e35"
TEXT = "#e8e8ec"
MUTED = "#9a9aa6"
ACCENT = "#d8a14a"
ACCENT_HOVER = "#e6b35a"
GOOD = "#6ec077"
BAD = "#d97a6c"


class FlatButton(tk.Frame):
    """A button rendered as a colored Frame+Label rather than tk.Button.

    Native tk.Button on macOS ignores `bg` and `fg` (it always uses the system
    AppKit button styling), which makes our custom-themed colors invisible.
    This widget bypasses that by using a tk.Label inside a tk.Frame and binding
    click events manually — colors render exactly as specified.
    """
    def __init__(self, parent, text, command, *, bg=ACCENT, fg="#1a1a1d",
                 hover_bg=None, padx=18, pady=10, font=("-apple-system", 13, "bold")):
        super().__init__(parent, bg=bg, cursor="hand2", highlightthickness=0)
        self._bg = bg
        self._hover_bg = hover_bg or self._lighten(bg)
        self._command = command
        self._enabled = True
        self.label = tk.Label(self, text=text, bg=bg, fg=fg, font=font,
                              padx=padx, pady=pady, cursor="hand2")
        self.label.pack()
        for w in (self, self.label):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    @staticmethod
    def _lighten(hex_color):
        """Quick-and-dirty lighten by ~10%."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * 0.12))
        g = min(255, int(g + (255 - g) * 0.12))
        b = min(255, int(b + (255 - b) * 0.12))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_click(self, _event):
        if self._enabled and self._command:
            self._command()

    def _on_enter(self, _event):
        if self._enabled:
            self.configure(bg=self._hover_bg)
            self.label.configure(bg=self._hover_bg)

    def _on_leave(self, _event):
        if self._enabled:
            self.configure(bg=self._bg)
            self.label.configure(bg=self._bg)

    def configure_state(self, enabled: bool, text: str = None):
        self._enabled = enabled
        if text is not None:
            self.label.configure(text=text)
        # Dim when disabled
        if enabled:
            self.configure(bg=self._bg)
            self.label.configure(bg=self._bg, fg="#1a1a1d", cursor="hand2")
            self.configure(cursor="hand2")
        else:
            dim = "#5a5a60"
            self.configure(bg=dim, cursor="arrow")
            self.label.configure(bg=dim, fg="#aaaaaa", cursor="arrow")


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(f"ZohoVideoRenamer {__version__}")
        root.geometry("720x640")
        root.configure(bg=BG)
        root.minsize(680, 600)

        # State
        self.stills_dir = tk.StringVar()
        self.videos_dir = tk.StringVar()
        self.output_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop", "video-rename-review"))
        self.provider = tk.StringVar(value="(none — use existing names)")
        self.api_key = tk.StringVar()
        self.model_override = tk.StringVar()
        self.videos_only = tk.BooleanVar(value=False)
        self.output_mode = tk.StringVar(value="rename (in place)")

        self._build_ui()
        self._check_environment()

    # ---------------------------------------------------------------- layout

    def _build_ui(self):
        pad = {"padx": 16, "pady": 8}

        # Header
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(20, 8))
        tk.Label(hdr, text="ZohoVideoRenamer", bg=BG, fg=ACCENT,
                 font=("-apple-system", 20, "bold")).pack(anchor="w")
        tk.Label(hdr,
                 text="Match videos to source stills, propose names, review, then bulk-rename.",
                 bg=BG, fg=MUTED, font=("-apple-system", 12)).pack(anchor="w", pady=(2, 0))

        # Mode toggle
        mode_row = tk.Frame(self.root, bg=BG)
        mode_row.pack(fill="x", padx=20, pady=(8, 0))
        cb = tk.Checkbutton(mode_row, text="  Videos only (catalog mode — AI names each video by looking at 3 frames)",
                             variable=self.videos_only, bg=BG, fg=TEXT, selectcolor=PANEL2,
                             activebackground=BG, activeforeground=TEXT,
                             font=("-apple-system", 12, "bold"),
                             command=self._on_mode_toggle)
        cb.pack(anchor="w")

        # Folder pickers
        self._stills_row_widgets = self._folder_row("Stills folder", self.stills_dir,
                         "Folder containing source images (PNG, JPG, etc.) — not needed in videos-only mode.")
        self._folder_row("Videos folder", self.videos_dir,
                         "Folder containing the videos to rename.")
        self._folder_row("Output / review folder", self.output_dir,
                         "Where the review UI + undo log go. Will be created if missing.")

        # Output mode (how to apply the renames)
        op_row = tk.Frame(self.root, bg=BG)
        op_row.pack(fill="x", padx=20, pady=(4, 0))
        tk.Label(op_row, text="Apply operation:", bg=BG, fg=TEXT,
                 font=("-apple-system", 12, "bold")).pack(side="left")
        op_menu = ttk.Combobox(op_row, textvariable=self.output_mode, state="readonly",
                               values=["rename (in place)",
                                       "copy (keep originals, new files in new folder)",
                                       "move (originals leave source folder)"],
                               width=50)
        op_menu.pack(side="left", padx=10)

        # AI section
        ai_frame = tk.LabelFrame(self.root, text="  AI naming (optional)  ",
                                  bg=BG, fg=ACCENT, bd=1, relief="solid",
                                  font=("-apple-system", 12, "bold"))
        ai_frame.pack(fill="x", padx=20, pady=(12, 8))

        tk.Label(ai_frame,
                 text="If your stills are already named (e.g. mountain-sunset.png), leave this set to (none).\n"
                      "Otherwise pick a vision API to propose 3-word descriptive names.",
                 bg=BG, fg=MUTED, font=("-apple-system", 11), justify="left").pack(anchor="w", padx=12, pady=(8, 6))

        row = tk.Frame(ai_frame, bg=BG)
        row.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(row, text="Provider:", bg=BG, fg=TEXT, width=12, anchor="w").pack(side="left")
        provider_menu = ttk.Combobox(row, textvariable=self.provider, state="readonly",
                                     values=["(none — use existing names)", "anthropic", "openai"],
                                     width=32)
        provider_menu.pack(side="left", fill="x", expand=True, padx=(4, 0))

        row = tk.Frame(ai_frame, bg=BG)
        row.pack(fill="x", padx=12, pady=(4, 6))
        tk.Label(row, text="API key:", bg=BG, fg=TEXT, width=12, anchor="w").pack(side="left")
        key_entry = tk.Entry(row, textvariable=self.api_key, show="•",
                             bg=PANEL2, fg=TEXT, insertbackground=TEXT, bd=1, relief="solid")
        key_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))

        row = tk.Frame(ai_frame, bg=BG)
        row.pack(fill="x", padx=12, pady=(4, 10))
        tk.Label(row, text="Model:", bg=BG, fg=TEXT, width=12, anchor="w").pack(side="left")
        model_entry = tk.Entry(row, textvariable=self.model_override,
                               bg=PANEL2, fg=TEXT, insertbackground=TEXT, bd=1, relief="solid")
        model_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Label(row, text="(optional override)", bg=BG, fg=MUTED, font=("-apple-system", 10)).pack(side="left", padx=(6, 0))

        # Action row — three buttons reflect the three steps of the flow
        action_row = tk.Frame(self.root, bg=BG)
        action_row.pack(fill="x", padx=20, pady=12)
        self.start_btn = FlatButton(action_row, text="①  Scan + Open Review",
                                     command=self._start, bg=ACCENT, fg="#1a1a1d")
        self.start_btn.pack(side="left")
        FlatButton(action_row, text="②  Open last review",
                    command=self._open_review, bg=PANEL2, fg=TEXT,
                    padx=14, pady=10, font=("-apple-system", 12, "bold")
                    ).pack(side="left", padx=8)
        self.apply_btn = FlatButton(action_row, text="③  Apply Renames",
                                     command=self._apply_renames, bg=GOOD, fg="#0f1a10",
                                     padx=18, pady=10, font=("-apple-system", 13, "bold"))
        self.apply_btn.pack(side="left", padx=4)
        tk.Label(action_row, text="  ① scan & name   →   ② review in browser, click Export   →   ③ rename for real",
                 bg=BG, fg=MUTED, font=("-apple-system", 10)).pack(side="left", padx=10)

        # Log area
        tk.Label(self.root, text="Log:", bg=BG, fg=MUTED,
                 font=("-apple-system", 11)).pack(anchor="w", padx=20)
        log_frame = tk.Frame(self.root, bg=PANEL)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(2, 16))
        self.log = tk.Text(log_frame, bg=PANEL, fg=TEXT, bd=0, font=("Menlo", 11),
                            wrap="word", state="disabled")
        self.log.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        sb = tk.Scrollbar(log_frame, command=self.log.yview)
        sb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=sb.set)

    def _folder_row(self, label: str, var: tk.StringVar, hint: str):
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="x", padx=20, pady=4)
        tk.Label(outer, text=label, bg=BG, fg=TEXT, anchor="w",
                 font=("-apple-system", 12, "bold")).pack(anchor="w")
        row = tk.Frame(outer, bg=BG)
        row.pack(fill="x", pady=(2, 2))
        e = tk.Entry(row, textvariable=var, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                     bd=1, relief="solid")
        e.pack(side="left", fill="x", expand=True)
        FlatButton(row, text="Browse…",
                    command=lambda: self._pick(var),
                    bg=PANEL2, fg=TEXT,
                    padx=14, pady=4, font=("-apple-system", 11, "bold")
                    ).pack(side="left", padx=4)
        tk.Label(outer, text=hint, bg=BG, fg=MUTED, font=("-apple-system", 10),
                 anchor="w").pack(anchor="w")
        return outer

    def _on_mode_toggle(self):
        """Hide/show the stills folder when toggling videos-only mode."""
        if self.videos_only.get():
            self._stills_row_widgets.pack_forget()
        else:
            self._stills_row_widgets.pack(fill="x", padx=20, pady=4, before=None)
            # Re-pack at the right position is tricky with tk; user can scroll if needed.

    def _pick(self, var: tk.StringVar):
        d = filedialog.askdirectory(initialdir=var.get() or os.path.expanduser("~"))
        if d:
            var.set(d)

    # ---------------------------------------------------------------- logic

    def _check_environment(self):
        ffmpeg = check_ffmpeg()
        if ffmpeg:
            if "imageio_ffmpeg" in ffmpeg or "imageio-ffmpeg" in ffmpeg:
                self._log("✓ Using bundled ffmpeg.")
            else:
                self._log(f"✓ Using system ffmpeg: {ffmpeg}")
        else:
            self._log("⚠ ffmpeg not available (neither bundled nor on PATH). Video thumbnails won't generate.")
            self._log("  If you installed via pip and not via the .dmg, `pip install imageio-ffmpeg` or `brew install ffmpeg`.")
        self._log(f"Version: ZohoVideoRenamer {__version__}")
        self._log("")
        self._log("Pick a stills folder and a videos folder, then click Scan.")
        self._log("Tip: if your stills are already nicely named (e.g. mountain-sunset.png),")
        self._log("     leave AI provider as (none) — names will be inherited.")

    def _log(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.root.update_idletasks()

    def _start(self):
        stills = self.stills_dir.get().strip()
        videos = self.videos_dir.get().strip()
        out = self.output_dir.get().strip()
        videos_only = self.videos_only.get()
        if not videos_only and (not stills or not os.path.isdir(stills)):
            messagebox.showerror("Missing folder", "Pick a valid stills folder, or check 'Videos only'.")
            return
        if not videos or not os.path.isdir(videos):
            messagebox.showerror("Missing folder", "Pick a valid videos folder.")
            return
        if not out:
            messagebox.showerror("Missing folder", "Pick an output folder.")
            return

        self.start_btn.configure_state(False, text="Working…")
        t = threading.Thread(target=self._run, args=(stills, videos, out, videos_only), daemon=True)
        t.start()

    def _run(self, stills_dir: str, videos_dir: str, out_dir: str, videos_only: bool = False):
        try:
            self._log("\n" + "=" * 60)
            if videos_only:
                self._log("Videos-only mode (catalog).")
                stills_index = {}
            else:
                self._log("Scanning stills...")
                stills_index = scan_stills(stills_dir, recursive=True)
                self._log(f"  Found {sum(len(v) for v in stills_index.values())} stills across {len(stills_index)} stubs.")

            self._log("Scanning videos...")
            videos = scan_videos(videos_dir, recursive=True)
            self._log(f"  Found {len(videos)} videos.")

            if videos_only:
                from .matcher import scan_videos_only
                matches = scan_videos_only(videos)
                unmatched = []
                self._log(f"  Cataloging {len(matches)} videos as individual entries.")
            else:
                self._log("Matching...")
                matches, unmatched = match_videos_to_stills(stills_index, videos)
                self._log(f"  Matched {len(matches)} stubs, {len(unmatched)} videos unmatched.")

            os.makedirs(os.path.join(out_dir, "thumbs", "stills"), exist_ok=True)
            os.makedirs(os.path.join(out_dir, "thumbs", "videos"), exist_ok=True)

            def picker(stills):
                return pick_canonical_still(stills)

            dataset = ui.matches_to_ui_dataset(
                matches, stills_root=stills_dir or videos_dir, videos_root=videos_dir,
                project_root=out_dir, canonical_picker=picker,
                suggested_names={},
            )
            dataset["mode"] = "videos-only" if videos_only else "stills+videos"
            if not videos_only:
                for entry in dataset["entries"]:
                    if entry.get("canonical_still_rel"):
                        stem = os.path.splitext(os.path.basename(entry["canonical_still_rel"]))[0]
                        cleaned = naming.name_from_still_filename(stem + ".png")
                        if naming.looks_like_descriptive_name(cleaned):
                            entry["suggested_name"] = cleaned

            if videos_only:
                # Extract 3 frames per video (start/mid/end)
                self._log("Extracting 3 frames per video (start/mid/end)...")
                from .thumbnailer import extract_three_frames
                three_frames_dir = os.path.join(out_dir, "thumbs", "video_frames")
                os.makedirs(three_frames_dir, exist_ok=True)
                three_ok = 0
                for e in dataset["entries"]:
                    vid = e["videos"][0]
                    src = next((v.abs_path for v in videos if v.filename == vid["filename"]), None)
                    if not src:
                        continue
                    frames = extract_three_frames(src, three_frames_dir, e["id"])
                    if frames.get("mid"):
                        e["still_thumb"] = os.path.relpath(frames["mid"], out_dir)
                        e["canonical_still_rel"] = e["still_thumb"]
                        three_ok += 1
                    e["_video_frames"] = {k: os.path.relpath(p, out_dir) for k, p in frames.items()}
                self._log(f"  3-frame extraction OK for {three_ok}/{len(dataset['entries'])} videos")

            import json
            with open(os.path.join(out_dir, "matches.json"), "w") as f:
                json.dump(dataset, f, indent=2, default=str)
            self._log("  Wrote matches.json")

            if not videos_only:
                # Generate still thumbnails (from real stills)
                self._log("Generating still thumbnails...")
                still_tasks = []
                for e in dataset["entries"]:
                    if not e["canonical_still_rel"]:
                        continue
                    src = next((s.abs_path for s in stills_index.get(e["stub"], [])
                                if os.path.relpath(s.abs_path, out_dir) == e["canonical_still_rel"]), None)
                    if not src and stills_index.get(e["stub"]):
                        src = stills_index[e["stub"]][0].abs_path
                    if src:
                        still_tasks.append((src, os.path.join(out_dir, e["still_thumb"])))
                ok, fail = batch_make_still_thumbs(still_tasks, max_workers=4)
                self._log(f"  {ok} ok, {fail} failed")

            self._log("Extracting video frames...")
            vid_tasks = []
            for e in dataset["entries"]:
                for v in e["videos"]:
                    src = next((vid.abs_path for vid in videos if vid.filename == v["filename"]), None)
                    if src:
                        vid_tasks.append((src, os.path.join(out_dir, v["thumb"]), 0.5))
            ok, fail = batch_extract_video_frames(vid_tasks, max_workers=4)
            self._log(f"  {ok} ok, {fail} failed")

            # AI naming?
            provider = self.provider.get()
            if provider not in ("(none — use existing names)", "(none)", ""):
                key = self.api_key.get().strip()
                if not key:
                    self._log(f"⚠ AI provider '{provider}' selected but no API key provided. Skipping AI naming.")
                else:
                    self._log(f"Calling {provider} for name suggestions...")
                    try:
                        from .ai import get_client
                        from .ai.base import VIDEO_NAMING_PROMPT
                        client = get_client(provider, api_key=key,
                                            model=self.model_override.get().strip() or None)
                        raw_names: dict = {}
                        if videos_only:
                            # Multi-image: pass all 3 frames per video to the AI
                            items_multi = []
                            for e in dataset["entries"]:
                                if e.get("_video_frames"):
                                    paths = [os.path.join(out_dir, p) for p in e["_video_frames"].values() if p]
                                    paths = [p for p in paths if os.path.exists(p)]
                                    if paths:
                                        items_multi.append((e["id"], paths))
                            if items_multi:
                                raw_names = naming.ai_name_batch_multi(
                                    client, items_multi, prompt=VIDEO_NAMING_PROMPT, max_workers=3,
                                    on_progress=lambda d, t, _id, n: self._log(f"  {d}/{t}: {_id} -> {n}"))
                        else:
                            items = [(e["id"], os.path.join(out_dir, e["still_thumb"]))
                                     for e in dataset["entries"]
                                     if e["still_thumb"] and os.path.exists(os.path.join(out_dir, e["still_thumb"]))]
                            raw_names = naming.ai_name_batch(client, items, max_workers=3,
                                                             on_progress=lambda d, t, _id, n: self._log(f"  {d}/{t}: {_id} -> {n}"))
                        final = naming.disambiguate_names(raw_names)
                        for e in dataset["entries"]:
                            if e["id"] in final:
                                e["suggested_name"] = final[e["id"]]
                        with open(os.path.join(out_dir, "matches.json"), "w") as f:
                            json.dump(dataset, f, indent=2)
                        self._log(f"  Got {len(final)} AI names.")
                    except Exception as e:
                        self._log(f"  AI naming failed: {e}")

            html_path = os.path.join(out_dir, "index.html")
            ui.write_review_html(dataset, html_path)
            self._log(f"Wrote review UI: {html_path}")

            self._log("\n✓ Done. Opening review UI in your browser...")
            webbrowser.open("file://" + html_path)

        except Exception as e:
            self._log(f"\n✗ Error: {e}")
            import traceback
            self._log(traceback.format_exc())
        finally:
            self.root.after(0, lambda: self.start_btn.configure_state(True, text="▶  Scan + Generate Review"))

    def _open_review(self):
        html_path = os.path.join(self.output_dir.get(), "index.html")
        if os.path.exists(html_path):
            webbrowser.open("file://" + html_path)
        else:
            messagebox.showinfo("No review yet", f"No index.html in:\n{self.output_dir.get()}\n\nRun a scan first.")

    def _apply_renames(self):
        """Find the user's exported rename-approvals.json, show a dry-run preview,
        and on confirmation actually rename the files. End-to-end in the app —
        no CLI needed."""
        out_dir = self.output_dir.get().strip()
        if not out_dir or not os.path.isdir(out_dir):
            messagebox.showerror("No project folder", "Pick the output / review folder first.")
            return

        # Look for approvals JSON in: project folder, then ~/Downloads (browser default)
        candidates = [
            os.path.join(out_dir, "rename-approvals.json"),
            os.path.join(os.path.expanduser("~"), "Downloads", "rename-approvals.json"),
        ]
        approvals_path = next((c for c in candidates if os.path.exists(c)), None)
        if not approvals_path:
            approvals_path = filedialog.askopenfilename(
                title="Pick the rename-approvals.json you exported from the review UI",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir=os.path.expanduser("~/Downloads"),
            )
            if not approvals_path:
                return

        # Load matches.json + approvals
        import json
        matches_path = os.path.join(out_dir, "matches.json")
        if not os.path.exists(matches_path):
            messagebox.showerror("Missing data", f"No matches.json in {out_dir}. Run scan first.")
            return
        with open(matches_path) as f:
            dataset = json.load(f)
        with open(approvals_path) as f:
            approvals = json.load(f)

        # Resolve project-relative paths back to absolute (same as cli.cmd_apply)
        by_rel = {}
        for e in dataset["entries"]:
            for v in e["videos"]:
                by_rel[v["rel_path"]] = v["abs_path"]
            for s in e["all_still_files"]:
                by_rel[s["rel_path"]] = s["abs_path"]

        for entry in approvals.get("approved", []):
            for r in entry.get("renames", []):
                if r.get("skip"):
                    continue
                abs_src = by_rel.get(r["from"])
                if abs_src:
                    r["from"] = abs_src
                src_path = r["from"]
                src_dir = os.path.dirname(src_path) if os.path.isabs(src_path) else None
                new_filename = os.path.basename(r["to"])
                if src_dir:
                    r["to"] = os.path.join(src_dir, new_filename)

        from . import apply as apply_mod
        plan = apply_mod.build_plan(approvals, project_root=out_dir)

        # Determine operation from the dropdown
        mode_str = self.output_mode.get()
        if mode_str.startswith("copy"):
            op = "copy"
        elif mode_str.startswith("move"):
            op = "move"
        else:
            op = "rename"

        # Build preview text
        approved_count = len(approvals.get("approved", []))
        lines = [
            f"Source: {approvals_path}",
            f"Approved entries: {approved_count}",
            f"Total file operations: {len(plan.ops)}",
            f"Operation: {op} ({mode_str})",
            "",
        ]
        if plan.collisions:
            lines.append(f"⚠ {len(plan.collisions)} collisions detected (same target file from multiple sources)")
            lines.append("Aborting — fix names in the review UI first.")
            messagebox.showerror("Collisions detected", "\n".join(lines))
            return
        if plan.missing_sources:
            lines.append(f"⚠ {len(plan.missing_sources)} source files not found:")
            for o in plan.missing_sources[:5]:
                lines.append(f"  {o.src}")
            if len(plan.missing_sources) > 5:
                lines.append(f"  ... and {len(plan.missing_sources)-5} more")
            messagebox.showerror("Files missing", "\n".join(lines))
            return

        # Show first 20 ops as preview
        lines.append(f"First {min(20, len(plan.ops))} operations:")
        for o in plan.ops[:20]:
            lines.append(f"  {os.path.basename(o.src)}  →  {os.path.basename(o.dst)}")
        if len(plan.ops) > 20:
            lines.append(f"  ... and {len(plan.ops) - 20} more")

        msg = "\n".join(lines)
        msg += f"\n\nReady to {op} {len(plan.ops)} files. Undo log will be saved in {out_dir}.\n\nProceed?"

        if not messagebox.askyesno(f"Apply {len(plan.ops)} renames?", msg):
            self._log("Apply cancelled by user.")
            return

        self.apply_btn.configure_state(False, text="Working…")
        self._log(f"\n{'='*60}")
        self._log(f"Applying {len(plan.ops)} {op} ops...")

        def _work():
            try:
                ok, failed, undo_path = apply_mod.execute_plan(plan, undo_log_dir=out_dir, operation=op)
                msg2 = f"✓ Renamed: {ok}\n✗ Failed: {failed}\n\nUndo log: {undo_path}"
                if failed == 0:
                    self.root.after(0, lambda: messagebox.showinfo("Done", msg2))
                else:
                    self.root.after(0, lambda: messagebox.showwarning("Done with errors", msg2))
                self._log(msg2)
            except Exception as ex:
                self._log(f"✗ Apply failed: {ex}")
                self.root.after(0, lambda: messagebox.showerror("Apply failed", str(ex)))
            finally:
                self.root.after(0, lambda: self.apply_btn.configure_state(True, text="③  Apply Renames"))

        threading.Thread(target=_work, daemon=True).start()


def main():
    root = tk.Tk()
    try:
        # Set tk theme to dark-ish on macOS
        root.tk.call("tk", "scaling", 1.2)
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
