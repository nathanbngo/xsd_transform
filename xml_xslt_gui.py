#!/usr/bin/env python3
"""
XML + XSLT transform desktop app (no browser/JS).
Uses lxml (libxslt) for XSLT 1.0 — same class of engine as the browser app.
"""

import io
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from lxml import etree

OUTPUT_RENDER_LIMIT = 500_000


def normalize_input(s: str) -> str:
    if not s:
        return s
    if s.startswith("\ufeff"):
        return s[1:]
    return s


def pretty_xml_bytes(xml_bytes: bytes) -> str:
    """Pretty-print XML for display; fallback to decoded bytes on failure."""
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.parse(io.BytesIO(xml_bytes), parser).getroot()
        return etree.tostring(
            root, encoding="unicode", pretty_print=True
        )
    except Exception:
        return xml_bytes.decode("utf-8", errors="replace")


def transform(source_xml: str, xslt_str: str) -> tuple[str, str]:
    """
    Returns (output_string, suggested_extension_without_dot).
    Raises ValueError with user-facing message on failure.
    """
    source_xml = normalize_input(source_xml)
    xslt_str = normalize_input(xslt_str)
    if not source_xml.strip():
        raise ValueError("Please provide source XML to transform.")
    if not xslt_str.strip():
        raise ValueError("Please provide an XSLT stylesheet.")

    try:
        source_doc = etree.parse(
            io.BytesIO(source_xml.encode("utf-8")),
            etree.XMLParser(encoding="utf-8"),
        )
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Source XML: {e}") from e

    try:
        xslt_doc = etree.parse(
            io.BytesIO(xslt_str.encode("utf-8")),
            etree.XMLParser(encoding="utf-8"),
        )
    except etree.XMLSyntaxError as e:
        raise ValueError(f"XSLT: {e}") from e

    try:
        transform_fn = etree.XSLT(xslt_doc)
    except etree.XSLTParseError as e:
        raise ValueError(
            "Stylesheet rejected (invalid XSLT 1.0 or unsupported). "
            "XSLT 2.0/3.0 is not supported — use Saxon for those."
        ) from e

    try:
        result_tree = transform_fn(source_doc)
    except etree.XSLTApplyError as e:
        raise ValueError(f"Transform failed: {e}") from e

    # lxml returns _XSLTResultTree; serialize to string
    if hasattr(result_tree, "getroot") and result_tree.getroot() is not None:
        root = result_tree.getroot()
        ns = root.nsmap.get(None) if hasattr(root, "nsmap") else None
        tag = etree.QName(root).localname.lower()
        is_html = tag == "html" and (
            root.nsmap.get(None) == "http://www.w3.org/1999/xhtml"
            or (not root.nsmap or "html" in tag)
        )
        # Serialize
        out_bytes = etree.tostring(
            result_tree, encoding="utf-8", xml_declaration=True, pretty_print=True
        )
        out_str = out_bytes.decode("utf-8").strip()
        if not out_str:
            raise ValueError(
                "Transform produced empty output. Ensure your XSLT builds a single root element."
            )
        ext = "html" if is_html else "xml"
        return out_str, ext

    # Fragment / text-only edge cases
    if isinstance(result_tree, str):
        return result_tree, "txt"

    try:
        out_bytes = etree.tostring(
            result_tree,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )
    except Exception:
        out_bytes = etree.tostring(result_tree, encoding="utf-8")
    out_str = out_bytes.decode("utf-8").strip()
    if not out_str:
        raise ValueError(
            "Transform produced empty output. Ensure your XSLT builds a single root element, "
            "or use method=\"xml\"/\"html\"."
        )
    return out_str, "xml"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("XML Transform — XSLT 1.0")
        self.geometry("1280x820")
        self.minsize(900, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._full_output = ""
        self._output_ext = "xml"
        self._last_xml_path: str | None = None
        self._last_xslt_path: str | None = None
        self._find_bar = None
        self._find_after_id = None

        self._build_ui()
        self._setup_find_bindings()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=("gray90", "gray17"))
        header.pack(fill="x", padx=0, pady=0)
        title = ctk.CTkLabel(
            header,
            text="XML → XSLT Transform",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        )
        title.pack(side="left", padx=20, pady=14)
        badge = ctk.CTkLabel(
            header,
            text="  XSLT 1.0  ",
            font=ctk.CTkFont(size=12),
            fg_color=("gray70", "gray35"),
            corner_radius=6,
        )
        badge.pack(side="left", pady=14)
        subtitle = ctk.CTkLabel(
            header,
            text="Source XML + stylesheet → formatted preview → save file",
            font=ctk.CTkFont(size=13),
            text_color="gray60",
        )
        subtitle.pack(side="right", padx=20, pady=14)

        paned = ctk.CTkFrame(self, fg_color="transparent")
        paned.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # Left: inputs
        left = ctk.CTkFrame(paned, fg_color=("gray95", "gray20"), corner_radius=12)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        ctk.CTkLabel(
            left, text="Source XML", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=12, pady=(12, 4))
        xml_row = ctk.CTkFrame(left, fg_color="transparent")
        xml_row.pack(fill="x", padx=12)
        self.xml_text = ctk.CTkTextbox(
            left, font=ctk.CTkFont(family="Consolas", size=12), wrap="none"
        )
        self.xml_text.pack(fill="both", expand=True, padx=12, pady=(4, 8))
        self.btn_reload_xml = ctk.CTkButton(
            xml_row, text="Reload", width=72, command=self._reload_xml, state="disabled"
        )
        self.btn_reload_xml.pack(side="right", padx=(0, 6))
        ctk.CTkButton(
            xml_row, text="Browse XML…", width=110, command=self._load_xml
        ).pack(side="right")

        ctk.CTkLabel(
            left, text="XSLT stylesheet", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=12, pady=(8, 4))
        xslt_row = ctk.CTkFrame(left, fg_color="transparent")
        xslt_row.pack(fill="x", padx=12)
        self.xslt_text = ctk.CTkTextbox(
            left, font=ctk.CTkFont(family="Consolas", size=12), wrap="none"
        )
        self.xslt_text.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.btn_reload_xslt = ctk.CTkButton(
            xslt_row, text="Reload", width=72, command=self._reload_xslt, state="disabled"
        )
        self.btn_reload_xslt.pack(side="right", padx=(0, 6))
        ctk.CTkButton(
            xslt_row, text="Browse XSLT…", width=110, command=self._load_xslt
        ).pack(side="right")

        toolbar = ctk.CTkFrame(left, fg_color="transparent")
        toolbar.pack(fill="x", padx=12, pady=(0, 12))
        self.btn_run = ctk.CTkButton(
            toolbar,
            text="Run transformation",
            width=160,
            height=36,
            font=ctk.CTkFont(weight="bold"),
            command=self._run_transform,
        )
        self.btn_run.pack(side="left", padx=(0, 8))
        ctk.CTkButton(toolbar, text="Clear all", width=100, command=self._clear_all).pack(
            side="left", padx=4
        )
        ctk.CTkButton(
            toolbar, text="Load sample", width=100, command=self._load_sample
        ).pack(side="left", padx=4)
        self.btn_reload_all = ctk.CTkButton(
            toolbar,
            text="Reload files",
            width=100,
            command=self._reload_all_files,
            state="disabled",
        )
        self.btn_reload_all.pack(side="left", padx=4)

        self.error_label = ctk.CTkLabel(
            left, text="", text_color="#e74c3c", font=ctk.CTkFont(size=12)
        )
        self.error_label.pack(anchor="w", padx=12, pady=(0, 8))

        # Right: output
        right = ctk.CTkFrame(paned, fg_color=("gray95", "gray20"), corner_radius=12)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        out_header = ctk.CTkFrame(right, fg_color="transparent")
        out_header.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            out_header,
            text="Output (formatted)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        self.meta_label = ctk.CTkLabel(
            out_header, text="", text_color="gray55", font=ctk.CTkFont(size=11)
        )
        self.meta_label.pack(side="left", padx=12)

        out_btns = ctk.CTkFrame(right, fg_color="transparent")
        out_btns.pack(fill="x", padx=12, pady=(0, 4))
        self.btn_copy = ctk.CTkButton(
            out_btns,
            text="Copy",
            width=80,
            command=self._copy_output,
            state="disabled",
        )
        self.btn_copy.pack(side="right", padx=(4, 0))
        self.btn_save = ctk.CTkButton(
            out_btns,
            text="Save / Download…",
            width=140,
            fg_color=("#1f538d", "#14375e"),
            command=self._save_output,
            state="disabled",
        )
        self.btn_save.pack(side="right")

        self.output_text = ctk.CTkTextbox(
            right,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="none",
            state="disabled",
        )
        self.output_text.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        self.placeholder = ctk.CTkLabel(
            right,
            text="Run a transformation to see output here.\n\nDownload always saves the full result;\nvery large output is truncated in the preview only.",
            text_color="gray50",
            font=ctk.CTkFont(size=13),
        )
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _load_xml(self):
        path = filedialog.askopenfilename(
            title="Open source XML",
            filetypes=[
                ("XML", "*.xml"),
                ("All", "*.*"),
            ],
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    self.xml_text.delete("1.0", "end")
                    self.xml_text.insert("1.0", normalize_input(f.read()))
                self._last_xml_path = path
                self.btn_reload_xml.configure(state="normal")
                self._update_reload_all_state()
                self.error_label.configure(text="")
            except Exception as e:
                messagebox.showerror("Error", f"Could not read file: {e}")

    def _load_xslt(self):
        path = filedialog.askopenfilename(
            title="Open XSLT",
            filetypes=[
                ("XSLT", "*.xsl *.xslt *.xml"),
                ("All", "*.*"),
            ],
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    self.xslt_text.delete("1.0", "end")
                    self.xslt_text.insert("1.0", normalize_input(f.read()))
                self._last_xslt_path = path
                self.btn_reload_xslt.configure(state="normal")
                self._update_reload_all_state()
                self.error_label.configure(text="")
            except Exception as e:
                messagebox.showerror("Error", f"Could not read file: {e}")

    def _clear_all(self):
        self.xml_text.delete("1.0", "end")
        self.xslt_text.delete("1.0", "end")
        self._set_output("", "")
        self._last_xml_path = None
        self._last_xslt_path = None
        self.btn_reload_xml.configure(state="disabled")
        self.btn_reload_xslt.configure(state="disabled")
        self.btn_reload_all.configure(state="disabled")
        self.error_label.configure(text="")

    def _load_sample(self):
        sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<root>
  <item id="1">Hello</item>
  <item id="2">World</item>
</root>"""
        sample_xslt = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="xml" encoding="UTF-8" indent="yes"/>
  <xsl:template match="/">
    <out>
      <xsl:for-each select="//item">
        <line><xsl:value-of select="."/></line>
      </xsl:for-each>
    </out>
  </xsl:template>
</xsl:stylesheet>"""
        self.xml_text.delete("1.0", "end")
        self.xml_text.insert("1.0", sample_xml)
        self.xslt_text.delete("1.0", "end")
        self.xslt_text.insert("1.0", sample_xslt)
        self._last_xml_path = None
        self._last_xslt_path = None
        self.btn_reload_xml.configure(state="disabled")
        self.btn_reload_xslt.configure(state="disabled")
        self.btn_reload_all.configure(state="disabled")
        self.error_label.configure(text="")

    def _update_reload_all_state(self):
        if self._last_xml_path or self._last_xslt_path:
            self.btn_reload_all.configure(state="normal")
        else:
            self.btn_reload_all.configure(state="disabled")

    def _reload_xml(self):
        if not self._last_xml_path:
            return
        try:
            with open(self._last_xml_path, "r", encoding="utf-8-sig") as f:
                self.xml_text.delete("1.0", "end")
                self.xml_text.insert("1.0", normalize_input(f.read()))
            self.error_label.configure(
                text=f"Reloaded XML: {self._last_xml_path}", text_color="gray60"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not reload XML: {e}")

    def _reload_xslt(self):
        if not self._last_xslt_path:
            return
        try:
            with open(self._last_xslt_path, "r", encoding="utf-8-sig") as f:
                self.xslt_text.delete("1.0", "end")
                self.xslt_text.insert("1.0", normalize_input(f.read()))
            self.error_label.configure(
                text=f"Reloaded XSLT: {self._last_xslt_path}", text_color="gray60"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not reload XSLT: {e}")

    def _reload_all_files(self):
        self._reload_xml()
        self._reload_xslt()
        if self._last_xml_path and self._last_xslt_path:
            self.error_label.configure(text="Reloaded both files from disk.", text_color="gray60")

    def _run_transform(self):
        self.error_label.configure(text="")
        self.btn_run.configure(state="disabled")
        self.update_idletasks()
        try:
            out, ext = transform(
                self.xml_text.get("1.0", "end"),
                self.xslt_text.get("1.0", "end"),
            )
            # Pretty-print again for display when XML
            if ext == "xml" and out.strip().startswith("<"):
                try:
                    out_display = pretty_xml_bytes(out.encode("utf-8"))
                except Exception:
                    out_display = out
            else:
                out_display = out
            self._full_output = out
            self._output_ext = ext
            self._set_output(out_display, ext)
        except ValueError as e:
            self.error_label.configure(text=str(e))
            self._set_output("", "")
        finally:
            self.btn_run.configure(state="normal")

    def _set_output(self, text: str, ext: str):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        if not text:
            self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
            self.meta_label.configure(text="")
            self.btn_copy.configure(state="disabled")
            self.btn_save.configure(state="disabled")
        else:
            self.placeholder.place_forget()
            display = text
            if len(text) > OUTPUT_RENDER_LIMIT:
                display = (
                    text[:OUTPUT_RENDER_LIMIT]
                    + f"\n\n… truncated for display ({len(text):,} chars). Save to get the full file."
                )
            self.output_text.insert("1.0", display)
            lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
            self.meta_label.configure(
                text=f"{lines:,} lines · {len(text):,} chars · .{ext}"
            )
            self.btn_copy.configure(state="normal")
            self.btn_save.configure(state="normal")
        self.output_text.configure(state="disabled")

    def _copy_output(self):
        if not self._full_output:
            return
        self.clipboard_clear()
        self.clipboard_append(self._full_output)
        self.error_label.configure(text="Copied to clipboard.", text_color="gray60")

    def _save_output(self):
        if not self._full_output:
            return
        ext = self._output_ext
        path = filedialog.asksaveasfilename(
            title="Save output",
            defaultextension=f".{ext}",
            filetypes=[
                (ext.upper(), f"*.{ext}"),
                ("All", "*.*"),
            ],
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(self._full_output)
                self.error_label.configure(
                    text=f"Saved: {path}", text_color="gray60"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Could not save: {e}")

    # --- Find (Ctrl+F) for XML / XSLT / output text panes ---
    def _get_inner_text(self, ctk_textbox):
        """Return underlying tk Text widget for CTkTextbox."""
        return getattr(ctk_textbox, "_textbox", ctk_textbox)

    def _find_target_widget(self):
        """Which text pane has focus (or contains focus)."""
        focus = self.focus_get()
        for name, tb in (
            ("xml", self.xml_text),
            ("xslt", self.xslt_text),
            ("output", self.output_text),
        ):
            inner = self._get_inner_text(tb)
            try:
                if focus == inner or focus == tb:
                    return tb
                w = focus
                while w:
                    if w == inner:
                        return tb
                    w = getattr(w, "master", None)
            except Exception:
                pass
        return self.xml_text

    def _setup_find_bindings(self):
        # Ctrl+F open find; Ctrl+G / F3 find next
        self.bind_all("<Control-f>", lambda e: self._find_show() or "break")
        self.bind_all("<Control-F>", lambda e: self._find_show() or "break")
        self.bind_all("<F3>", lambda e: self._find_next() or "break")
        self.bind_all("<Control-g>", lambda e: self._find_next() or "break")
        self.bind_all("<Control-G>", lambda e: self._find_next() or "break")

    def _find_show(self):
        if self._find_bar and self._find_bar.winfo_exists():
            self._find_bar.lift()
            self._find_entry.focus_set()
            return "break"
        self._find_bar = ctk.CTkToplevel(self)
        self._find_bar.title("Find")
        self._find_bar.geometry("420x120")
        self._find_bar.resizable(False, False)
        self._find_bar.attributes("-topmost", True)
        frame = ctk.CTkFrame(self._find_bar, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(frame, text="Find in current pane (XML / XSLT / Output):").pack(
            anchor="w"
        )
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", pady=(8, 4))
        self._find_var = tk.StringVar(self)
        self._find_entry = ctk.CTkEntry(row, textvariable=self._find_var, width=220)
        self._find_entry.pack(side="left", padx=(0, 8))
        self._find_entry.bind("<Return>", lambda e: self._find_next())
        ctk.CTkButton(row, text="Find next", width=90, command=self._find_next).pack(
            side="left", padx=4
        )
        ctk.CTkButton(row, text="Close", width=70, command=self._find_close).pack(
            side="left", padx=4
        )
        self._find_status = ctk.CTkLabel(
            frame, text="Ctrl+G / F3 — next match", text_color="gray55", font=ctk.CTkFont(size=11)
        )
        self._find_status.pack(anchor="w", pady=(4, 0))
        self._find_bar.protocol("WM_DELETE_WINDOW", self._find_close)
        self._find_bar.bind("<Escape>", lambda e: self._find_close())
        self._find_entry.focus_set()
        return "break"

    def _find_close(self):
        if self._find_bar and self._find_bar.winfo_exists():
            self._find_bar.destroy()
        self._find_bar = None

    def _find_next(self):
        query = (self._find_var.get() if self._find_var else "").strip()
        if not query:
            if self._find_status:
                self._find_status.configure(text="Enter text to find.")
            return "break"
        tb = self._find_target_widget()
        inner = self._get_inner_text(tb)
        # Output may be disabled — enable temporarily for search/highlight
        was_disabled = str(inner.cget("state")) == "disabled"
        if was_disabled:
            inner.configure(state="normal")
        try:
            inner.tag_delete("find_match", "1.0", "end")
            inner.tag_configure("find_match", background="#4a6741", foreground="white")
            start = inner.index("insert")
            # If selection at start, search after it
            try:
                if inner.compare(inner.index("sel.first"), "==", start):
                    start = inner.index("sel.last")
            except tk.TclError:
                pass
            pos = inner.search(query, start, stopindex="end", nocase=True, regexp=False)
            if not pos:
                pos = inner.search(query, "1.0", stopindex=start, nocase=True, regexp=False)
            if not pos:
                if self._find_status:
                    self._find_status.configure(text="No match.")
                return "break"
            end = f"{pos}+{len(query)}c"
            inner.mark_set("insert", pos)
            inner.see(pos)
            inner.tag_remove("sel", "1.0", "end")
            inner.tag_add("find_match", pos, end)
            inner.tag_add("sel", pos, end)
            inner.focus_set()
            if self._find_status:
                self._find_status.configure(text=f"Match at {pos}  —  Ctrl+G / F3 for next")
        finally:
            if was_disabled:
                inner.configure(state="disabled")
        return "break"


if __name__ == "__main__":
    app = App()
    app.mainloop()
