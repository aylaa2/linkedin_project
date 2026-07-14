import csv
import re
import threading
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import requests


API_URL = "http://127.0.0.1:8001/api/discover"


SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "sql",
    "machine learning", "deep learning", "nlp", "computer vision",
    "pytorch", "tensorflow", "scikit-learn", "langchain", "llm",
    "rag", "fastapi", "flask", "django", "react", "angular",
    "spring boot", "microservices", "docker", "kubernetes",
    "aws", "azure", "gcp", "postgresql", "mysql", "mongodb",
    "git", "api", "rest", "data processing"
]


JOB_TITLES = [
    "ai developer", "junior ai developer", "machine learning engineer",
    "data scientist", "backend developer", "java developer",
    "python developer", "software engineer", "full stack developer"
]


class TalentScoutApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TalentScout AI")
        self.geometry("1440x900")
        self.minsize(1180, 760)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.candidates = []
        self.detected_info = {}

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_sidebar()
        self._build_main_area()
        self._build_right_panel()

    # ---------------- UI BUILDERS ----------------

    def _build_topbar(self):
        self.topbar = ctk.CTkFrame(self, height=64, corner_radius=0)
        self.topbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.topbar.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            self.topbar,
            text="TalentScout AI",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title.grid(row=0, column=0, padx=24, pady=16, sticky="w")

        subtitle = ctk.CTkLabel(
            self.topbar,
            text="AI-assisted candidate sourcing from Job Descriptions",
            text_color=("gray35", "gray70"),
            font=ctk.CTkFont(size=13)
        )
        subtitle.grid(row=0, column=1, padx=10, pady=16, sticky="w")

        self.theme_switch = ctk.CTkSwitch(
            self.topbar,
            text="Dark mode",
            command=self.toggle_theme
        )
        self.theme_switch.select()
        self.theme_switch.grid(row=0, column=2, padx=20, pady=16)

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        logo = ctk.CTkLabel(
            self.sidebar,
            text="TS",
            width=58,
            height=58,
            corner_radius=18,
            fg_color="#2563EB",
            font=ctk.CTkFont(size=23, weight="bold")
        )
        logo.pack(pady=(32, 10))

        app_name = ctk.CTkLabel(
            self.sidebar,
            text="Candidate Search",
            font=ctk.CTkFont(size=17, weight="bold")
        )
        app_name.pack(pady=(0, 28))

        new_search_btn = ctk.CTkButton(
            self.sidebar,
            text="●  New Search",
            height=46,
            corner_radius=14,
            anchor="w",
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            text_color="white",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        new_search_btn.pack(fill="x", padx=20, pady=(0, 18))

        export_card = ctk.CTkFrame(
            self.sidebar,
            corner_radius=18,
            fg_color=("#DCFCE7", "#143A24")
        )
        export_card.pack(fill="x", padx=18, pady=(10, 18))

        ctk.CTkLabel(
            export_card,
            text="Export shortlist",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=("#14532D", "#DCFCE7")
        ).pack(anchor="w", padx=16, pady=(16, 4))

        ctk.CTkLabel(
            export_card,
            text="Download the current candidate results as a CSV file.",
            wraplength=170,
            justify="left",
            text_color=("#166534", "#BBF7D0"),
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=16, pady=(0, 12))

        self.export_btn_sidebar = ctk.CTkButton(
            export_card,
            text="⬇  Export CSV",
            height=46,
            corner_radius=14,
            fg_color="#16A34A",
            hover_color="#15803D",
            text_color="white",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.export_csv
        )
        self.export_btn_sidebar.pack(fill="x", padx=14, pady=(0, 16))

        hint_card = ctk.CTkFrame(
            self.sidebar,
            corner_radius=16,
            fg_color=("gray88", "#1E293B")
        )
        hint_card.pack(fill="x", padx=18, pady=(8, 0))

        ctk.CTkLabel(
            hint_card,
            text="How it works",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            hint_card,
            text="Paste a JD, search candidates, then export the results.",
            wraplength=170,
            justify="left",
            text_color=("gray35", "gray70"),
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=16, pady=(0, 14))

        bottom = ctk.CTkLabel(
            self.sidebar,
            text="Local UI connected to\nFastAPI backend",
            justify="left",
            text_color=("gray40", "gray65"),
            font=ctk.CTkFont(size=12)
        )
        bottom.pack(side="bottom", padx=20, pady=24, anchor="w")

    def _build_main_area(self):
        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray95", "#0F172A"))
        self.main.grid(row=1, column=1, sticky="nsew")
        self.main.grid_rowconfigure(0, weight=0)
        self.main.grid_rowconfigure(1, weight=0)
        self.main.grid_rowconfigure(2, weight=0)
        self.main.grid_rowconfigure(3, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 10))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="AI Job Description Chat",
            font=ctk.CTkFont(size=26, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Paste a JD, extract relevant keywords, search public profiles, then export the shortlist.",
            text_color=("gray35", "gray70"),
            font=ctk.CTkFont(size=14)
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        input_card = ctk.CTkFrame(self.main, corner_radius=20)
        input_card.grid(row=1, column=0, sticky="ew", padx=28, pady=12)
        input_card.grid_columnconfigure(0, weight=1)

        self.jd_textbox = ctk.CTkTextbox(
            input_card,
            height=170,
            corner_radius=14,
            border_width=1,
            font=ctk.CTkFont(size=14)
        )
        self.jd_textbox.grid(row=0, column=0, columnspan=5, sticky="ew", padx=18, pady=(18, 12))
        self.jd_textbox.insert(
            "1.0",
            "We are looking for a Junior AI Developer to join our team in Bucharest. "
            "The ideal candidate should have basic knowledge of Python, machine learning, NLP, APIs and data processing. "
            "Experience with PyTorch, scikit-learn or LangChain is a plus. Work mode: hybrid."
        )

        self.location_entry = ctk.CTkEntry(input_card, placeholder_text="Location e.g. Bucharest", height=42)
        self.location_entry.grid(row=1, column=0, sticky="ew", padx=(18, 8), pady=(0, 18))
        self.location_entry.insert(0, "Bucharest")

        self.max_hits_entry = ctk.CTkEntry(input_card, placeholder_text="Profiles", width=100, height=42)
        self.max_hits_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=(0, 18))
        self.max_hits_entry.insert(0, "5")

        self.clear_btn = ctk.CTkButton(
            input_card,
            text="Clear",
            width=90,
            height=42,
            fg_color="transparent",
            border_width=1,
            text_color=("gray20", "gray80"),
            command=self.clear_input
        )
        self.clear_btn.grid(row=1, column=2, padx=8, pady=(0, 18))

        self.search_btn = ctk.CTkButton(
            input_card,
            text="Search candidates",
            width=190,
            height=42,
            corner_radius=12,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            text_color="white",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_search
        )
        self.search_btn.grid(row=1, column=3, padx=(8, 18), pady=(0, 18))

        results_header = ctk.CTkFrame(self.main, fg_color="transparent")
        results_header.grid(row=2, column=0, sticky="new", padx=28, pady=(8, 0))
        results_header.grid_columnconfigure(0, weight=1)

        self.results_title = ctk.CTkLabel(
            results_header,
            text="Results",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.results_title.grid(row=0, column=0, sticky="w")

        self.status_label = ctk.CTkLabel(
            results_header,
            text="Ready. Add a Job Description and press Search candidates.",
            text_color=("gray40", "gray65")
        )
        self.status_label.grid(row=1, column=0, sticky="w", pady=(2, 8))

        self.results_frame = ctk.CTkScrollableFrame(self.main, corner_radius=18)
        self.results_frame.grid(row=3, column=0, sticky="nsew", padx=28, pady=(8, 24))
        self.results_frame.grid_columnconfigure(0, weight=1)

        self._show_empty_results()

    def _build_right_panel(self):
        self.right_shell = ctk.CTkFrame(self, width=370, corner_radius=0)
        self.right_shell.grid(row=1, column=2, sticky="nsew")
        self.right_shell.grid_propagate(False)
        self.right_shell.grid_rowconfigure(0, weight=1)
        self.right_shell.grid_columnconfigure(0, weight=1)

        self.right = ctk.CTkScrollableFrame(
            self.right_shell,
            width=350,
            corner_radius=0,
            fg_color=("gray92", "#262626")
        )
        self.right.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(
            self.right,
            text="Extracted Information",
            font=ctk.CTkFont(size=19, weight="bold")
        ).pack(anchor="w", padx=22, pady=(26, 4))

        ctk.CTkLabel(
            self.right,
            text="Preview of the important data detected from the JD.",
            text_color=("gray40", "gray65"),
            wraplength=290,
            justify="left"
        ).pack(anchor="w", padx=22, pady=(0, 16))

        self.info_container = ctk.CTkFrame(self.right, corner_radius=18)
        self.info_container.pack(fill="x", padx=18, pady=(0, 18))

        self.role_label = self._info_row("Role", "—")
        self.seniority_label = self._info_row("Seniority", "—")
        self.location_label = self._info_row("Location", "—")

        ctk.CTkLabel(
            self.info_container,
            text="Skills",
            text_color=("gray35", "gray70"),
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=16, pady=(12, 4))

        self.skills_box = ctk.CTkFrame(self.info_container, fg_color="transparent")
        self.skills_box.pack(fill="x", padx=12, pady=(0, 14))

        ctk.CTkLabel(
            self.right,
            text="Candidate Search Process",
            font=ctk.CTkFont(size=19, weight="bold")
        ).pack(anchor="w", padx=22, pady=(8, 10))

        self.process_container = ctk.CTkFrame(self.right, corner_radius=18)
        self.process_container.pack(fill="x", padx=18, pady=(0, 18))

        self.process_steps = []

        steps = [
            "1. JD input received",
            "2. LLM extracts role, seniority, skills and location",
            "3. Search queries are generated",
            "4. SERP search is executed",
            "5. LinkedIn URLs are collected",
            "6. Duplicate profiles are removed",
            "7. Candidate data is extracted",
            "8. Skills are matched with the JD",
            "9. Candidates are scored",
            "10. Results are ready for export"
        ]

        for step in steps:
            label = ctk.CTkLabel(
                self.process_container,
                text=f"○  {step}",
                anchor="w",
                justify="left",
                wraplength=285,
                height=36,
                text_color=("gray35", "gray70"),
                font=ctk.CTkFont(size=13)
            )
            label.pack(fill="x", padx=16, pady=4)
            self.process_steps.append(label)

    def _info_row(self, label, value):
        ctk.CTkLabel(
            self.info_container,
            text=label,
            text_color=("gray35", "gray70"),
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=16, pady=(12, 2))

        value_label = ctk.CTkLabel(
            self.info_container,
            text=value,
            anchor="w",
            justify="left",
            wraplength=275,
            font=ctk.CTkFont(size=14)
        )
        value_label.pack(anchor="w", padx=16, pady=(0, 2))
        return value_label

    # ---------------- ACTIONS ----------------

    def toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("dark")
            self.theme_switch.configure(text="Dark mode")
        else:
            ctk.set_appearance_mode("light")
            self.theme_switch.configure(text="Light mode")

    def clear_input(self):
        self.jd_textbox.delete("1.0", "end")
        self.location_entry.delete(0, "end")
        self.max_hits_entry.delete(0, "end")
        self.max_hits_entry.insert(0, "5")
        self.candidates = []
        self.detected_info = {}
        self.update_detected_panel({})
        self.reset_process()
        self._show_empty_results()
        self.status_label.configure(text="Ready. Add a Job Description and press Search candidates.")

    def start_search(self):
        jd = self.jd_textbox.get("1.0", "end").strip()
        location = self.location_entry.get().strip()

        try:
            max_hits = int(self.max_hits_entry.get().strip())
        except ValueError:
            messagebox.showerror("Invalid value", "Profiles needed must be a number.")
            return

        if not jd:
            messagebox.showerror("Missing JD", "Please paste a Job Description first.")
            return

        if max_hits < 1 or max_hits > 200:
            messagebox.showerror("Invalid value", "Profiles needed must be between 1 and 200.")
            return

        self.detected_info = extract_jd_preview(jd, location)
        self.update_detected_panel(self.detected_info)

        self.search_btn.configure(state="disabled", text="Searching...")
        self.status_label.configure(text="Starting candidate search...")
        self.reset_process()
        self.set_process_step(0, "active")

        self._clear_results()
        loading = ctk.CTkLabel(
            self.results_frame,
            text="Searching public profiles. This may take a few seconds...",
            text_color=("gray35", "gray70"),
            font=ctk.CTkFont(size=15)
        )
        loading.grid(row=0, column=0, pady=40)

        thread = threading.Thread(
            target=self._search_worker,
            args=(jd, location, max_hits),
            daemon=True
        )
        thread.start()

    def _search_worker(self, jd, location, max_hits):
        try:
            self.after(300, lambda: self.set_process_step(1, "active"))
            self.after(600, lambda: self.set_process_step(2, "active"))
            self.after(900, lambda: self.set_process_step(3, "active"))

            response = requests.post(
                API_URL,
                json={
                    "jd": jd,
                    "location": location,
                    "max_hits": max_hits
                },
                timeout=180
            )
            response.raise_for_status()
            data = response.json()

            self.after(0, lambda: self._handle_success(data))

        except requests.exceptions.ConnectionError:
            self.after(0, lambda: self._handle_error(
                "Backend is not running. Start it with:\npython -m uvicorn discovery.api:app --reload"
            ))
        except requests.exceptions.Timeout:
            self.after(0, lambda: self._handle_error(
                "The request timed out. Try fewer profiles, for example 3 or 5."
            ))
        except Exception as exc:
            self.after(0, lambda: self._handle_error(str(exc)))

    def _handle_success(self, data):
        print("RAW API RESPONSE:")
        print(data)

        self.set_process_step(4, "active")

        self.candidates = normalize_candidates(data, self.detected_info.get("skills", []))

        self.set_process_step(5, "active")
        self.set_process_step(6, "active")
        self.set_process_step(7, "active")
        self.set_process_step(8, "active")
        self.set_process_step(9, "active")

        self.render_candidates()

        self.search_btn.configure(state="normal", text="Search candidates")
        self.status_label.configure(
            text=f"Found {len(self.candidates)} candidate profile(s). You can review or export them."
        )

    def _handle_error(self, message):
        self.search_btn.configure(state="normal", text="Search candidates")
        self.status_label.configure(text="Search failed.")
        self._clear_results()

        error_box = ctk.CTkFrame(self.results_frame, corner_radius=16)
        error_box.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(
            error_box,
            text="Search error",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=18, pady=(16, 4))

        ctk.CTkLabel(
            error_box,
            text=message,
            text_color=("gray35", "gray70"),
            wraplength=720,
            justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 16))

    def export_csv(self):
        if not self.candidates:
            messagebox.showinfo("No results", "There are no candidates to export yet.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )

        if not file_path:
            return

        fields = [
            "first_name",
            "last_name",
            "full_name",
            "profile_url",
            "email",
            "phone",
            "current_title",
            "location",
            "matched_skills",
            "match_score",
            "source"
        ]

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()

            for c in self.candidates:
                writer.writerow({
                    "first_name": c.get("first_name", ""),
                    "last_name": c.get("last_name", ""),
                    "full_name": c.get("full_name", ""),
                    "profile_url": c.get("profile_url", ""),
                    "email": c.get("email", ""),
                    "phone": c.get("phone", ""),
                    "current_title": c.get("current_title", ""),
                    "location": c.get("location", ""),
                    "matched_skills": ", ".join(c.get("matched_skills", [])),
                    "match_score": c.get("match_score", ""),
                    "source": c.get("source", "")
                })

        messagebox.showinfo("Export complete", f"CSV saved successfully:\n{file_path}")

    # ---------------- RENDERING ----------------

    def update_detected_panel(self, info):
        self.role_label.configure(text=info.get("role", "—"))
        self.seniority_label.configure(text=info.get("seniority", "—"))
        self.location_label.configure(text=info.get("location", "—"))

        for widget in self.skills_box.winfo_children():
            widget.destroy()

        skills = info.get("skills", [])
        if not skills:
            ctk.CTkLabel(
                self.skills_box,
                text="No skills detected yet.",
                text_color=("gray40", "gray65")
            ).pack(anchor="w", padx=4, pady=4)
            return

        row = None
        for i, skill in enumerate(skills[:12]):
            if i % 2 == 0:
                row = ctk.CTkFrame(self.skills_box, fg_color="transparent")
                row.pack(fill="x", pady=3)

            badge = ctk.CTkLabel(
                row,
                text=skill,
                height=28,
                corner_radius=14,
                fg_color=("#DBEAFE", "#1E3A8A"),
                text_color=("#1E3A8A", "#DBEAFE"),
                padx=10
            )
            badge.pack(side="left", padx=4)

    def reset_process(self):
        for label in self.process_steps:
            label.configure(
                text=label.cget("text").replace("●", "○").replace("✓", "○"),
                text_color=("gray35", "gray70")
            )

    def set_process_step(self, index, status):
        for i, label in enumerate(self.process_steps):
            text = label.cget("text")
            clean_text = text.replace("●", "○").replace("✓", "○")

            if i < index:
                label.configure(
                    text=clean_text.replace("○", "✓", 1),
                    text_color=("#16A34A", "#4ADE80")
                )
            elif i == index:
                label.configure(
                    text=clean_text.replace("○", "●", 1),
                    text_color=("#2563EB", "#60A5FA")
                )

    def _clear_results(self):
        for widget in self.results_frame.winfo_children():
            widget.destroy()

    def _show_empty_results(self):
        self._clear_results()

        empty = ctk.CTkFrame(self.results_frame, corner_radius=18)
        empty.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(
            empty,
            text="No candidates yet",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(22, 4))

        ctk.CTkLabel(
            empty,
            text="Paste a Job Description and press Search candidates. Results will appear here as candidate cards.",
            text_color=("gray35", "gray70"),
            wraplength=760,
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 22))

    def render_candidates(self):
        self._clear_results()

        if not self.candidates:
            self._show_empty_results()
            self.status_label.configure(text="No candidates found. Try fewer constraints or another location.")
            return

        for i, candidate in enumerate(self.candidates):
            self._candidate_card(candidate, i)

    def _candidate_card(self, candidate, index):
        card = ctk.CTkFrame(self.results_frame, corner_radius=18)
        card.grid(row=index, column=0, sticky="ew", padx=10, pady=10)
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 4))
        top.grid_columnconfigure(0, weight=1)

        name = candidate.get("full_name") or "Unknown candidate"
        score = candidate.get("match_score", 0)

        ctk.CTkLabel(
            top,
            text=name,
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            top,
            text=f"{score}% match",
            height=30,
            corner_radius=15,
            fg_color=get_score_color(score),
            text_color="white",
            font=ctk.CTkFont(size=13, weight="bold"),
            padx=12
        ).grid(row=0, column=1, sticky="e")

        title = candidate.get("current_title") or "No title detected"
        ctk.CTkLabel(
            card,
            text=title,
            text_color=("gray30", "gray75"),
            font=ctk.CTkFont(size=14)
        ).grid(row=1, column=0, sticky="w", padx=18)

        location = candidate.get("location") or "Location not found"
        source = candidate.get("source") or "discovery"
        ctk.CTkLabel(
            card,
            text=f"{location}  ·  Source: {source}",
            text_color=("gray45", "gray60"),
            font=ctk.CTkFont(size=12)
        ).grid(row=2, column=0, sticky="w", padx=18, pady=(2, 10))

        skills_row = ctk.CTkFrame(card, fg_color="transparent")
        skills_row.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 10))

        matched = candidate.get("matched_skills", [])
        if matched:
            for skill in matched[:6]:
                ctk.CTkLabel(
                    skills_row,
                    text=skill,
                    height=26,
                    corner_radius=13,
                    fg_color=("#DCFCE7", "#14532D"),
                    text_color=("#166534", "#DCFCE7"),
                    padx=9
                ).pack(side="left", padx=4)
        else:
            ctk.CTkLabel(
                skills_row,
                text="No clear skill match detected",
                text_color=("gray45", "gray60")
            ).pack(side="left", padx=4)

        contact = ctk.CTkLabel(
            card,
            text=f"Email: {candidate.get('email') or 'not found'}   |   Phone: {candidate.get('phone') or 'not found'}",
            text_color=("gray35", "gray70"),
            font=ctk.CTkFont(size=13)
        )
        contact.grid(row=4, column=0, sticky="w", padx=18, pady=(0, 10))

        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 16))
        bottom.grid_columnconfigure(0, weight=1)

        url = candidate.get("profile_url", "")
        ctk.CTkLabel(
            bottom,
            text=url,
            text_color=("#2563EB", "#93C5FD"),
            font=ctk.CTkFont(size=12)
        ).grid(row=0, column=0, sticky="w")

        open_btn = ctk.CTkButton(
            bottom,
            text="Open profile",
            width=120,
            height=34,
            command=lambda u=url: webbrowser.open(u) if u else None
        )
        open_btn.grid(row=0, column=1, sticky="e")


# ---------------- HELPERS ----------------

def extract_jd_preview(jd_text, fallback_location=""):
    lower = jd_text.lower()

    skills = []
    for skill in SKILL_KEYWORDS:
        if skill in lower:
            skills.append(skill.title() if skill not in ["api", "llm", "rag", "nlp"] else skill.upper())

    role = "—"
    for title in JOB_TITLES:
        if title in lower:
            role = title.title()
            break

    if role == "—":
        match = re.search(r"(junior|mid|senior)?\s?([a-zA-Z ]+ developer|engineer|scientist)", jd_text, re.I)
        if match:
            role = match.group(0).strip().title()

    seniority = "—"
    if "junior" in lower:
        seniority = "Junior"
    elif "senior" in lower:
        seniority = "Senior"
    elif "mid" in lower or "middle" in lower:
        seniority = "Mid"

    location = fallback_location or "—"
    for loc in ["bucharest", "romania", "cluj", "iasi", "timisoara", "remote", "hybrid"]:
        if loc in lower:
            location = loc.title()
            break

    return {
        "role": role,
        "seniority": seniority,
        "location": location,
        "skills": skills
    }


def normalize_candidates(raw_data, jd_skills):
    if isinstance(raw_data, dict):
        raw_candidates = (
            raw_data.get("profiles")
            or raw_data.get("results")
            or raw_data.get("candidates")
            or raw_data.get("data")
            or []
        )
    else:
        raw_candidates = raw_data

    normalized = []

    for item in raw_candidates:
        if not isinstance(item, dict):
            continue

        profile_url = (
            item.get("profile_url")
            or item.get("url")
            or item.get("link")
            or item.get("linkedin_url")
            or ""
        )

        full_name = (
            item.get("name")
            or item.get("full_name")
            or item.get("fullName")
            or extract_name_from_title(item.get("headline") or item.get("title") or "")
            or extract_name_from_linkedin_url(profile_url)
            or "Unknown candidate"
        )

        first_name, last_name = split_name(full_name)

        current_title = (
            item.get("role")
            or item.get("headline")
            or item.get("title")
            or "No title detected"
        )

        location = item.get("location") or item.get("city") or ""

        experience = item.get("experience") or item.get("experienta") or []
        education = item.get("education") or item.get("educatie") or []

        if isinstance(experience, str):
            experience = [experience]

        if isinstance(education, str):
            education = [education]

        text_blob = " ".join([
            full_name,
            current_title,
            location,
            " ".join(experience),
            " ".join(education)
        ]).lower()

        matched_skills = []
        for skill in jd_skills:
            if skill.lower() in text_blob:
                matched_skills.append(skill)

        score = compute_score(
            {
                "role": current_title,
                "location": location,
                "experience": experience,
                "education": education
            },
            matched_skills,
            jd_skills
        )

        normalized.append({
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "profile_url": profile_url,
            "email": item.get("email", ""),
            "phone": item.get("phone", ""),
            "current_title": current_title,
            "location": location,
            "experience": experience,
            "education": education,
            "matched_skills": matched_skills,
            "match_score": score,
            "source": item.get("source") or "discovery"
        })

    normalized.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return normalized


def extract_name_from_title(title):
    if not title:
        return ""

    title = title.replace("| LinkedIn", "").strip()

    if " - " in title:
        return title.split(" - ", 1)[0].strip()

    return ""


def extract_name_from_linkedin_url(url):
    if not url or "/in/" not in url:
        return ""

    slug = url.split("/in/")[-1].split("?")[0].strip("/")
    slug = re.sub(r"-[0-9a-f]{6,}$", "", slug)
    slug = re.sub(r"-\d+$", "", slug)
    slug = slug.replace("-", " ").replace("_", " ")

    if not slug:
        return ""

    return slug.title()

def split_name(full_name):
    parts = full_name.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def compute_score(item, matched_skills, jd_skills):
    score = 30

    if jd_skills:
        score += int((len(matched_skills) / max(len(jd_skills), 1)) * 45)

    if item.get("role"):
        score += 10

    if item.get("location"):
        score += 5

    if item.get("experience"):
        score += 7

    if item.get("education"):
        score += 3

    return min(score, 100)


def get_score_color(score):
    if score >= 80:
        return "#16A34A"
    if score >= 60:
        return "#F59E0B"
    return "#DC2626"


if __name__ == "__main__":
    app = TalentScoutApp()
    app.mainloop()