import streamlit as st
from google import genai
from google.genai import types
import json
import os

# =========================================================
# 1. TETAPAN HALAMAN & KAWALAN AKSES (LOGIN)
# =========================================================
st.set_page_config(page_title="Pro Marketing Command Center", page_icon="⚡", layout="wide")

APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Log Masuk Marketing Agent Hub")
    st.info("Sila masukkan kata laluan keselamatan untuk mengakses sistem.")
    pwd_input = st.text_input("Kata Laluan:", type="password")
    if st.button("Log Masuk 🚀"):
        if pwd_input == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Kata laluan tidak sah! Sila cuba lagi.")
    st.stop()

# =========================================================
# 2. SAMBUNGAN GEMINI CLIENT
# =========================================================
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if not API_KEY:
    st.error("Ralat: GEMINI_API_KEY tidak dijumpai di Streamlit Secrets!")
    st.stop()

client = genai.Client(api_key=API_KEY)

# =========================================================
# 3. PANGKALAN PENGETAHUAN PRODUK (DEFAULT KNOWLEDGE)
# =========================================================
DEFAULT_KNOWLEDGE = {
    "Tone Wow": {
        "kategori": "Telco & Pendapatan Pasif",
        "usp": "Simkad prabayar pelan data jimat yang memberi insentif komisen rujukan setiap kali pengguna topup.",
        "avatar": "Pengguna telefon pintar yang ingin kurangkan beban bil & individu mencari pendapatan sampingan.",
        "compliance": "Dilarang janjikan pendapatan goyang kaki atau guna istilah skim cepat kaya / skim piramid."
    },
    "Eastel": {
        "kategori": "Telco Mampu Milik",
        "usp": "Penyedia pelan internet pantas dengan kuota besar pada kadar mampu milik mesra poket.",
        "avatar": "Pelajar, penghantar makanan / gig workers, dan keluarga yang mengutamakan penjimatan.",
        "compliance": "Fokus pada kestabilan liputan dan penjimatan kos bulanan."
    },
    "Produk AI": {
        "kategori": "Automasi & Perisian AI",
        "usp": "Sistem ejen pintar untuk automasi copywriting, analisis data, dan sokongan pemasaran bisnes.",
        "avatar": "Pemilik bisnes PKS, usahawan solo, dan pencipta kandungan digital.",
        "compliance": "Jangan buat kenyataan palsu (overclaim) bahawa AI menggantikan 100% manusia tanpa semakan fakta."
    },
    "BeliBeliOnline": {
        "kategori": "Marketplace & E-Commerce Tempatan",
        "usp": "Platform e-dagang tempatan mesra peniaga kecil dengan kadar komisen adil dan sokongan komuniti usahawan.",
        "avatar": "Peniaga kecil IKS tempatan dan pembeli barangan buatan Malaysia.",
        "compliance": "Elakkan membuat perbandingan agresif atau memburukkan platform e-commerce lain."
    }
}

# =========================================================
# 4. INISIALISASI MEMORI SESI (SESSION STATE)
# =========================================================
if "research_store" not in st.session_state:
    st.session_state.research_store = {}  # Memori L1 bagi setiap produk
if "content_history" not in st.session_state:
    st.session_state.content_history = [] # Sejarah draf L2 & laporan L3

# =========================================================
# 5. SIDEBAR: PEMILIHAN PRODUK & KEMAS KINI PDF
# =========================================================
st.sidebar.title("🎛️ Pusat Kawalan Produk")
selected_product = st.sidebar.selectbox("Pilih Produk:", list(DEFAULT_KNOWLEDGE.keys()))

st.sidebar.markdown("---")
st.sidebar.subheader("📄 Kemas Kini Pengetahuan Terkini")
uploaded_pdf = st.sidebar.file_uploader(f"Muat naik PDF baru ({selected_product})", type=["pdf"])

product_info = DEFAULT_KNOWLEDGE[selected_product]
with st.sidebar.expander("📌 Info Asas Produk"):
    st.write(f"**USP:** {product_info['usp']}")
    st.write(f"**Sasaran:** {product_info['avatar']}")
    st.write(f"**Pematuhan:** {product_info['compliance']}")

# Butang Logout di Sidebar
if st.sidebar.button("Log Keluar"):
    st.session_state.authenticated = False
    st.rerun()

# =========================================================
# 6. PAPARAN UTAMA (L1 -> L2 -> L3)
# =========================================================
st.title(f"⚡ Command Center: {selected_product}")
st.write("Seni bina Multi-Agent: Research dijalankan sekali (L1), Copywriting dijana berulang kali (L2), dan disemak automatik oleh QA (L3).")

# ---------------------------------------------------------
# BAHAGIAN L1: TEAM RESEARCH (Jalankan Sekali / Cached)
# ---------------------------------------------------------
st.markdown("### 🔍 Tahap 1: Laporan Kajian Pasaran (Research Hub)")

has_research = selected_product in st.session_state.research_store
status_text = "✅ Sedia dalam memori (Boleh terus guna di L2)" if has_research else "⚠️ Belum dijalankan untuk produk ini"
st.info(f"Status Kajian Produk **{selected_product}**: {status_text}")

col_r1, col_r2 = st.columns([3, 1])
with col_r1:
    research_focus = st.text_input(
        "Fokus Tambahan untuk Kajian Pasaran (Pilihan):", 
        placeholder="Contoh: Kaji trend cabaran kewangan peniaga kecil masa kini"
    )
with col_r2:
    btn_research = st.button("Jana / Kemas Kini Research (L1) 🧠", type="secondary")

if btn_research:
    with st.spinner("Research Agent sedang membedah pasaran & membaca dokumen..."):
        pdf_attachment = None
        if uploaded_pdf is not None:
            temp_path = f"temp_{uploaded_pdf.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_pdf.getbuffer())
            pdf_attachment = client.files.upload(file=temp_path)
            os.remove(temp_path)

        prompt_payload = [
            f"Produk: {selected_product}",
            f"Profil Asas Produk: {json.dumps(product_info)}",
            f"Fokus Tambahan: {research_focus if research_focus else 'Kajian pasaran menyeluruh'}",
            "Tugasan: Sediakan Customer Avatar terperinci, senaraikan 3 Masalah Utama (Pain Points), dan cadangkan 3 Sudut Pemasaran (Angles) yang paling berkesan di Malaysia."
        ]
        if pdf_attachment:
            prompt_payload.append(pdf_attachment)

        res_research = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt_payload,
            config=types.GenerateContentConfig(
                system_instruction="Awak ialah Market Research Specialist berpengalaman luas dalam pasaran tempatan Malaysia."
            )
        )
        st.session_state.research_store[selected_product] = res_research.text
        st.success("Kajian L1 berjaya disimpan dalam memori!")
        st.rerun()

# Paparkan hasil kajian jika wujud
if has_research:
    with st.expander("📖 Lihat Dokumen Research L1 Terperinci"):
        st.markdown(st.session_state.research_store[selected_product])

st.markdown("---")

# ---------------------------------------------------------
# BAHAGIAN L2 & L3: TEAM CONTENT & DATA ANALYST / QA
# ---------------------------------------------------------
st.markdown("### ✍️ Tahap 2 & 3: Penjanaan Kandungan & Semakan QA Automatik")

if not has_research:
    st.warning("Sila jalankan Tahap 1 (Research Hub) terlebih dahulu sebelum menjana kandungan.")
else:
    c1, c2 = st.columns(2)
    with c1:
        campaign_theme = st.text_input("Tema Kempen Hari Ini:", placeholder="Contoh: Kempen Gaji Masuk / Cuti Sekolah / Tawaran Terhad")
    with c2:
        angle_choice = st.selectbox("Gaya / Pendekatan:", [
            "Emosi & Storytelling (Kisah Kehidupan / Selesaikan Masalah)",
            "Direct Response (Tawaran Segera, Mendesak & Diskaun)",
            "Edukasi / Nilai Tambah (Tips Percuma & Kesedaran)"
        ])

    btn_content = st.button("Jana Draf Iklan Baru (L2) 🚀", type="primary")

    if btn_content:
        if not campaign_theme.strip():
            st.warning("Sila masukkan Tema Kempen sebelum menjana draf!")
        else:
            cached_research = st.session_state.research_store[selected_product]

            # 1. Panggil Content & Visual Agent (L2)
            with st.spinner("Content Agent sedang mengarang copywriting & idea visual..."):
                content_prompt = f"""
                Produk: {selected_product}
                Tema Kempen: {campaign_theme}
                Pendekatan Pemasaran: {angle_choice}
                Sumber Kajian Induk (L1):
                {cached_research}

                Tugasan:
                1. Tulis 1 salinan Facebook Post yang santai, memikat jiwa, dan ada Call-To-Action (CTA) jelas.
                2. Tulis 1 bebenang X / Twitter yang pendek dan padat (Hook + Isi + CTA).
                3. Berikan 1 cadangan Visual (Prompt imej AI atau konsep poster Canva).
                """
                res_content = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=content_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction="Awak ialah Senior Copywriter dan Creative Director di Malaysia."
                    )
                )
                draft_text = res_content.text

            # 2. Panggil Data Analyst & QA Agent (L3) secara automatik
            with st.spinner("QA Agent sedang mengaudit kualiti, fakta & integriti iklan..."):
                qa_prompt = f"""
                Produk: {selected_product}
                Peraturan Integriti & Compliance: {product_info['compliance']}
                Draf Iklan yang Dihasilkan:
                {draft_text}

                Tugasan:
                1. Berikan Skor Kualiti (1 hingga 10).
                2. Semak jika ada overclaim, kenyataan palsu, atau risiko melanggar etika.
                3. Berikan komen penambahbaikan ringkas.
                """
                res_qa = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=qa_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction="Awak ialah Data Analyst & QA Compliance Officer yang sangat teliti dan beretika."
                    )
                )
                qa_report_text = res_qa.text

            # Simpan dalam senarai arkib sesi
            st.session_state.content_history.insert(0, {
                "product": selected_product,
                "theme": campaign_theme,
                "angle": angle_choice,
                "content": draft_text,
                "qa": qa_report_text
            })
            st.success("Kandungan berjaya dijana dan selesai diaudit oleh QA!")

# Paparkan arkib draf kandungan terkini
if st.session_state.content_history:
    st.markdown("---")
    st.subheader("📂 Arkib Draf Iklan & Laporan Audit Terkini")

    for i, item in enumerate(st.session_state.content_history):
        with st.container():
            st.markdown(f"#### 🏷️ #{len(st.session_state.content_history) - i} | [{item['product']}] {item['theme']} — *{item['angle']}*")
            tab_copy, tab_audit = st.tabs(["📝 Salinan Iklan & Visual (L2)", "⚖️ Laporan QA & Integriti (L3)"])
            with tab_copy:
                st.markdown(item["content"])
            with tab_audit:
                st.markdown(item["qa"])
            st.markdown("---")
