from __future__ import annotations

from html import escape
import streamlit as st


def inject_ui_shell_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #f4f7fb 0%, #eef3f9 100%);
            color: #142033;
        }

        [data-testid="stHeader"] {
            background: rgba(0,0,0,0);
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 3rem;
            max-width: 1200px;
        }

        .ev-hero {
            position: relative;
            overflow: hidden;
            border-radius: 28px;
            padding: 34px 36px 30px 36px;
            background:
                linear-gradient(135deg, rgba(9,22,43,0.88), rgba(21,46,84,0.76)),
                url("https://images.unsplash.com/photo-1513828583688-c52646db42da?auto=format&fit=crop&w=1600&q=80");
            background-size: cover;
            background-position: center;
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 18px 50px rgba(17, 30, 54, 0.12);
            margin-bottom: 20px;
        }

        .ev-hero-topline {
            display: inline-block;
            font-size: 0.78rem;
            letter-spacing: 0.18em;
            font-weight: 800;
            text-transform: uppercase;
            color: rgba(255,255,255,0.84);
            margin-bottom: 14px;
        }

        .ev-hero h1 {
            margin: 0;
            font-size: 3rem;
            line-height: 1.02;
            letter-spacing: -0.03em;
            font-weight: 800;
            color: #ffffff;
        }

        .ev-hero p {
            margin-top: 16px;
            margin-bottom: 0;
            max-width: 780px;
            color: rgba(255,255,255,0.88);
            font-size: 1.08rem;
            line-height: 1.72;
        }

        .ev-hero-chip-row {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 20px;
        }

        .ev-hero-chip {
            padding: 8px 14px;
            border-radius: 999px;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.14);
            color: rgba(255,255,255,0.96);
            font-size: 0.90rem;
            font-weight: 600;
        }

        .ev-stage-card {
            background: rgba(255,255,255,0.86);
            border: 1px solid #d9e2f0;
            border-radius: 16px;
            padding: 15px 15px 14px 15px;
            min-height: 112px;
            height: 112px;
            box-sizing: border-box;
            box-shadow: 0 8px 22px rgba(25, 37, 62, 0.04);
        }

        .ev-stage-num {
            font-size: 0.76rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            font-weight: 800;
            color: #4467aa;
            margin-bottom: 10px;
        }

        .ev-stage-title {
            font-size: 1.08rem;
            line-height: 1.25;
            font-weight: 800;
            color: #142033;
            margin-bottom: 7px;
        }

        .ev-stage-subtitle {
            font-size: 0.72rem;
            line-height: 1.3;
            color: #718097;
            font-weight: 700;
            margin-top: 2px;
            margin-bottom: 8px;
            letter-spacing: 0.01em;
        }

        .ev-stage-desc {
            font-size: 0.88rem;
            line-height: 1.48;
            color: #5d6c85;
            word-break: keep-all;
            overflow-wrap: break-word;
        }

        .ev-section {
            margin-top: 24px;
            margin-bottom: 8px;
        }

        .ev-section-kicker {
            font-size: 0.74rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            font-weight: 800;
            color: #4d6fb2;
            margin-bottom: 6px;
        }

        .ev-section-title {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            color: #16233a;
            margin-bottom: 8px;
        }

        .ev-section-desc {
            font-size: 1rem;
            line-height: 1.7;
            color: #60708a;
            margin-bottom: 18px;
            max-width: 860px;
        }

        .ev-soft-note {
            background: rgba(255,255,255,0.82);
            border: 1px solid #d9e2f0;
            border-left: 4px solid #4d6fb2;
            border-radius: 16px;
            padding: 14px 16px;
            color: #2a3a56;
            line-height: 1.65;
            margin-bottom: 12px;
        }


        /* =========================================================
           EV FILE UPLOADER POLISH
           Scoped to Streamlit file uploader only.
           ========================================================= */

        [data-testid="stFileUploader"] {
            margin-top: 0.25rem;
            margin-bottom: 0.75rem;
        }

        [data-testid="stFileUploader"] > label {
            color: #22324c !important;
            font-weight: 700 !important;
        }

        [data-testid="stFileUploaderDropzone"] {
            background: #fbfdff !important;
            border: 1.5px dashed #b8c7dc !important;
            border-radius: 16px !important;
            padding: 1.15rem 1.25rem !important;
            transition:
                border-color 160ms ease,
                background-color 160ms ease,
                box-shadow 160ms ease;
        }

        [data-testid="stFileUploaderDropzone"]:hover {
            background: #f6f9fd !important;
            border-color: #6f8fc5 !important;
            box-shadow: 0 5px 18px rgba(28, 48, 82, 0.06);
        }

        [data-testid="stFileUploaderDropzone"] *,
        [data-testid="stFileUploaderDropzoneInstructions"] * {
            color: #45566f !important;
        }

        [data-testid="stFileUploaderDropzoneInstructions"] span {
            color: #263851 !important;
            font-weight: 650 !important;
        }

        [data-testid="stFileUploaderDropzoneInstructions"] small {
            color: #718097 !important;
            font-weight: 500 !important;
        }

        [data-testid="stFileUploaderDropzone"] button {
            background: #ffffff !important;
            color: #315d9b !important;
            border: 1px solid #aebfd7 !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            box-shadow: none !important;
        }

        [data-testid="stFileUploaderDropzone"] button:hover {
            background: #f1f6fc !important;
            color: #244f8d !important;
            border-color: #7695c2 !important;
        }

        [data-testid="stFileUploaderFile"] {
            background: #ffffff !important;
            border: 1px solid #d9e2f0 !important;
            border-radius: 12px !important;
            color: #263851 !important;
        }

        [data-testid="stFileUploaderFile"] * {
            color: #263851 !important;
        }


        /* =========================================================
           EV RADIO AND PRIMARY ACTION POLISH
           ========================================================= */

        [data-testid="stRadio"] > label,
        [data-testid="stRadio"] > label p {
            color: #33445f !important;
            font-weight: 700 !important;
        }

        [data-testid="stRadio"] [role="radiogroup"] label,
        [data-testid="stRadio"] [role="radiogroup"] label p {
            color: #4c5d75 !important;
            font-weight: 600 !important;
        }

        [data-testid="stRadio"] [role="radiogroup"] {
            gap: 0.65rem;
        }

        [data-testid="stBaseButton-primary"] {
            background: #315f9f !important;
            color: #ffffff !important;
            border: 1px solid #315f9f !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            box-shadow: 0 4px 12px rgba(37, 78, 137, 0.12) !important;
            transition:
                background-color 150ms ease,
                border-color 150ms ease,
                box-shadow 150ms ease,
                transform 150ms ease;
        }

        [data-testid="stBaseButton-primary"]:hover {
            background: #274f88 !important;
            border-color: #274f88 !important;
            box-shadow: 0 6px 16px rgba(37, 78, 137, 0.16) !important;
        }

        [data-testid="stBaseButton-primary"]:active {
            transform: translateY(1px);
        }

        [data-testid="stBaseButton-primary"] p {
            color: #ffffff !important;
            font-weight: 700 !important;
        }


        /* =========================================================
           EV LIGHT CONTROL POLISH
           Keep interactive controls aligned with the light
           engineering workspace. No dark control surfaces.
           ========================================================= */

        /* ---------- EXPANDER / SOURCE CARD ---------- */

        [data-testid="stExpander"] details {
            background: #ffffff !important;
            border: 1px solid #d9e2f0 !important;
            border-radius: 14px !important;
            overflow: hidden !important;
            box-shadow: 0 4px 14px rgba(28, 48, 82, 0.035) !important;
        }

        [data-testid="stExpander"] summary {
            background: #ffffff !important;
            color: #21324b !important;
            min-height: 50px !important;
        }

        [data-testid="stExpander"] summary:hover {
            background: #f6f9fd !important;
        }

        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] summary p,
        [data-testid="stExpander"] summary span {
            color: #21324b !important;
        }

        [data-testid="stExpander"] summary svg {
            color: #58749b !important;
            fill: currentColor !important;
        }

        /* ---------- MULTISELECT ---------- */

        [data-testid="stMultiSelect"] > label,
        [data-testid="stMultiSelect"] > label *,
        [data-testid="stMultiSelect"] label p {
            color: #33445f !important;
            font-weight: 700 !important;
        }

        [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            border-color: #b8c7dc !important;
            color: #22324c !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            min-height: 44px !important;
        }

        [data-testid="stMultiSelect"] [data-baseweb="select"] > div:hover {
            border-color: #7695c2 !important;
            background: #fbfdff !important;
        }

        [data-testid="stMultiSelect"] [data-baseweb="select"] input {
            color: #22324c !important;
            caret-color: #315f9f !important;
        }

        [data-testid="stMultiSelect"] [data-baseweb="select"] svg {
            color: #5c7191 !important;
            fill: currentColor !important;
        }

        /* Selected Analysis Scope chips */

        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background: #edf4fc !important;
            border: 1px solid #c5d5e8 !important;
            border-radius: 8px !important;
            color: #244f7e !important;
            box-shadow: none !important;
        }

        [data-testid="stMultiSelect"] [data-baseweb="tag"] *,
        [data-testid="stMultiSelect"] [data-baseweb="tag"] span {
            color: #244f7e !important;
        }

        [data-testid="stMultiSelect"] [data-baseweb="tag"] svg {
            color: #55759e !important;
            fill: currentColor !important;
        }

        /* ---------- OPEN MULTISELECT MENU ---------- */

        [data-baseweb="popover"] {
            background: transparent !important;
        }

        [data-baseweb="popover"] [role="listbox"] {
            background: #ffffff !important;
            border: 1px solid #d9e2f0 !important;
            border-radius: 10px !important;
            box-shadow: 0 10px 28px rgba(25, 37, 62, 0.10) !important;
            overflow: hidden !important;
        }

        [data-baseweb="popover"] [role="option"] {
            background: #ffffff !important;
            color: #263851 !important;
        }

        [data-baseweb="popover"] [role="option"] * {
            color: #263851 !important;
        }

        [data-baseweb="popover"] [role="option"]:hover {
            background: #f1f6fc !important;
            color: #244f7e !important;
        }

        [data-baseweb="popover"] [aria-selected="true"] {
            background: #eaf2fb !important;
            color: #244f7e !important;
        }

        /* ---------- UPLOADED FILE ITEMS ---------- */

        [data-testid="stFileUploaderFile"] {
            background: #f8fbff !important;
            border: 1px solid #d5e0ee !important;
            border-radius: 10px !important;
            color: #263851 !important;
        }

        [data-testid="stFileUploaderFile"] > div {
            background: transparent !important;
        }

        [data-testid="stFileUploaderFile"] *,
        [data-testid="stFileUploaderFile"] span,
        [data-testid="stFileUploaderFile"] small {
            color: #33445f !important;
        }

        [data-testid="stFileUploaderFile"] button {
            background: #eef4fb !important;
            border: 1px solid #d2deec !important;
            color: #496789 !important;
            box-shadow: none !important;
        }

        [data-testid="stFileUploaderFile"] button:hover {
            background: #e4edf8 !important;
        }

        /* ---------- STREAMLIT STATUS / ALERT TEXT ---------- */

        [data-testid="stAlert"] {
            border-radius: 12px !important;
        }

        [data-testid="stAlert"] *,
        [data-testid="stAlert"] p,
        [data-testid="stAlert"] span {
            color: #263851 !important;
        }


        /* =========================================================
           EV FORCE LIGHT INTERACTIVE CONTROLS V2
           Strong override for Streamlit / BaseWeb dark defaults.
           ========================================================= */

        /* ---------- MULTISELECT MAIN FIELD ---------- */

        [data-testid="stMultiSelect"] div[data-baseweb="select"],
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] [role="combobox"] {
            background-color: #ffffff !important;
            background: #ffffff !important;
            color: #22324c !important;
            border-color: #b8c7dc !important;
        }

        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
            border: 1px solid #b8c7dc !important;
            border-radius: 10px !important;
            box-shadow: none !important;
        }

        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div:hover {
            background: #fbfdff !important;
            border-color: #7695c2 !important;
        }

        [data-testid="stMultiSelect"] div[data-baseweb="select"] input {
            background: transparent !important;
            color: #22324c !important;
            -webkit-text-fill-color: #22324c !important;
        }

        [data-testid="stMultiSelect"] div[data-baseweb="select"] svg {
            color: #597393 !important;
            fill: currentColor !important;
        }

        /* ---------- SELECTED SCOPE CHIPS ---------- */

        [data-testid="stMultiSelect"] [data-baseweb="tag"],
        [data-testid="stMultiSelect"] span[data-baseweb="tag"],
        [data-testid="stMultiSelect"] div[data-baseweb="tag"] {
            background: #eaf2fb !important;
            background-color: #eaf2fb !important;
            border: 1px solid #c5d6e9 !important;
            color: #244f7e !important;
            border-radius: 8px !important;
            box-shadow: none !important;
        }

        [data-testid="stMultiSelect"] [data-baseweb="tag"] *,
        [data-testid="stMultiSelect"] [data-baseweb="tag"] span,
        [data-testid="stMultiSelect"] [data-baseweb="tag"] div {
            background: transparent !important;
            background-color: transparent !important;
            color: #244f7e !important;
            -webkit-text-fill-color: #244f7e !important;
        }

        [data-testid="stMultiSelect"] [data-baseweb="tag"] svg {
            color: #55759e !important;
            fill: currentColor !important;
        }

        /* ---------- DROPDOWN / POPOVER ---------- */

        div[data-baseweb="popover"],
        div[data-baseweb="popover"] > div,
        div[data-baseweb="popover"] ul,
        div[data-baseweb="popover"] [role="listbox"],
        ul[role="listbox"] {
            background: #ffffff !important;
            background-color: #ffffff !important;
            color: #263851 !important;
        }

        div[data-baseweb="popover"] [role="listbox"],
        ul[role="listbox"] {
            border: 1px solid #d9e2f0 !important;
            border-radius: 10px !important;
            box-shadow: 0 10px 28px rgba(25, 37, 62, 0.10) !important;
        }

        div[data-baseweb="popover"] [role="option"],
        ul[role="listbox"] [role="option"],
        li[role="option"] {
            background: #ffffff !important;
            background-color: #ffffff !important;
            color: #263851 !important;
        }

        div[data-baseweb="popover"] [role="option"] *,
        ul[role="listbox"] [role="option"] *,
        li[role="option"] * {
            color: #263851 !important;
            -webkit-text-fill-color: #263851 !important;
        }

        div[data-baseweb="popover"] [role="option"]:hover,
        ul[role="listbox"] [role="option"]:hover,
        li[role="option"]:hover {
            background: #f1f6fc !important;
            background-color: #f1f6fc !important;
            color: #244f7e !important;
        }

        div[data-baseweb="popover"] [aria-selected="true"],
        ul[role="listbox"] [aria-selected="true"] {
            background: #eaf2fb !important;
            background-color: #eaf2fb !important;
            color: #244f7e !important;
        }

        /* ---------- FILE UPLOAD ITEMS ---------- */

        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"],
        [data-testid="stFileUploaderFile"] {
            background: #f8fbff !important;
            background-color: #f8fbff !important;
            border: 1px solid #d5e0ee !important;
            color: #263851 !important;
            border-radius: 10px !important;
        }

        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] *,
        [data-testid="stFileUploaderFile"] * {
            color: #33445f !important;
            -webkit-text-fill-color: #33445f !important;
        }

        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] button,
        [data-testid="stFileUploaderFile"] button {
            background: #eef4fb !important;
            background-color: #eef4fb !important;
            border: 1px solid #d2deec !important;
            color: #496789 !important;
        }

        /* ---------- ALERTS ---------- */

        [data-testid="stAlert"] p,
        [data-testid="stAlert"] span,
        [data-testid="stAlert"] div {
            color: #263851 !important;
            -webkit-text-fill-color: #263851 !important;
        }


        /* =========================================================
           EV CHECKBOX POLISH
           Unselected = white / selected = engineering blue.
           ========================================================= */

        [data-testid="stCheckbox"] {
            margin: 0.12rem 0 !important;
        }

        [data-testid="stCheckbox"] label {
            color: #263851 !important;
            cursor: pointer !important;
        }

        [data-testid="stCheckbox"] label p,
        [data-testid="stCheckbox"] label span {
            color: #263851 !important;
        }

        /* Common Streamlit/BaseWeb checkbox surfaces */
        [data-testid="stCheckbox"] [role="checkbox"] {
            background: #ffffff !important;
            background-color: #ffffff !important;
            border: 1.5px solid #8fa5c0 !important;
            border-radius: 5px !important;
            box-shadow: none !important;
        }

        [data-testid="stCheckbox"] [role="checkbox"][aria-checked="true"] {
            background: #315f9f !important;
            background-color: #315f9f !important;
            border-color: #315f9f !important;
        }

        [data-testid="stCheckbox"] label[data-baseweb="checkbox"] > span:first-child {
            background: #ffffff !important;
            background-color: #ffffff !important;
            border: 1.5px solid #8fa5c0 !important;
            border-radius: 5px !important;
            box-shadow: none !important;
        }

        [data-testid="stCheckbox"]
        label[data-baseweb="checkbox"]:has(input:checked)
        > span:first-child {
            background: #315f9f !important;
            background-color: #315f9f !important;
            border-color: #315f9f !important;
        }

        [data-testid="stCheckbox"]
        label[data-baseweb="checkbox"]:has(input:checked)
        svg,
        [data-testid="stCheckbox"]
        [role="checkbox"][aria-checked="true"]
        svg {
            color: #ffffff !important;
            fill: #ffffff !important;
        }

        [data-testid="stCheckbox"] label:hover {
            color: #244f7e !important;
        }


        /* =========================================================
           EV SECONDARY BUTTON LIGHT STYLE
           Unselected scope button = light surface.
           ========================================================= */

        [data-testid="stBaseButton-secondary"] {
            background: #ffffff !important;
            color: #263851 !important;
            border: 1px solid #b8c7dc !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            font-weight: 650 !important;
        }

        [data-testid="stBaseButton-secondary"] p,
        [data-testid="stBaseButton-secondary"] span {
            color: #263851 !important;
        }

        [data-testid="stBaseButton-secondary"]:hover {
            background: #f4f8fc !important;
            border-color: #6f8fc5 !important;
            color: #244f7e !important;
        }


        /* =========================================================
           EV UPLOADED FILE CHIP LIGHT V2
           Native uploader file items should never use dark surfaces.
           ========================================================= */

        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"],
        [data-testid="stFileUploader"] [data-baseweb="tag"],
        [data-testid="stFileUploader"] li {
            background: #f7faff !important;
            background-color: #f7faff !important;
            border: 1px solid #cbd9e9 !important;
            color: #263851 !important;
            border-radius: 10px !important;
            box-shadow: none !important;
        }

        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] *,
        [data-testid="stFileUploader"] [data-baseweb="tag"] *,
        [data-testid="stFileUploader"] li * {
            color: #33445f !important;
            -webkit-text-fill-color: #33445f !important;
        }

        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] button,
        [data-testid="stFileUploader"] [data-baseweb="tag"] button,
        [data-testid="stFileUploader"] li button {
            background: #eef4fb !important;
            background-color: #eef4fb !important;
            border: 1px solid #cbd9e9 !important;
            color: #496789 !important;
            box-shadow: none !important;
        }

        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] svg,
        [data-testid="stFileUploader"] [data-baseweb="tag"] svg,
        [data-testid="stFileUploader"] li svg {
            color: #496789 !important;
            fill: currentColor !important;
        }

        .ev-divider-space {
            height: 4px;
        }

        /* =========================================================
           EV METRIC CARDS
           Improve contrast and remove the empty-space appearance.
           ========================================================= */

        [data-testid="stMetric"] {
            background: rgba(255,255,255,0.82) !important;
            border: 1px solid #d9e2f0 !important;
            border-radius: 14px !important;
            padding: 0.85rem 1rem 0.78rem 1rem !important;
            min-height: 86px !important;
            box-shadow: 0 6px 18px rgba(25, 37, 62, 0.035) !important;
        }

        [data-testid="stMetricLabel"],
        [data-testid="stMetricLabel"] * {
            color: #5d6c85 !important;
            font-weight: 700 !important;
        }

        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] * {
            color: #16233a !important;
            font-weight: 800 !important;
        }

        [data-testid="stMetricDelta"],
        [data-testid="stMetricDelta"] * {
            color: #60708a !important;
        }


        /* =========================================================
           EV SOURCE COVERAGE
           Neutral engineering-status presentation.
           ========================================================= */

        .ev-coverage-list {
            background: rgba(255,255,255,0.78);
            border: 1px solid #d9e2f0;
            border-radius: 16px;
            overflow: hidden;
            margin-top: 0.8rem;
            margin-bottom: 0.7rem;
        }

        .ev-coverage-row {
            display: grid;
            grid-template-columns: minmax(240px, 1.45fr) 150px 2fr;
            gap: 18px;
            align-items: center;
            padding: 15px 16px;
            border-bottom: 1px solid #e5ebf3;
        }

        .ev-coverage-row:last-child {
            border-bottom: none;
        }

        .ev-coverage-file {
            color: #20314b;
            font-size: 0.90rem;
            font-weight: 700;
            overflow-wrap: anywhere;
        }

        .ev-coverage-state {
            display: inline-flex;
            width: fit-content;
            align-items: center;
            border: 1px solid #c8d4e5;
            border-radius: 999px;
            padding: 5px 10px;
            background: #f7f9fc;
            color: #36557d;
            font-size: 0.76rem;
            font-weight: 800;
            white-space: nowrap;
        }

        .ev-coverage-detail {
            color: #5b6b82;
            font-size: 0.88rem;
            line-height: 1.5;
            word-break: keep-all;
        }

        .ev-coverage-note {
            border-left: 3px solid #6683ae;
            padding: 10px 13px;
            margin-top: 8px;
            margin-bottom: 12px;
            color: #53637a;
            background: rgba(255,255,255,0.50);
            font-size: 0.86rem;
            line-height: 1.55;
            border-radius: 0 10px 10px 0;
        }

        .ev-analysis-ready {
            display: flex;
            align-items: center;
            gap: 9px;
            background: #f8fafc;
            border: 1px solid #ccd8e8;
            border-radius: 12px;
            padding: 12px 14px;
            margin-top: 0.5rem;
            margin-bottom: 0.65rem;
            color: #203651;
            font-size: 0.90rem;
            font-weight: 700;
        }

        .ev-analysis-ready-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #416ca8;
            flex: 0 0 8px;
        }

        @media (max-width: 900px) {
            .ev-coverage-row {
                grid-template-columns: 1fr;
                gap: 7px;
            }
        }


        /* =========================================================
           EV TYPOGRAPHY TUNING
           Cleaner hierarchy for judge-facing UI.
           ========================================================= */

        /* General markdown body */
        [data-testid="stMarkdownContainer"] p {
            font-size: 0.94rem;
            line-height: 1.62;
            font-weight: 400;
        }

        /* Streamlit headings */
        [data-testid="stMarkdownContainer"] h1 {
            font-weight: 780;
            letter-spacing: -0.035em;
            line-height: 1.18;
        }

        [data-testid="stMarkdownContainer"] h2 {
            font-size: 1.55rem;
            font-weight: 760;
            letter-spacing: -0.03em;
            line-height: 1.25;
        }

        [data-testid="stMarkdownContainer"] h3 {
            font-size: 1.30rem;
            font-weight: 720;
            letter-spacing: -0.025em;
            line-height: 1.3;
        }

        [data-testid="stMarkdownContainer"] h4 {
            font-size: 1.12rem;
            font-weight: 700;
            letter-spacing: -0.018em;
        }

        [data-testid="stMarkdownContainer"] h5 {
            font-size: 1.00rem;
            font-weight: 700;
            letter-spacing: -0.012em;
        }

        /* Metric cards */
        [data-testid="stMetric"] {
            min-height: 88px;
            padding: 15px 16px 14px;
        }

        [data-testid="stMetricLabel"] p {
            font-size: 0.81rem !important;
            line-height: 1.25 !important;
            font-weight: 650 !important;
            letter-spacing: -0.01em;
            color: #61708a !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.96rem !important;
            line-height: 1.08 !important;
            font-weight: 700 !important;
            letter-spacing: -0.035em !important;
            color: #17243a !important;
            white-space: nowrap !important;
        }

        [data-testid="stMetricValue"] > div {
            font-size: inherit !important;
            font-weight: inherit !important;
            line-height: inherit !important;
            white-space: nowrap !important;
        }

        /* Captions / secondary copy */
        [data-testid="stCaptionContainer"] {
            font-size: 0.84rem !important;
            line-height: 1.55 !important;
            font-weight: 400 !important;
            color: #6a778c !important;
        }

        /* Buttons */
        .stButton > button {
            font-size: 0.89rem !important;
            font-weight: 650 !important;
            letter-spacing: -0.01em;
        }

        /* Coverage table */
        .ev-coverage-file {
            font-size: 0.90rem;
            font-weight: 640;
            letter-spacing: -0.015em;
        }

        .ev-coverage-state {
            font-size: 0.77rem;
            font-weight: 680;
        }

        .ev-coverage-detail {
            font-size: 0.89rem;
            line-height: 1.5;
            font-weight: 400;
        }

        .ev-analysis-ready {
            font-size: 0.86rem;
            line-height: 1.45;
            font-weight: 650;
        }

        /* Expanders */
        [data-testid="stExpander"] summary {
            font-size: 0.86rem;
            font-weight: 600;
        }


        /* =========================================================
           EV METRIC VALUE EMPHASIS
           Make judge-facing KPI values visually dominant.
           ========================================================= */

        [data-testid="stMetric"] {
            min-height: 94px !important;
            padding: 15px 16px 14px !important;
        }

        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] > div,
        [data-testid="stMetricValue"] div,
        [data-testid="stMetricValue"] span,
        [data-testid="stMetricValue"] p {
            font-size: 1.82rem !important;
            line-height: 1.05 !important;
            font-weight: 690 !important;
            letter-spacing: -0.03em !important;
            color: #17243a !important;
        }

        [data-testid="stMetricLabel"],
        [data-testid="stMetricLabel"] p,
        [data-testid="stMetricLabel"] span {
            font-size: 0.82rem !important;
            font-weight: 650 !important;
            line-height: 1.3 !important;
            color: #61708a !important;
        }


        /* =========================================================
           EV ASSURANCE PRESENTATION
           ========================================================= */

        .ev-assurance-line {
            min-height: 94px;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px 18px;
            padding: 16px 18px;
            background: rgba(255,255,255,0.74);
            border: 1px solid #d9e2f0;
            border-radius: 14px;
            box-sizing: border-box;
            color: #40536f;
            font-size: 0.90rem;
            line-height: 1.5;
            font-weight: 600;
        }

        .ev-assurance-line span {
            white-space: nowrap;
        }

        .ev-analysis-capability {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-top: 10px;
            margin-bottom: 4px;
            padding: 9px 13px;
            background: rgba(255,255,255,0.62);
            border: 1px solid #d5dfed;
            border-radius: 10px;
            color: #40536f;
            font-size: 0.88rem;
            line-height: 1.4;
            font-weight: 600;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero_banner() -> None:
    st.markdown(
        """
        <div class="ev-hero">
            <div class="ev-hero-topline">
                Engineering Verification Stress Test · Evidence-Grounded
            </div>
            <h1>공학 검증 스트레스 테스트</h1>
            <p>
                실제 공학 문서에서 Requirement, Verification Criterion,
                Observed Evidence를 추적하고, Role Grounding과 엔지니어 검토를 거쳐
                결정론적 solver로 Verification Escape 여부를 판정합니다.
            </p>
            <div class="ev-hero-chip-row">
                <div class="ev-hero-chip">원본 근거 · Document Evidence</div>
                <div class="ev-hero-chip">공학 의미 분석 · Semantics</div>
                <div class="ev-hero-chip">엔지니어 검토 · Review</div>
                <div class="ev-hero-chip">결정론적 검증 · Verification</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stage_strip() -> None:
    items = [
        ("01", "공학 원본 문서", "Engineering Sources"),
        ("02", "근거 탐색", "Evidence Discovery"),
        ("03", "근거 검증 및 승인", "Grounding & Review"),
        ("04", "수식화", "Formalization"),
        ("05", "결정론적 검증", "Deterministic Verification"),
    ]

    cols = st.columns(5)

    for col, (num, title, subtitle) in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="ev-stage-card">
                    <div class="ev-stage-num">{escape(num)}</div>
                    <div class="ev-stage-title">{escape(title)}</div>
                    <div class="ev-stage-subtitle">{escape(subtitle)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )



def render_section_header(
    kicker: str,
    title: str,
    desc: str,
) -> None:
    st.markdown(
        f"""
        <div class="ev-section">
            <div class="ev-section-kicker">{escape(kicker)}</div>
            <div class="ev-section-title">{escape(title)}</div>
            <div class="ev-section-desc">{escape(desc)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_soft_note(text: str) -> None:
    st.markdown(
        f'<div class="ev-soft-note">{escape(text)}</div>',
        unsafe_allow_html=True,
    )
