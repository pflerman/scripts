"""Vista de generación con IA — Títulos, descripciones y prompts Gemini."""

import logging
import os
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from pathlib import Path

from app.config import PRODUCTOS_BASE
from app.models.catalogo import Catalogo
from app.services.ia_generation import (
    generar_titulos,
    generar_descripciones,
    generar_prompts_gemini,
)
from app.ui import theme
from app.ui.components.log_panel import LogPanel
from app.utils.file_helpers import load_json, save_json

logger = logging.getLogger(__name__)


class IAView(tk.Frame):
    """Vista de generación de contenido con Claude AI."""

    def __init__(self, master: tk.Widget, catalogo: Catalogo, **kwargs):
        super().__init__(master, bg=theme.BG_PRIMARY, **kwargs)
        self.catalogo = catalogo
        self._sku_var = tk.StringVar()
        self._processing = False
        self._titulos_generados: list[str] = []
        self._descripciones_generadas: list[str] = []
        self._build()

    def _build(self) -> None:
        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=theme.BG_PRIMARY)
        header.pack(fill="x", padx=20, pady=(20, 8))

        tk.Label(header, text="Inteligencia Artificial", font=theme.FONT_TITLE,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_PRIMARY).pack(side="left")

        # API key status
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        key_text = "API Key: OK" if has_key else "API Key: no configurada"
        key_color = theme.SUCCESS if has_key else theme.ERROR
        tk.Label(header, text=key_text, font=theme.FONT_SMALL,
                 bg=theme.BG_PRIMARY, fg=key_color).pack(side="right")

        # ── Selector de producto ────────────────────────────────────────────
        sel_frame = tk.Frame(self, bg=theme.BG_SECONDARY, bd=1, relief="solid",
                             highlightbackground=theme.BORDER, highlightthickness=1)
        sel_frame.pack(fill="x", padx=20, pady=(0, 8))

        tk.Label(sel_frame, text="Producto:", font=theme.FONT_BOLD,
                 bg=theme.BG_SECONDARY, fg=theme.TEXT_SECONDARY).pack(
            side="left", padx=(10, 4), pady=6)

        skus = self.catalogo.skus
        self._combo = ttk.Combobox(sel_frame, textvariable=self._sku_var,
                                    values=skus, state="readonly", width=30)
        self._combo.pack(side="left", padx=(0, 10), pady=6)
        self._combo.bind("<<ComboboxSelected>>", lambda e: self._on_sku_changed())

        if skus:
            self._combo.current(0)

        # Info del producto
        self._info_label = tk.Label(
            sel_frame, text="", font=theme.FONT_SMALL,
            bg=theme.BG_SECONDARY, fg=theme.TEXT_MUTED)
        self._info_label.pack(side="left", padx=4, pady=6)

        # ── Botones de generación ───────────────────────────────────────────
        btn_frame = tk.Frame(self, bg=theme.BG_PRIMARY)
        btn_frame.pack(fill="x", padx=20, pady=(0, 8))

        tk.Button(
            btn_frame, text="Generar Títulos ML", font=theme.FONT_BOLD,
            bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
            padx=14, pady=4, cursor="hand2",
            command=self._generar_titulos,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            btn_frame, text="Generar Descripciones ML", font=theme.FONT_BOLD,
            bg=theme.BTN_INFO, fg="white", relief="flat", bd=0,
            padx=14, pady=4, cursor="hand2",
            command=self._generar_descripciones,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            btn_frame, text="Generar Prompts Gemini", font=theme.FONT_BOLD,
            bg=theme.BTN_WARNING, fg="white", relief="flat", bd=0,
            padx=14, pady=4, cursor="hand2",
            command=self._generar_prompts,
        ).pack(side="left")

        # ── Área de resultados ──────────────────────────────────────────────
        results_frame = tk.Frame(self, bg=theme.BG_PRIMARY)
        results_frame.pack(fill="both", expand=True, padx=20, pady=(0, 4))

        self._results_text = tk.Text(
            results_frame, height=15, font=theme.FONT_NORMAL,
            bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY, relief="solid",
            bd=1, wrap="word", state="disabled",
        )
        results_scroll = ttk.Scrollbar(results_frame, orient="vertical",
                                        command=self._results_text.yview)
        self._results_text.configure(yscrollcommand=results_scroll.set)
        results_scroll.pack(side="right", fill="y")
        self._results_text.pack(fill="both", expand=True)

        # ── Botones de acción sobre resultados ──────────────────────────────
        action_frame = tk.Frame(self, bg=theme.BG_PRIMARY)
        action_frame.pack(fill="x", padx=20, pady=(0, 4))

        tk.Button(
            action_frame, text="Copiar al portapapeles", font=theme.FONT_SMALL,
            bg=theme.BG_SECONDARY, fg=theme.TEXT_PRIMARY, relief="solid", bd=1,
            padx=8, pady=2, cursor="hand2",
            command=self._copiar_resultado,
        ).pack(side="left", padx=(0, 6))

        self._apply_label = tk.Label(
            action_frame, text="", font=theme.FONT_SMALL,
            bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED)
        self._apply_label.pack(side="left", padx=4)

        # Selector para elegir un resultado específico
        tk.Label(action_frame, text="Elegir N°:", font=theme.FONT_SMALL,
                 bg=theme.BG_PRIMARY, fg=theme.TEXT_SECONDARY).pack(
            side="left", padx=(12, 2))
        self._choice_var = tk.StringVar(value="1")
        ttk.Entry(action_frame, textvariable=self._choice_var, width=4).pack(
            side="left")

        tk.Button(
            action_frame, text="Aplicar título", font=theme.FONT_SMALL,
            bg=theme.BTN_SUCCESS, fg="white", relief="flat", bd=0,
            padx=8, pady=2, cursor="hand2",
            command=self._aplicar_titulo,
        ).pack(side="left", padx=(6, 0))

        tk.Button(
            action_frame, text="Aplicar descripción", font=theme.FONT_SMALL,
            bg=theme.BTN_INFO, fg="white", relief="flat", bd=0,
            padx=8, pady=2, cursor="hand2",
            command=self._aplicar_descripcion,
        ).pack(side="left", padx=(4, 0))

        # ── Status ──────────────────────────────────────────────────────────
        self._status_label = tk.Label(
            self, text="", font=theme.FONT_SMALL,
            bg=theme.BG_PRIMARY, fg=theme.TEXT_MUTED)
        self._status_label.pack(fill="x", padx=20, pady=(0, 6))

        if skus:
            self._on_sku_changed()

    def _on_sku_changed(self) -> None:
        sku = self._sku_var.get()
        if not sku:
            return
        prod = self.catalogo.get(sku)
        if prod:
            info_parts = [prod.nombre]
            if prod.titulo_ml:
                info_parts.append(f"Título: {prod.titulo_ml[:40]}...")
            self._info_label.configure(text=" | ".join(info_parts))

    def _set_result(self, text: str) -> None:
        self._results_text.configure(state="normal")
        self._results_text.delete("1.0", "end")
        self._results_text.insert("1.0", text)
        self._results_text.configure(state="disabled")

    def _copiar_resultado(self) -> None:
        text = self._results_text.get("1.0", "end-1c")
        if text.strip():
            self.clipboard_clear()
            self.clipboard_append(text)
            self._status_label.configure(
                text="Copiado al portapapeles", fg=theme.SUCCESS)

    # ── Generación de títulos ───────────────────────────────────────────────

    def _generar_titulos(self) -> None:
        if self._processing:
            return
        sku = self._sku_var.get()
        if not sku:
            return

        prod = self.catalogo.get(sku)
        if not prod:
            return

        self._processing = True
        self._status_label.configure(
            text="Generando títulos con Claude AI...", fg=theme.INFO)
        self._set_result("Consultando Claude AI...")
        self.update()

        def _worker():
            try:
                titulos = generar_titulos(sku, prod.to_dict())
                self.after(0, lambda: self._on_titulos_ready(sku, titulos))
            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_titulos_ready(self, sku: str, titulos: list[str]) -> None:
        self._processing = False
        self._titulos_generados = titulos

        lines = []
        for i, t in enumerate(titulos, 1):
            chars = len(t)
            status = "OK" if chars <= 60 else "LARGO"
            lines.append(f"{i:2d}. [{chars} chars] [{status}] {t}")

        self._set_result("\n".join(lines))
        self._status_label.configure(
            text=f"{len(titulos)} títulos generados. Elegí uno con 'Aplicar título'.",
            fg=theme.SUCCESS)

        # Save to history
        self._guardar_historial_titulos(sku, titulos)

    def _aplicar_titulo(self) -> None:
        if not self._titulos_generados:
            self._status_label.configure(
                text="Primero generá títulos", fg=theme.WARNING)
            return

        try:
            idx = int(self._choice_var.get()) - 1
            if not (0 <= idx < len(self._titulos_generados)):
                self._status_label.configure(
                    text=f"Número entre 1 y {len(self._titulos_generados)}",
                    fg=theme.ERROR)
                return
        except ValueError:
            self._status_label.configure(
                text="Ingresá un número válido", fg=theme.ERROR)
            return

        titulo = self._titulos_generados[idx]
        sku = self._sku_var.get()
        ok = self.catalogo.actualizar_producto(sku, titulo_ml=titulo)
        if ok:
            self._status_label.configure(
                text=f"Título aplicado: {titulo}", fg=theme.SUCCESS)
        else:
            self._status_label.configure(
                text="Error al guardar título", fg=theme.ERROR)

    def _guardar_historial_titulos(self, sku: str, titulos: list[str]) -> None:
        path = PRODUCTOS_BASE / sku / "inteligencia" / "titulos_generados.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = load_json(path) if path.exists() else {"historial": []}
        except Exception:
            data = {"historial": []}

        data["historial"].append({
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "titulos": [{"titulo": t, "caracteres": len(t)} for t in titulos],
        })
        save_json(path, data)

    # ── Generación de descripciones ─────────────────────────────────────────

    def _generar_descripciones(self) -> None:
        if self._processing:
            return
        sku = self._sku_var.get()
        if not sku:
            return

        prod = self.catalogo.get(sku)
        if not prod:
            return

        self._processing = True
        self._status_label.configure(
            text="Generando descripciones con Claude AI...", fg=theme.INFO)
        self._set_result("Consultando Claude AI...")
        self.update()

        def _worker():
            try:
                descs = generar_descripciones(sku, prod.to_dict())
                self.after(0, lambda: self._on_descripciones_ready(sku, descs))
            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_descripciones_ready(self, sku: str, descripciones: list[str]) -> None:
        self._processing = False
        self._descripciones_generadas = descripciones

        lines = []
        for i, d in enumerate(descripciones, 1):
            chars = len(d)
            status = "OK" if chars <= 1500 else "LARGA"
            lines.append(f"── Versión {i} [{chars} chars] [{status}] ──")
            lines.append(d)
            lines.append("")

        self._set_result("\n".join(lines))
        self._status_label.configure(
            text=f"{len(descripciones)} descripciones generadas. Elegí una con 'Aplicar descripción'.",
            fg=theme.SUCCESS)

        # Save to history
        self._guardar_historial_descripciones(sku, descripciones)

    def _aplicar_descripcion(self) -> None:
        if not self._descripciones_generadas:
            self._status_label.configure(
                text="Primero generá descripciones", fg=theme.WARNING)
            return

        try:
            idx = int(self._choice_var.get()) - 1
            if not (0 <= idx < len(self._descripciones_generadas)):
                self._status_label.configure(
                    text=f"Número entre 1 y {len(self._descripciones_generadas)}",
                    fg=theme.ERROR)
                return
        except ValueError:
            self._status_label.configure(
                text="Ingresá un número válido", fg=theme.ERROR)
            return

        desc = self._descripciones_generadas[idx]
        sku = self._sku_var.get()
        ok = self.catalogo.actualizar_producto(sku, descripcion=desc)
        if ok:
            self._status_label.configure(
                text=f"Descripción {idx + 1} aplicada ({len(desc)} chars)",
                fg=theme.SUCCESS)
        else:
            self._status_label.configure(
                text="Error al guardar descripción", fg=theme.ERROR)

    def _guardar_historial_descripciones(self, sku: str,
                                          descripciones: list[str]) -> None:
        path = PRODUCTOS_BASE / sku / "inteligencia" / "descripciones_generadas.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = load_json(path) if path.exists() else {"historial": []}
        except Exception:
            data = {"historial": []}

        data["historial"].append({
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "descripciones": [
                {"descripcion": d, "caracteres": len(d)} for d in descripciones
            ],
        })
        save_json(path, data)

    # ── Generación de prompts Gemini ────────────────────────────────────────

    def _generar_prompts(self) -> None:
        if self._processing:
            return
        sku = self._sku_var.get()
        if not sku:
            return

        # Find a photo to analyze
        from app.config import IMG_EXTENSIONS
        fotos_dir = PRODUCTOS_BASE / sku / "fotos" / "listas_gemini"
        if not fotos_dir.exists():
            fotos_dir = PRODUCTOS_BASE / sku / "fotos" / "originales"

        fotos = sorted(
            f for f in fotos_dir.iterdir()
            if f.is_file() and f.suffix.lower() in IMG_EXTENSIONS
        ) if fotos_dir.exists() else []

        if not fotos:
            self._status_label.configure(
                text="No hay fotos disponibles para analizar", fg=theme.WARNING)
            return

        foto = fotos[0]  # Use first photo
        self._processing = True
        self._status_label.configure(
            text=f"Analizando {foto.name} con Claude Vision...", fg=theme.INFO)
        self._set_result("Enviando foto a Claude AI...")
        self.update()

        def _worker():
            try:
                prompts = generar_prompts_gemini(sku, foto)
                self.after(0, lambda: self._on_prompts_ready(sku, prompts, foto.name))
            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_prompts_ready(self, sku: str, prompts: list[dict],
                          foto_nombre: str) -> None:
        self._processing = False

        lines = []
        for p in prompts:
            lines.append(f"── #{p.get('id', '?')} — {p.get('ambiente', '?')} ──")
            lines.append(p.get("prompt", ""))
            lines.append("")

        self._set_result("\n".join(lines))
        self._status_label.configure(
            text=f"{len(prompts)} prompts generados desde {foto_nombre}",
            fg=theme.SUCCESS)

        # Save prompts
        self._guardar_prompts(sku, prompts, foto_nombre)

    def _guardar_prompts(self, sku: str, prompts: list[dict],
                         foto_nombre: str) -> None:
        json_path = PRODUCTOS_BASE / sku / f"{sku}.json"
        try:
            datos = load_json(json_path) if json_path.exists() else {}
        except Exception:
            datos = {}

        if "prompts_gemini" not in datos:
            datos["prompts_gemini"] = []

        datos["prompts_gemini"].append({
            "timestamp": datetime.now().isoformat(),
            "foto_origen": foto_nombre,
            "prompts": prompts,
        })
        save_json(json_path, datos)

    # ── Error handler ───────────────────────────────────────────────────────

    def _on_error(self, error: str) -> None:
        self._processing = False
        self._set_result(f"Error: {error}")
        self._status_label.configure(text=f"Error: {error}", fg=theme.ERROR)

    def refresh(self) -> None:
        self.catalogo.reload()
        skus = self.catalogo.skus
        self._combo.configure(values=skus)
        if skus and not self._sku_var.get():
            self._combo.current(0)
        self._on_sku_changed()
