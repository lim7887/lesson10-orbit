"""위성 궤도 정보 실습실 - 소개 화면 + 위성 찾기 + 그래프"""
import json
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

APP_TITLE = "위성 궤도 정보 실습실"
APP_ICON = "🛰️"

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "위성궤도정보.csv"  # main.py와 같은 폴더에 두세요
RECORD_DIR = BASE_DIR / "내_기록"
RECORD_FILE = RECORD_DIR / "기록.json"

MU = 398600.4418  # 지구 중력상수 (km^3/s^2)
EARTH_RADIUS = 6378.137  # 지구 적도 반지름 (km)
NEED_COLUMNS = ["위성명", "위성번호", "평균 회전값"]

# 브라우저 탭에 제목과 아이콘이 표시됩니다.
st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")

st.markdown(
    """
    <style>
    .stat-card {
        background: rgba(128, 128, 128, 0.12);
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 14px;
        padding: 22px 12px;
        text-align: center;
    }
    .stat-label { font-size: 1rem; opacity: 0.8; margin-bottom: 6px; }
    .stat-value { font-size: 2.6rem; font-weight: 700; line-height: 1.15; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- 기록 저장/불러오기
def load_record():
    """내_기록/기록.json에서 우리말 뜻과 출처를 불러옵니다. 없으면 빈 값."""
    try:
        with open(RECORD_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}, ""
    meanings = data.get("meanings", {}) if isinstance(data, dict) else {}
    source = data.get("source", "") if isinstance(data, dict) else ""
    if not isinstance(meanings, dict):
        meanings = {}
    if not isinstance(source, str):
        source = ""
    return meanings, source


def save_record(meanings, source):
    """우리말 뜻과 출처를 내_기록/기록.json에 저장합니다."""
    try:
        RECORD_DIR.mkdir(parents=True, exist_ok=True)
        with open(RECORD_FILE, "w", encoding="utf-8") as f:
            json.dump({"meanings": meanings, "source": source}, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- 데이터 불러오기와 계산
def find_csv():
    """위성궤도정보.csv를 찾습니다. 같은 폴더 → 하위 폴더 → 실행 위치 순서로 찾고,
    이름이 달라도 csv 파일이면 사용합니다."""
    if CSV_PATH.exists():
        return CSV_PATH
    for folder in (BASE_DIR, Path.cwd()):
        found = sorted(folder.glob("*.csv"))
        if found:
            return found[0]
    for folder in (BASE_DIR, Path.cwd()):
        found = sorted(p for p in folder.rglob("*.csv") if "내_기록" not in p.parts)
        if found:
            return found[0]
    return None


@st.cache_data(show_spinner="데이터를 불러오는 중입니다...")
def load_data(path_text):
    """포털 CSV는 CP949(한글 윈도우 인코딩)인 경우가 많아서 둘 다 시도합니다."""
    raw = None
    for encoding in ("utf-8-sig", "cp949"):
        try:
            raw = pd.read_csv(path_text, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raise ValueError("파일의 글자 인코딩을 읽지 못했습니다.")
    raw.columns = [str(c).strip() for c in raw.columns]  # 열 이름 앞뒤 공백 제거
    return raw


def orbit_type(height_km):
    """고도 구간으로 나눈 임의 분류 (데이터에 있는 값이 아닙니다)."""
    if pd.isna(height_km):
        return "알 수 없음"
    if height_km < 2000:
        return "저궤도"
    if height_km < 35000:
        return "중궤도"
    if height_km <= 36500:
        return "정지궤도 부근"
    return "그 외 고궤도"


def add_calcs(raw):
    """평균 회전값을 '하루에 지구를 도는 횟수'로 보고 주기와 고도를 계산합니다."""
    df = raw.copy()
    df["위성명(정리)"] = (
        df["위성명"].astype(str).str.replace(r"^0\s+", "", regex=True).str.strip()
    )
    n = pd.to_numeric(df["평균 회전값"], errors="coerce")
    omega = n * 2 * math.pi / 86400  # rad/s
    semi_major = (MU / omega**2) ** (1 / 3)  # 궤도 긴반지름 (km)
    df["궤도주기(분)"] = 1440 / n
    df["고도(km)"] = semi_major - EARTH_RADIUS  # 원 궤도로 가정한 근사값
    df["궤도 유형"] = df["고도(km)"].apply(orbit_type)
    return df


def describe_values(series):
    """열에 어떤 값이 들어 있는지 짧게 설명합니다."""
    values = series.dropna().unique().tolist()
    if pd.api.types.is_numeric_dtype(series):
        if len(values) <= 10:
            return ", ".join(str(v) for v in sorted(values))
        return f"숫자 ({series.min():g} ~ {series.max():g}), 서로 다른 값 {len(values):,}개"
    if len(values) <= 10:
        return ", ".join(sorted(str(v) for v in values))
    return f"글자, 서로 다른 값 {len(values):,}개"


csv_file = find_csv()
if csv_file is None:
    st.error("위성궤도정보.csv 파일을 찾지 못했습니다. main.py와 같은 폴더에 CSV 파일을 넣어 주세요.")
    try:
        listing = sorted(p.name for p in BASE_DIR.iterdir())
    except OSError:
        listing = []
    st.write("앱이 찾아본 폴더:", f"`{BASE_DIR}`")
    st.write("그 폴더 안의 파일:", listing if listing else "(확인하지 못했습니다)")
    st.stop()

try:
    raw_df = load_data(str(csv_file))
except Exception as error:
    st.error(f"데이터를 불러오지 못했습니다.\n\n({error})")
    st.stop()

missing = [c for c in NEED_COLUMNS if c not in raw_df.columns]
if missing:
    st.error(f"필요한 열이 없습니다: {missing}. 파일의 열 이름은 {list(raw_df.columns)} 입니다.")
    st.stop()

df = add_calcs(raw_df)

# ---------------------------------------------------------------- 처음 한 번만: 저장된 기록 불러오기
if "table_base" not in st.session_state:
    saved_meanings, saved_source = load_record()
    meanings_init = {col: str(saved_meanings.get(col, "")) for col in raw_df.columns}
    st.session_state["table_base"] = pd.DataFrame(
        {
            "열 이름": list(raw_df.columns),
            "우리말 뜻": [meanings_init[col] for col in raw_df.columns],
            "값의 종류": [describe_values(raw_df[col]) for col in raw_df.columns],
            "빈 값 개수": [int(raw_df[col].isna().sum()) for col in raw_df.columns],
        }
    )
    st.session_state["source_text"] = saved_source
    st.session_state["last_saved"] = {"meanings": meanings_init, "source": saved_source}

# ---------------------------------------------------------------- 제목
st.title(f"{APP_ICON} {APP_TITLE}")
st.markdown("<div style='font-size:2rem; letter-spacing:0.4rem;'>🚀 🌍 🛰️ 🌙 ⭐ 🪐 ☄️ 👨‍🚀</div>", unsafe_allow_html=True)
st.write(
    "이 데이터는 과학기술정보통신부 중앙전파관리소가 공개한 **인공위성 목록**입니다. "
    "위성의 이름, 번호, 그리고 궤도를 도는 정도를 나타내는 **평균 회전값**이 들어 있습니다."
)

tab_intro, tab_search, tab_chart = st.tabs(["📖 데이터 소개", "🔎 위성 찾기", "📈 그래프"])

# ================================================================ 탭 1: 소개
with tab_intro:
    rev = pd.to_numeric(raw_df["평균 회전값"], errors="coerce")
    cards = [
        ("🛰️ 전체 위성 수", f"{len(raw_df):,}개"),
        ("📋 열 개수", f"{raw_df.shape[1]}개"),
        ("🕳️ 빈 값 총 개수", f"{int(raw_df.isna().sum().sum()):,}개"),
        ("🌀 평균 회전값 범위", f"{rev.min():.2f} ~ {rev.max():.2f}"),
    ]
    for column, (label, value) in zip(st.columns(4), cards):
        column.markdown(
            f'<div class="stat-card"><div class="stat-label">{label}</div>'
            f'<div class="stat-value">{value}</div></div>',
            unsafe_allow_html=True,
        )

    st.subheader("📝 열 설명 표")
    st.caption("'우리말 뜻' 칸을 더블클릭해서 직접 적어 보세요. 적은 내용은 자동으로 저장됩니다.")
    edited = st.data_editor(
        st.session_state["table_base"],
        hide_index=True,
        disabled=["열 이름", "값의 종류", "빈 값 개수"],
        column_config={
            "우리말 뜻": st.column_config.TextColumn("우리말 뜻", help="직접 적어 보세요."),
            "빈 값 개수": st.column_config.NumberColumn("빈 값 개수", format="%d"),
        },
        key="meaning_editor",
    )

    st.subheader("👀 데이터 처음 다섯 줄")
    st.dataframe(
        raw_df.head(5),
        hide_index=True,
        column_config={"위성번호": st.column_config.NumberColumn("위성번호", format="%d")},
    )
    st.caption(
        "위성명 앞의 '0 '은 위성 궤도 자료에서 쓰는 표기로 보입니다. "
        "아래 '위성 찾기'와 '그래프'에서는 이 부분을 지우고 보여 줍니다."
    )

    st.subheader("🔗 데이터 출처")
    st.text_area(
        "데이터 출처",
        key="source_text",
        height=120,
        placeholder="데이터 출처를 여기에 적어 주세요.",
        label_visibility="collapsed",
    )
    st.caption("글을 다 쓴 뒤 칸 바깥을 클릭하거나 Ctrl+Enter를 누르면 저장됩니다.")

# ================================================================ 탭 2: 위성 찾기
with tab_search:
    st.subheader("🔭 위성명으로 찾기")
    query = st.text_input("위성명 또는 위성번호", placeholder="예: 3CAT, AAC, 43467").strip()

    shown = df
    if query:
        by_name = df["위성명(정리)"].str.contains(query, case=False, regex=False)
        by_number = df["위성번호"].astype(str).str.contains(query, regex=False)
        shown = df[by_name | by_number]

    st.write(f"**{len(shown)}개** 위성이 보입니다. (전체 {len(df)}개)")
    if shown.empty:
        st.info("검색 결과가 없습니다. 다른 글자로 찾아보세요.")
    else:
        st.dataframe(
            shown[["위성명(정리)", "위성번호", "평균 회전값", "궤도주기(분)", "고도(km)", "궤도 유형"]]
            .rename(columns={"위성명(정리)": "위성명"}),
            hide_index=True,
            column_config={
                "위성번호": st.column_config.NumberColumn("위성번호", format="%d"),
                "평균 회전값": st.column_config.NumberColumn("평균 회전값", format="%.4f"),
                "궤도주기(분)": st.column_config.NumberColumn("궤도주기(분)", format="%.1f"),
                "고도(km)": st.column_config.NumberColumn("고도(km)", format="%.0f"),
            },
        )
    st.caption(
        "※ 궤도주기와 고도는 평균 회전값을 '하루에 지구를 도는 횟수'라고 보고 계산한 근사값입니다 "
        "(포털에 단위가 적혀 있지 않아 값의 크기를 보고 판단했습니다). "
        "궤도 유형은 고도로 제가 나눈 분류이며 원래 데이터에 있는 값이 아닙니다."
    )

# ================================================================ 탭 3: 그래프
with tab_chart:
    st.subheader("📈 위성번호 순서로 본 평균 회전값 (선그래프)")
    by_number = df.sort_values("위성번호")
    line_fig = px.line(
        by_number,
        x="위성번호",
        y="평균 회전값",
        markers=True,
        hover_name="위성명(정리)",
    )
    line_fig.update_xaxes(type="category")
    st.plotly_chart(line_fig, use_container_width=True)
    st.caption("점 하나가 위성 하나입니다. 위성 사이의 선은 비교를 돕기 위한 것이며, 시간에 따른 변화는 아닙니다.")

    st.subheader("🌌 평균 회전값과 고도의 관계 (산점도)")
    log_scale = st.checkbox("고도를 로그 눈금으로 보기 (값 차이가 클 때 편해요)", value=True)
    scatter_fig = px.scatter(
        df,
        x="평균 회전값",
        y="고도(km)",
        color="궤도 유형",
        hover_name="위성명(정리)",
    )
    if log_scale:
        scatter_fig.update_yaxes(type="log")
    st.plotly_chart(scatter_fig, use_container_width=True)
    st.caption("많이 도는 위성일수록 낮은 곳에 있습니다. 두 값이 같은 계산식으로 이어져 있어 점들이 하나의 곡선 위에 놓입니다.")

    st.subheader("🏆 고도가 높은 위성 순위 (막대그래프)")
    top_n = st.slider("몇 개까지 볼까요?", min_value=3, max_value=min(20, len(df)), value=min(10, len(df)))
    top_df = df.nlargest(top_n, "고도(km)").sort_values("고도(km)")
    rank_fig = px.bar(
        top_df,
        x="고도(km)",
        y="위성명(정리)",
        orientation="h",
        color="궤도 유형",
        hover_data={"위성번호": True, "궤도주기(분)": ":.1f", "고도(km)": ":,.0f"},
    )
    rank_fig.update_yaxes(title="위성명", type="category")
    st.plotly_chart(rank_fig, use_container_width=True)
    st.caption("평균 회전값으로 계산한 고도(원 궤도 가정)가 높은 순서입니다. 막대가 길수록 지구에서 먼 위성입니다.")

    st.subheader("🪐 케플러 제3법칙 확인 (주기² ÷ 궤도 반지름³)")
    kepler = df.copy()
    kepler["궤도 반지름(km)"] = kepler["고도(km)"] + EARTH_RADIUS
    kepler["a³ (km³)"] = kepler["궤도 반지름(km)"] ** 3
    kepler["T² (s²)"] = (kepler["궤도주기(분)"] * 60) ** 2
    k_const = 4 * math.pi**2 / MU  # 이론상 기울기 (s²/km³)
    kepler["T²/a³"] = kepler["T² (s²)"] / kepler["a³ (km³)"]
    kepler_fig = px.scatter(
        kepler,
        x="a³ (km³)",
        y="T² (s²)",
        color="궤도 유형",
        hover_name="위성명(정리)",
        hover_data={"궤도주기(분)": ":.1f", "고도(km)": ":,.0f"},
    )
    x_max = float(kepler["a³ (km³)"].max())
    theory_df = pd.DataFrame({"a³ (km³)": [0, x_max], "T² (s²)": [0, k_const * x_max]})
    theory_fig = px.line(theory_df, x="a³ (km³)", y="T² (s²)")
    theory_fig.update_traces(name="이론선 (T² = 4π²/μ × a³)", showlegend=True, line={"dash": "dash"})
    kepler_fig.add_traces(theory_fig.data)
    st.plotly_chart(kepler_fig, use_container_width=True)
    st.caption(
        f"모든 위성이 한 직선 위에 놓이면 케플러 제3법칙(주기²는 궤도 반지름³에 비례)이 맞는 것입니다. "
        f"계산한 T²/a³의 평균은 {kepler['T²/a³'].mean():.3e}, 이론값 4π²/μ는 {k_const:.3e}입니다."
    )
    st.caption(
        "참고: 이 앱의 고도는 평균 회전값에서 케플러 법칙으로 계산한 값이라, 이 그래프는 계산이 일관된지 확인하는 용도입니다. "
        "위성을 따로 관측해서 법칙을 검증한 것은 아닙니다."
    )

# ---------------------------------------------------------------- 자동 저장
current = {
    "meanings": {
        str(name): ("" if pd.isna(text) else str(text))
        for name, text in zip(edited["열 이름"], edited["우리말 뜻"])
    },
    "source": st.session_state["source_text"],
}
if current != st.session_state["last_saved"]:
    if save_record(current["meanings"], current["source"]):
        st.session_state["last_saved"] = current
        st.toast("내_기록 폴더에 저장했어요.", icon="💾")
    else:
        st.warning("기록을 저장하지 못했습니다. 폴더 쓰기 권한을 확인해 주세요.")
